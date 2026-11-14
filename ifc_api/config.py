"""Independent IFC planner selection and bounded request budgets."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Literal, Mapping

from dotenv import dotenv_values
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from nemotron.config import ConfigurationError, default_env_file


class IfcSettings(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", hide_input_in_errors=True)

    provider: Literal["nemotron", "gemini"] = "nemotron"
    gemini_thinking_level: Literal["low", "medium", "high", "xhigh"] = "high"
    gemini_max_output_tokens: int = Field(default=65536, gt=0, le=65536)
    max_tokens: int = Field(default=6000, gt=0, le=65536)
    deadline_seconds: float = Field(default=180, gt=0, le=600, allow_inf_nan=False)
    max_model_requests: int = Field(default=3, ge=1, le=3)
    max_inspections: int = Field(default=6, ge=0, le=6)

    @classmethod
    def from_env(cls, env_file: str | Path | None = None, *,
                 environ: Mapping[str, str] | None = None) -> IfcSettings:
        path = Path(env_file) if env_file is not None else default_env_file()
        if env_file is not None and not path.is_file():
            raise ConfigurationError("The explicit IFC settings file does not exist.")
        try:
            file_values = dotenv_values(path, encoding="utf-8-sig", interpolate=False) if path.is_file() else {}
        except (OSError, UnicodeError):
            raise ConfigurationError("Could not read the IFC settings file as UTF-8.") from None
        values = {**file_values, **(os.environ if environ is None else environ)}
        names = {
            "provider": "IFC_API_PROVIDER",
            "gemini_thinking_level": "IFC_GEMINI_THINKING_LEVEL",
            "gemini_max_output_tokens": "IFC_GEMINI_MAX_OUTPUT_TOKENS",
            "max_tokens": "IFC_API_MAX_TOKENS",
            "deadline_seconds": "IFC_API_DEADLINE_SECONDS",
            "max_model_requests": "IFC_API_MAX_MODEL_REQUESTS",
            "max_inspections": "IFC_API_MAX_INSPECTIONS",
        }
        options = {name: values[variable] for name, variable in names.items() if variable in values}
        try:
            return cls.model_validate(options)
        except ValidationError:
            raise ConfigurationError("Invalid IFC planner settings; check .env.example for supported values.") from None
