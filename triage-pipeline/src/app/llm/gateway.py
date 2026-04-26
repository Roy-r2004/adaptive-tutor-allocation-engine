"""Multi-provider LLM gateway.

- LiteLLM under the hood: handles provider routing, cost calculation, and the
  fallback chain Groq → Gemini → OpenAI → Ollama.
- Structured output enforced via response_format=json_object + Pydantic validation
  on the application side. Falls back to robust JSON extraction if the model
  ignores instructions.
- Every successful or failed call writes an llm_calls row.

This file is the only place in the codebase that talks to a model.
"""

from __future__ import annotations

import asyncio
import json
import re
import time
import uuid
from functools import lru_cache
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from app.core.config import get_settings
from app.core.db import session_scope
from app.core.logging import get_logger
from app.llm.tracking import record_llm_call

logger = get_logger(__name__)

T = TypeVar("T", bound=BaseModel)

# Match a JSON object even when wrapped in markdown fences or prose.
_JSON_BLOCK_RE = re.compile(r"\{(?:[^{}]|(?:\{[^{}]*\}))*\}", re.DOTALL)


class LLMError(Exception):
    """All providers failed."""


class LLMValidationError(Exception):
    """The model returned content but it didn't match the requested schema."""


class LLMGateway:
    """Thin wrapper over litellm.acompletion with fallback + structured-output retry."""

    def __init__(self) -> None:
        settings = get_settings()
        self.primary_model = settings.llm_primary_model
        self.fallback_models = list(settings.llm_fallback_models)
        self.temperature = settings.llm_temperature
        self.max_tokens = settings.llm_max_tokens
        self.timeout = settings.llm_timeout_seconds

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def complete_structured(
        self,
        *,
        prompt: str,
        schema: type[T],
        operation: str,
        ticket_id: uuid.UUID | str | None = None,
        tenant_id: str = "default",
        prompt_version_id: uuid.UUID | str | None = None,
        system: str | None = None,
        max_retries: int = 1,
    ) -> T:
        """Call the model and validate the response against `schema`.

        Strategy:
          1. Try primary model. On any error, fall through fallbacks.
          2. After we have a string response, try strict JSON parse → schema validate.
          3. On ValidationError, do ONE reflection retry (feed validation error back).
        """
        chain = [self.primary_model, *self.fallback_models]
        last_err: Exception | None = None

        for attempt_idx, model in enumerate(chain):
            try:
                raw = await self._call(
                    model=model,
                    prompt=prompt,
                    system=system,
                    operation=operation,
                    ticket_id=ticket_id,
                    tenant_id=tenant_id,
                    prompt_version_id=prompt_version_id,
                    json_mode=True,
                )
                parsed = _extract_json(raw)
                try:
                    return schema.model_validate(parsed)
                except ValidationError as ve:
                    if max_retries <= 0:
                        raise LLMValidationError(str(ve)) from ve
                    # Reflection retry — same model, give it the error.
                    reflective = (
                        f"{prompt}\n\n"
                        f"Your previous response failed schema validation: {ve}\n"
                        f"Return ONLY a valid JSON object matching the schema."
                    )
                    raw2 = await self._call(
                        model=model,
                        prompt=reflective,
                        system=system,
                        operation=f"{operation}_retry",
                        ticket_id=ticket_id,
                        tenant_id=tenant_id,
                        prompt_version_id=prompt_version_id,
                        json_mode=True,
                    )
                    parsed2 = _extract_json(raw2)
                    return schema.model_validate(parsed2)
            except LLMValidationError:
                raise
            except Exception as e:  # noqa: BLE001 — fall through to next model
                last_err = e
                logger.warning(
                    "llm_provider_failed",
                    model=model,
                    operation=operation,
                    error=str(e),
                    is_last=(attempt_idx == len(chain) - 1),
                )
                continue

        raise LLMError(f"All providers failed for {operation}: {last_err}") from last_err

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential_jitter(initial=0.5, max=4),
        retry=retry_if_exception_type((TimeoutError, ConnectionError)),
        reraise=True,
    )
    async def _call(
        self,
        *,
        model: str,
        prompt: str,
        system: str | None,
        operation: str,
        ticket_id: uuid.UUID | str | None,
        tenant_id: str,
        prompt_version_id: uuid.UUID | str | None,
        json_mode: bool,
    ) -> str:
        """Single LLM call. Records cost/tokens regardless of outcome."""
        try:
            import litellm
        except ImportError as e:
            raise LLMError(
                "litellm not installed. Run `pip install litellm`."
            ) from e

        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "timeout": self.timeout,
        }
        if json_mode and not model.startswith("ollama/"):
            kwargs["response_format"] = {"type": "json_object"}

        start = time.perf_counter()
        resp = None
        outcome = "success"
        error: str | None = None

        try:
            resp = await litellm.acompletion(**kwargs)
            content = resp.choices[0].message.content or ""
            return content
        except Exception as e:
            outcome = "error"
            error = f"{type(e).__name__}: {e}"
            raise
        finally:
            latency_ms = int((time.perf_counter() - start) * 1000)
            try:
                await self._record(
                    model=model,
                    operation=operation,
                    ticket_id=ticket_id,
                    tenant_id=tenant_id,
                    prompt_version_id=prompt_version_id,
                    messages=messages,
                    response=resp,
                    latency_ms=latency_ms,
                    outcome=outcome,
                    error=error,
                )
            except Exception as record_err:  # noqa: BLE001
                logger.warning("llm_call_record_failed", error=str(record_err))

    async def _record(
        self,
        *,
        model: str,
        operation: str,
        ticket_id: uuid.UUID | str | None,
        tenant_id: str,
        prompt_version_id: uuid.UUID | str | None,
        messages: list[dict[str, str]],
        response: Any,
        latency_ms: int,
        outcome: str,
        error: str | None,
    ) -> None:
        provider, _, _ = model.partition("/")
        prompt_tokens = completion_tokens = total_tokens = 0
        cost_usd = 0.0
        response_dict: dict[str, Any] | None = None
        if response is not None:
            try:
                usage = getattr(response, "usage", None)
                if usage is not None:
                    prompt_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
                    completion_tokens = int(getattr(usage, "completion_tokens", 0) or 0)
                    total_tokens = int(getattr(usage, "total_tokens", 0) or 0)
                # Best-effort cost calc; not all providers expose pricing in litellm
                try:
                    import litellm

                    cost_usd = float(litellm.completion_cost(completion_response=response) or 0.0)
                except Exception:  # noqa: BLE001
                    cost_usd = 0.0
                content = response.choices[0].message.content or ""
                response_dict = {"content": content[:4000]}
            except Exception as e:  # noqa: BLE001
                logger.warning("llm_call_response_inspect_failed", error=str(e))

        async with session_scope() as s:
            await record_llm_call(
                s,
                ticket_id=_coerce_uuid(ticket_id),
                tenant_id=tenant_id,
                operation=operation,
                provider=provider,
                model=model,
                prompt_version_id=_coerce_uuid(prompt_version_id),
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens or (prompt_tokens + completion_tokens),
                cost_usd=cost_usd,
                latency_ms=latency_ms,
                outcome=outcome,
                error=error,
                request={"messages": [_truncate_msg(m) for m in messages]},
                response=response_dict,
            )


