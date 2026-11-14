"""API-only limits; loading never changes the process environment."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Literal, Mapping
from urllib.parse import urlsplit

from dotenv import dotenv_values
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from nemotron.config import ConfigurationError, default_env_file
from nemotron.client import MAX_IMAGE_BYTES


class ApiSettings(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", hide_input_in_errors=True)

    provider: Literal["nemotron", "gemini"] = "nemotron"
    routing_mode: Literal["off", "shadow", "auto"] = "off"
    routing_threshold: float = Field(default=0.6, ge=0.5, le=1, allow_inf_nan=False)
    routing_strong_threshold: float = Field(default=0.8, ge=0.5, le=1, allow_inf_nan=False)
    routing_timeout_seconds: float = Field(default=10, gt=0, le=30, allow_inf_nan=False)
    routing_cache_entries: int = Field(default=32, ge=0, le=256)
    routing_strong_thinking_level: Literal["low", "medium"] = "medium"
    max_image_bytes: int = Field(default=MAX_IMAGE_BYTES, gt=0, le=MAX_IMAGE_BYTES)
    max_pixels: int = Field(default=40_000_000, gt=0, le=80_000_000)
    max_body_bytes: int = Field(default=22 * 1024 * 1024, gt=0)
    max_question_chars: int = Field(default=4000, gt=0, le=4000)
    max_concurrent: int = Field(default=2, gt=0, le=32)
    deadline_seconds: float = Field(default=180, gt=0, le=600, allow_inf_nan=False)
    max_tokens: int = Field(default=8192, gt=0)
    preprocess_mode: Literal["off", "original", "overview"] = "original"
    preprocess_overview_long_edge: int = Field(default=1600, ge=128, le=8192)
    preprocess_cache_entries: int = Field(default=8, ge=1, le=64)
    origins: list[str] = Field(default_factory=lambda: [
        "http://127.0.0.1:5173", "http://localhost:5173",
    ])

    @model_validator(mode="after")
    def routing_configuration(self):
        if self.routing_mode != "off":
            if self.provider != "gemini":
                raise ValueError("routing requires the Gemini image provider")
            if self.preprocess_mode == "overview":
                raise ValueError("initial routing requires original full-image pixels")
        return self

    @field_validator("origins")
    @classmethod
    def valid_origins(cls, values: list[str]) -> list[str]:
        for value in values:
            url = urlsplit(value)
            if (url.scheme not in {"http", "https"} or not url.hostname
                    or url.username or url.password or url.path or url.query or url.fragment):
                raise ValueError("origins must be explicit HTTP(S) origins without paths")
            try:
                url.port
            except ValueError:
                raise ValueError("origin contains an invalid port") from None
        return list(dict.fromkeys(values))

    @classmethod
    def from_env(cls, env_file: str | Path | None = None, *,
                 environ: Mapping[str, str] | None = None) -> ApiSettings:
        path = Path(env_file) if env_file is not None else default_env_file()
        if env_file is not None and not path.is_file():
            raise ConfigurationError("The explicit API environment file does not exist.")
        try:
            file_values = dotenv_values(path, encoding="utf-8-sig", interpolate=False) if path.is_file() else {}
        except (OSError, UnicodeError):
            raise ConfigurationError("Could not read the API environment file as UTF-8.") from None
        values = {**file_values, **(os.environ if environ is None else environ)}
        options = {
            name: values[f"IMAGE_API_{name.upper()}"]
            for name in cls.model_fields if f"IMAGE_API_{name.upper()}" in values
        }
        if "origins" in options:
            options["origins"] = [origin.strip() for origin in str(options["origins"]).split(",") if origin.strip()]
        try:
            return cls.model_validate(options)
        except ValidationError:
            raise ConfigurationError("Invalid IMAGE_API settings; check the documented limits and origins.") from None
