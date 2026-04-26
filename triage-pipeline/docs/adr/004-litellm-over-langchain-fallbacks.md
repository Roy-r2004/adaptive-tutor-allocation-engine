# ADR 004 — LiteLLM for provider routing


## Context

We need a way to send completions to one of {Groq, Gemini, OpenAI,
Ollama}, with automatic fallback when the primary provider is down,
rate-limited, or returns malformed output. Three approaches:

1. **LangChain's `with_fallbacks`** — chains a list of `ChatModel`s,
   tries them in order on exception.
2. **LiteLLM** — unified API across 100+ providers, built-in cost
   catalog, per-error fallback policies, cooldown timers.
3. **Hand-roll it** — try/except chain in our gateway.

## Decision

**LiteLLM, wrapped in our own `LLMGateway` class so swapping the
underlying lib stays a one-day change.**

## Why

- **Per-error-class fallback.** LiteLLM supports different fallback
  behavior depending on whether the failure was a rate limit
  (`RateLimitError`), context window (`ContextWindowExceededError`),
  or content policy (`ContentPolicyViolationError`). LangChain's
  `with_fallbacks` treats every exception identically.
- **Cost catalog.** `litellm.completion_cost(response)` maps the
  response back to the provider's pricing and gives a USD figure. We
  log this on every call into `llm_calls.cost_usd`. Building this
  manually means maintaining a pricing dictionary per provider.
- **Cooldown timers.** Once a provider returns N failures in a window,
  LiteLLM puts it on a cooldown so we stop hammering it. Implementing
  this hand-rolled is a circuit breaker library plus testing it.
- **Unified function-calling and JSON mode.** When we eventually use
  tools, the API is consistent across providers.

## What we don't use from LiteLLM

- The Router and proxy server. Our gateway uses just
  `litellm.acompletion`. The Router/proxy are operationally heavy and
  not needed for our workload.
- Vendor-specific guardrails (most are disabled by default anyway).

## Tradeoffs

- LiteLLM has a wide surface area. Mitigated by wrapping it in our
  own narrow `LLMGateway.complete_structured(...)` API.
- Bug surface area: occasional bugs in cost calc for new models.
  Mitigated by `try/except` around the cost call (see
  `src/app/llm/gateway.py`).

## Consequences

- LiteLLM is in `pyproject.toml`. Provider keys are read from env via
  `Settings`. Switching primary or fallback providers is a config
  change, not a code change.
- Every call writes a row to `llm_calls` with provider, model,
  tokens, cost, latency, outcome — the foundation of FinOps for the
  service.