def _coerce_uuid(value: uuid.UUID | str | None) -> uuid.UUID | None:
    if value is None:
        return None
    if isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value))
    except (ValueError, TypeError):
        return None


def _truncate_msg(m: dict[str, str]) -> dict[str, str]:
    return {**m, "content": (m.get("content") or "")[:4000]}


def _extract_json(text: str) -> dict[str, Any]:
    """Robust JSON extraction. Handles markdown fences and prose wrappers."""
    if not text:
        raise LLMValidationError("Empty response from model")

    # Try direct parse first
    text = text.strip()
    try:
        return json.loads(text)  # type: ignore[no-any-return]
    except json.JSONDecodeError:
        pass

    # Strip markdown fences
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*\n?", "", text)
        text = re.sub(r"\n?```\s*$", "", text)
        try:
            return json.loads(text)  # type: ignore[no-any-return]
        except json.JSONDecodeError:
            pass

    # Find the first JSON object substring
    match = _JSON_BLOCK_RE.search(text)
    if match:
        try:
            return json.loads(match.group(0))  # type: ignore[no-any-return]
        except json.JSONDecodeError as e:
            raise LLMValidationError(f"Found JSON-like block but failed to parse: {e}") from e

    raise LLMValidationError(f"No JSON object found in response: {text[:300]!r}")


@lru_cache(maxsize=1)
def get_gateway() -> LLMGateway:
    return LLMGateway()


# Ensure asyncio doesn't complain on quick test loops
async def _warmup() -> None:  # pragma: no cover
    await asyncio.sleep(0)
