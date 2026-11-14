"""Errors safe to expose at the internal HTTP boundary."""
from __future__ import annotations

from typing import Any


class ApiError(RuntimeError):
    def __init__(self, status_code: int, code: str, message: str, retryable: bool = False, *,
                 usage: Any = None, returned_model: str | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.retryable = retryable
        self.usage = usage
        self.returned_model = returned_model
