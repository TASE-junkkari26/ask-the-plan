"""Backend-only allowlisted Gemini profiles; loading never mutates the environment."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Literal, Mapping

from dotenv import dotenv_values
from pydantic import BaseModel, ConfigDict, Field, SecretStr, ValidationError, field_validator, model_validator

from nemotron.config import ConfigurationError, default_env_file

DEFAULT_MODEL = "gemini-4-hydrogen"
ENV_FIELDS = {
    "api_key": "GEMINI_API_KEY",
    "model": "GEMINI_MODEL",
    "thinking_level": "GEMINI_THINKING_LEVEL",
    "max_output_tokens": "GEMINI_MAX_OUTPUT_TOKENS",
    "timeout_seconds": "GEMINI_TIMEOUT_SECONDS",
}


class GeminiSettings(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", hide_input_in_errors=True)

    api_key: SecretStr = Field(repr=False)
    model: Literal["gemini-4-hydrogen", "gemini-4-carbon"] = DEFAULT_MODEL
    thinking_level: Literal["low", "medium"] = "low"
    max_output_tokens: int = Field(default=65536, gt=0, le=65536)
    timeout_seconds: float = Field(default=120, gt=0, le=600, allow_inf_nan=False)

    @model_validator(mode="after")
    def valid_profile(self) -> GeminiSettings:
        if self.model == "gemini-4-hydrogen" and self.thinking_level != "low":
            raise ValueError("Hydrogen requires low thinking; Carbon supports low or medium")
        return self

    def profile(self, name: Literal["normal", "strong"], *,
                thinking_level: Literal["low", "medium"] = "medium") -> GeminiSettings:
        """Return a validated profile without mutating shared settings or secrets."""
        if name not in {"normal", "strong"} or thinking_level not in {"low", "medium"}:
            raise ValueError("Unknown Gemini analysis profile")
        values = self.model_dump()
        values.update(model="gemini-4-hydrogen" if name == "normal" else "gemini-4-carbon",
                      thinking_level="low" if name == "normal" else thinking_level)
        return type(self).model_validate(values)

    @field_validator("api_key")
    @classmethod
    def valid_key(cls, value: SecretStr) -> SecretStr:
        key = value.get_secret_value().strip()
        if (not key or key.lower() in {
                "your-api-key", "your_api_key", "paste-your-api-key-here", "changeme"}
                or any(ord(character) < 33 or ord(character) > 126 for character in key)):
            raise ValueError("GEMINI_API_KEY must contain a valid nonblank API credential")
        return SecretStr(key)

    @classmethod
    def from_env(cls, env_file: str | Path | None = None, *,
                 environ: Mapping[str, str] | None = None) -> GeminiSettings:
        path = Path(env_file) if env_file is not None else default_env_file()
        if env_file is not None and not path.is_file():
            raise ConfigurationError("The explicit Gemini environment file does not exist.")
        try:
            file_values = dotenv_values(path, encoding="utf-8-sig", interpolate=False) if path.is_file() else {}
        except (OSError, UnicodeError):
            raise ConfigurationError("Could not read the Gemini environment file as UTF-8.") from None
        values = {**file_values, **(os.environ if environ is None else environ)}
        fields = {field: values[name] for field, name in ENV_FIELDS.items() if name in values}
        if not fields.get("api_key"):
            raise ConfigurationError("Set GEMINI_API_KEY in the backend environment or repository .env.")
        try:
            return cls(**fields)
        except ValidationError:
            raise ConfigurationError("Invalid GEMINI settings; check .env.example for supported settings.") from None
