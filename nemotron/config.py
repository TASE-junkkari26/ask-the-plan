"""Explicit provider settings; importing this module never loads credentials."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Mapping
from urllib.parse import urlsplit

from dotenv import dotenv_values
from pydantic import BaseModel, ConfigDict, Field, SecretStr, ValidationError, field_validator

DEFAULT_BASE_URL = "https://containers.datacrunch.io/nemotron-3-5-super-vl-b300/v1"
DEFAULT_MODEL = "nemotron-3.5-super-vl"
ENV_FIELDS = {
    "api_key": "VERDA_INFERENCE_KEY",
    "base_url": "VERDA_BASE_URL",
    "model": "VERDA_MODEL",
    "timeout_seconds": "VERDA_TIMEOUT_SECONDS",
    "max_retries": "VERDA_MAX_RETRIES",
    "max_tokens": "VERDA_MAX_TOKENS",
    "temperature": "VERDA_TEMPERATURE",
    "enable_thinking": "VERDA_ENABLE_THINKING",
}


class ConfigurationError(ValueError):
    """Configuration cannot be used; messages never contain credential values."""


def default_env_file() -> Path:
    # Editable checkout: resolve independently of the caller's working directory.
    root = Path(__file__).resolve().parents[1]
    return (root if (root / "pyproject.toml").is_file() else Path.cwd()) / ".env"


class NemotronSettings(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", hide_input_in_errors=True)

    api_key: SecretStr = Field(repr=False)
    base_url: str = DEFAULT_BASE_URL
    model: str = DEFAULT_MODEL
    timeout_seconds: float = Field(default=120, gt=0, le=600, allow_inf_nan=False)
    max_retries: int = Field(default=2, ge=0, le=5)
    max_tokens: int = Field(default=2048, gt=0)
    temperature: float = Field(default=0.2, ge=0, le=2, allow_inf_nan=False)
    enable_thinking: bool | None = False

    @field_validator("api_key")
    @classmethod
    def valid_key(cls, value: SecretStr) -> SecretStr:
        key = value.get_secret_value().strip()
        if not key or key.lower() in {"your-api-key", "your_api_key", "paste-your-api-key-here", "changeme"}:
            raise ValueError("paste your inference key into VERDA_INFERENCE_KEY in .env")
        if any(character.isspace() for character in key):
            raise ValueError("VERDA_INFERENCE_KEY must not contain whitespace")
        return SecretStr(key)

    @field_validator("base_url")
    @classmethod
    def valid_url(cls, value: str) -> str:
        value = value.strip().rstrip("/")
        url = urlsplit(value)
        if (url.scheme not in {"https", "http"} or not url.hostname
                or url.username or url.password or url.query or url.fragment):
            raise ValueError("VERDA_BASE_URL must be an HTTP(S) base URL without credentials, query, or fragment")
        # Validate malformed/out-of-range ports without echoing the URL.
        try:
            url.port
        except ValueError:
            raise ValueError("VERDA_BASE_URL contains an invalid port") from None
        return value

    @field_validator("model")
    @classmethod
    def valid_model(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("VERDA_MODEL must not be empty")
        return value.strip()

    @classmethod
    def from_env(cls, env_file: str | Path | None = None, *,
                 environ: Mapping[str, str] | None = None) -> NemotronSettings:
        path = Path(env_file) if env_file is not None else default_env_file()
        if env_file is not None and not path.is_file():
            raise ConfigurationError("The explicit --env-file does not exist or is not a file.")
        try:
            # Do not mutate os.environ or expand '$' sequences in credentials.
            file_values = dotenv_values(path, encoding="utf-8-sig", interpolate=False) if path.is_file() else {}
        except (OSError, UnicodeError):
            raise ConfigurationError("Could not read the local .env file as UTF-8.") from None
        values = {**file_values, **(os.environ if environ is None else environ)}
        fields = {field: values[name] for field, name in ENV_FIELDS.items() if name in values}
        if not fields.get("api_key"):
            raise ConfigurationError("Paste your Verda inference key into VERDA_INFERENCE_KEY in the repository's .env file.")
        if str(fields.get("enable_thinking", "")).lower() == "auto":
            fields["enable_thinking"] = None
        try:
            return cls(**fields)
        except ValidationError as exc:
            # Pydantic's default error dictionaries contain input values. Never
            # log those, even for malformed credentials or a credential in a URL.
            names = ", ".join(ENV_FIELDS[str(error["loc"][0])] for error in exc.errors())
            raise ConfigurationError(f"Invalid {names}; check .env.example for the supported settings.") from None
