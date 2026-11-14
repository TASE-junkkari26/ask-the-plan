"""Evaluator-only expected outcomes; imported after predictions have been saved."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Reference:
    status: str
    count: int | None = None
    included: tuple[str, ...] | None = None
    related: tuple[str, ...] | None = None
    quality: str | None = None
    anchor_keys: tuple[str, ...] = ()


REFERENCES = {
    "classified-all": Reference("answered", 4, ("entry", "patio", "internal", "service")),
    "classified-outside": Reference("answered", 2, ("entry", "patio")),
    "classified-internal": Reference("answered", 2, ("internal", "service")),
    "classified-finnish": Reference("answered", 2, ("entry", "internal")),
    "topology-doors": Reference("answered", 2, ("entry", "patio"), anchor_keys=("entry-boundary", "entry-duplicate", "patio-boundary", "patio-fill")),
    "topology-rooms": Reference("answered", 2, ("room-a", "room-b"), anchor_keys=("entry-boundary", "patio-boundary", "patio-fill")),
    "topology-connected": Reference("answered", related=("room-c",), anchor_keys=("internal-b", "internal-c")),
    "topology-adjacent": Reference("answered", related=("room-c",), anchor_keys=("internal-b", "internal-c")),
    "missing-all": Reference("answered", 3, ("entry", "internal", "service")),
    "missing-outside": Reference("missing_information"),
    "missing-fire-rating": Reference("missing_information"),
    "missing-empty-view": Reference("answered", 0, ()),
    "floors-all": Reference("answered", 5, ("entry", "internal", "upper-entry", "upper-internal", "upper-service")),
    "floors-view": Reference("answered", 2, ("entry", "internal")),
    "floors-finnish-outside": Reference("answered", 1, ("entry",)),
    "floors-scope-change": Reference("needs_clarification"),
    "partial-combined": Reference("partial", 1, ("entry",), quality="lower_bound"),
    "partial-classification": Reference("partial", 1, ("entry",), quality="lower_bound"),
    "partial-boundary": Reference("answered", 1, ("entry",), anchor_keys=("entry-boundary",)),
    "partial-all": Reference("answered", 3, ("entry", "internal", "unknown")),
    "conflicting-all": Reference("answered", 3, ("entry", "patio", "internal")),
    "conflicting-outside": Reference("conflicting_evidence"),
    "conflicting-flags": Reference("answered", 1, ("patio",)),
    "conflicting-route": Reference("unsupported_operation"),
}
