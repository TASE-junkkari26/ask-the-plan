"""Settings for the separate, non-generative Decisions API."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Literal, Mapping

from dotenv import dotenv_values
from pydantic import BaseModel, ConfigDict, Field, SecretStr, ValidationError, field_validator

from nemotron.config import ConfigurationError, default_env_file
from .config import GeminiSettings


class DecisionsSettings(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", hide_input_in_errors=True)

    api_key: SecretStr = Field(repr=False)
    model: Literal["gemini-decision-1"] = "gemini-decision-1"
    timeout_seconds: float = Field(default=10, gt=0, le=30, allow_inf_nan=False)

    @field_validator("api_key")
    @classmethod
    def valid_key(cls, value: SecretStr) -> SecretStr:
        return GeminiSettings.valid_key(value)

    @classmethod
    def from_env(cls, env_file: str | Path | None = None, *,
                 environ: Mapping[str, str] | None = None) -> DecisionsSettings:
        path = Path(env_file) if env_file is not None else default_env_file()
        if env_file is not None and not path.is_file():
            raise ConfigurationError("The explicit Decisions environment file does not exist.")
        try:
            file_values = dotenv_values(path, encoding="utf-8-sig", interpolate=False) if path.is_file() else {}
        except (OSError, UnicodeError):
            raise ConfigurationError("Could not read the Decisions environment file as UTF-8.") from None
        values = {**file_values, **(os.environ if environ is None else environ)}
        fields = {field: values[name] for field, name in {
            "api_key": "GEMINI_API_KEY", "timeout_seconds": "GEMINI_DECISIONS_TIMEOUT_SECONDS",
        }.items() if name in values}
        if not fields.get("api_key"):
            raise ConfigurationError("Set GEMINI_API_KEY in the backend environment or repository .env.")
        try:
            return cls(**fields)
        except ValidationError:
            raise ConfigurationError("Invalid Decisions settings; check .env.example for supported settings.") from None
