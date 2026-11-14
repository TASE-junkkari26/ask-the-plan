"""Errors safe to expose at the internal HTTP boundary."""
from __future__ import annotations

from typing import Any


class ApiError(RuntimeError):
    def __init__(self, status_code: int, code: str, message: str, retryable: bool = False, *,
                 usage: Any = None, returned_model: str | None = None,
                 provider_status_code: int | None = None, provider_code: str | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.retryable = retryable
        self.usage = usage
        self.returned_model = returned_model
        # Private diagnostics only. Public HTTP envelopes deliberately serialize
        # only status/code/message/retryable. Callers supply recognized machine
        # categories, never provider bodies, exception strings or source data.
        self.provider_status_code = provider_status_code
        self.provider_code = provider_code
