"""Application configuration via pydantic-settings.

All env-driven config lives here. Secrets use SecretStr so they never leak in
logs or repr(). Reads from .env, .env.local, and Docker/K8s secrets at /run/secrets.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any, Literal

from pydantic import Field, RedisDsn, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", ".env.local"),
        env_nested_delimiter="__",
        secrets_dir="/run/secrets",
        extra="ignore",
        case_sensitive=False,
    )

    @classmethod
    def settings_customise_sources(  # type: ignore[override]
        cls, settings_cls, init_settings, env_settings, dotenv_settings, file_secret_settings
    ):
        # Custom env source that handles CSV for list fields (avoids needing JSON syntax in .env)
        class _CSVAwareEnv:
            def __init__(self, base: Any) -> None:
                self._base = base

            def __call__(self) -> dict[str, Any]:
                raw: dict[str, Any] = {}
                # Walk known fields and pull strings from os.environ ourselves
                import os as _os

                csv_fields = {
                    "internal_api_keys",
                    "llm_fallback_models",
                    "escalation_keywords",
                    "cors_origins",
                }
                for field_name in cls.model_fields:
                    env_key = field_name.upper()
                    if env_key not in _os.environ:
                        continue
                    val = _os.environ[env_key]
                    if field_name in csv_fields:
                        raw[field_name] = [p.strip() for p in val.split(",") if p.strip()]
                    else:
                        raw[field_name] = val
                return raw

            def __repr__(self) -> str:
                return "_CSVAwareEnv()"

        return (init_settings, _CSVAwareEnv(env_settings), dotenv_settings, file_secret_settings)

    # --- Environment ---
    env: Literal["dev", "test", "staging", "prod"] = "dev"
    service_name: str = "ai-triage"
    log_level: str = "INFO"
    log_format: Literal["json", "console"] = "console"

    # --- API ---
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_v1_prefix: str = "/v1"
    cors_origins: list[str] = Field(default_factory=lambda: ["*"])
    internal_api_keys: list[SecretStr] = Field(default_factory=list)

    # --- Database ---
    database_url: str = "postgresql+asyncpg://app:app@postgres:5432/app"
    db_pool_size: int = 10
    db_max_overflow: int = 20
    db_echo: bool = False

    # --- Redis / Queue ---
    redis_url: RedisDsn = "redis://redis:6379/0"  # type: ignore[assignment]

    # --- LLM provider keys ---
    groq_api_key: SecretStr | None = None
    gemini_api_key: SecretStr | None = None
    openai_api_key: SecretStr | None = None
    ollama_base_url: str = "http://ollama:11434"

    # --- LLM model identifiers (overridable per env) ---
    llm_primary_model: str = "groq/llama-3.3-70b-versatile"
    llm_fallback_models: list[str] = Field(
        default_factory=lambda: [
            "gemini/gemini-2.0-flash",
            "openai/gpt-4o-mini",
            "ollama/llama3.1",
        ]
    )
    llm_temperature: float = 0.0
    llm_max_tokens: int = 1024
    llm_timeout_seconds: int = 30
    llm_num_retries: int = 2

    # --- Observability ---
    otel_exporter_otlp_endpoint: str | None = None
    langfuse_host: str = "http://langfuse:3000"
    langfuse_public_key: SecretStr | None = None
    langfuse_secret_key: SecretStr | None = None

    # --- Escalation thresholds (mirrors /docs/escalation.md) ---
    escalation_confidence_threshold: float = 0.70
    escalation_billing_threshold_usd: float = 500.0
    escalation_keywords: list[str] = Field(
        default_factory=lambda: [
            "outage",
            "down for all users",
            "production down",
            "data loss",
            "security breach",
        ]
    )

    # --- Worker ---
    worker_max_jobs: int = 20
    worker_job_timeout: int = 300
    worker_max_tries: int = 5

    @field_validator("internal_api_keys", mode="before")
    @classmethod
    def _split_keys(cls, v: object) -> object:
        if isinstance(v, str):
            return [k.strip() for k in v.split(",") if k.strip()]
        return v

    @field_validator("escalation_keywords", "llm_fallback_models", mode="before")
    @classmethod
    def _split_csv(cls, v: object) -> object:
        if isinstance(v, str):
            return [k.strip() for k in v.split(",") if k.strip()]
        return v

    @property
    def is_production(self) -> bool:
        return self.env == "prod"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached singleton accessor — call this everywhere instead of `Settings()`."""
    return Settings()  # type: ignore[call-arg]
