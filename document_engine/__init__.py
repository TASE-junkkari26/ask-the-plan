"""Bounded, source-bound native document tools; no QA or model inference."""

from .store import DocumentError, DocumentSession, DocumentStore
from .pdf import NativePage, NativeSpan, extract_pdf

__all__ = ["DocumentError", "DocumentSession", "DocumentStore", "NativePage", "NativeSpan", "extract_pdf"]
