"""Questions, replay query intentions and grouping; no reference answer values."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Case:
    id: str
    group: str
    question: str
    family: str
    replay: str
    scope: str = "model"
    view_keys: tuple[str, ...] = ()
    whole_model: bool = False
    split: str = "development"


CASES = (
    Case("classified-all", "classified", "How many doors are in the entire model?", "door_count", "doors", whole_model=True),
    Case("classified-outside", "classified", "How many fitted doorways lead outside, including the terrace?", "exterior_door_count", "exterior"),
    Case("classified-internal", "classified", "How many doors are explicitly classified as internal?", "property_filter", "internal"),
    Case("classified-finnish", "classified", "Kuinka monta ovea nykyisessä näkymässä on?", "door_count", "doors", "view", ("entry", "internal")),
    Case("topology-doors", "topology", "How many doorways have a recorded direct outdoor connection?", "exterior_door_count", "exterior"),
    Case("topology-rooms", "topology", "How many rooms have direct outdoor access?", "outdoor_room_count", "outdoor-rooms"),
    Case("topology-connected", "topology", "Which rooms are directly connected to R-B through a door?", "door_connectivity", "connections"),
    Case("topology-adjacent", "topology", "Which rooms share a native physical boundary with R-B?", "room_adjacency", "neighbors"),
    Case("missing-all", "missing", "How many doors are modeled?", "door_count", "doors"),
    Case("missing-outside", "missing", "How many doors lead outside?", "exterior_door_count", "exterior"),
    Case("missing-fire-rating", "missing", "Which modeled doors have a recorded fire rating?", "missing_property", "missing-fire-rating"),
    Case("missing-empty-view", "missing", "How many doors are in this empty selected view?", "empty_view_count", "doors", "view"),
    Case("floors-all", "floors", "How many doors are in the entire model?", "door_count", "doors", whole_model=True, split="test"),
    Case("floors-view", "floors", "How many doors are in this view?", "door_count", "doors", "view", ("entry", "internal"), split="test"),
    Case("floors-finnish-outside", "floors", "Kuinka monta ulko-ovea tässä näkymässä on?", "exterior_door_count", "exterior", "view", ("entry", "internal"), split="test"),
    Case("floors-scope-change", "floors", "How many doors are in the entire building?", "scope_clarification", "doors", "view", ("entry", "internal"), True, "test"),
    Case("partial-combined", "partial", "How many doors lead outside, and is that inventory complete?", "exterior_door_count", "exterior", split="test"),
    Case("partial-classification", "partial", "How many doors are marked external in their source classification? Report unclassified doors separately.", "exterior_door_count", "classification", split="test"),
    Case("partial-boundary", "partial", "How many distinct doors have recorded physical external space-boundary links?", "recorded_boundary_count", "boundary", split="test"),
    Case("partial-all", "partial", "How many door occurrences are modeled?", "door_count", "doors", split="test"),
    Case("conflicting-all", "conflicting", "How many door occurrences exist?", "door_count", "doors", split="test"),
    Case("conflicting-outside", "conflicting", "How many doors lead outside? Check conflicting classifications and boundaries.", "conflicting_evidence", "exterior", split="test"),
    Case("conflicting-flags", "conflicting", "How many doors have IsExternal explicitly set to true, ignoring geometric inference?", "property_filter", "external-flags", split="test"),
    Case("conflicting-route", "conflicting", "What is the shortest navigable escape route from R-A to outside?", "unsupported_route", "unsupported-route", split="test"),
)
