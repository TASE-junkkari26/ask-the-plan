"""Conservative reconciliation of crop observations in one source-pixel frame.

This tool merges repeat observations, not physical truth. Coordinates are never
averaged, and ambiguous overlapping proposals survive for a later inspection.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import re
import unicodedata
from typing import Sequence


Box = tuple[float, float, float, float]


def _valid_box(box: Box) -> bool:
    return (len(box) == 4 and all(type(v) in {int, float} and math.isfinite(v) for v in box)
            and 0 <= box[0] < box[2] and 0 <= box[1] < box[3])


def _area(box: Box) -> float:
    return (box[2] - box[0]) * (box[3] - box[1])


def _intersection(a: Box, b: Box) -> float:
    return max(0., min(a[2], b[2]) - max(a[0], b[0])) * max(0., min(a[3], b[3]) - max(a[1], b[1]))


def box_iou(a: Box, b: Box) -> float:
    intersection = _intersection(a, b)
    return intersection / (_area(a) + _area(b) - intersection)


@dataclass(frozen=True)
class SourceCandidate:
    observation_id: str
    region_id: str
    category: str
    box: Box
    region_box: Box
    source_label: str | None = None
    uncertain: bool = False
    uncertainty_reason: str | None = None
    visual_cue: str = ""
    source_sha256: str | None = None

    def __post_init__(self):
        if any(not isinstance(value, str) or not value.strip()
               for value in (self.observation_id, self.region_id, self.category)):
            raise ValueError("Observation ID, region ID and category must be nonblank")
        if not _valid_box(self.box) or not _valid_box(self.region_box):
            raise ValueError("Source boxes must be finite, positive source-pixel boxes")
        a, b = self.box, self.region_box
        if a[0] < b[0]-1e-6 or a[1] < b[1]-1e-6 or a[2] > b[2]+1e-6 or a[3] > b[3]+1e-6:
            raise ValueError("Candidate box must lie within its source region")
        if type(self.uncertain) is not bool:
            raise ValueError("Uncertain must be boolean")
        if self.uncertain and (not isinstance(self.uncertainty_reason, str) or not self.uncertainty_reason.strip()):
            raise ValueError("Uncertain observations need an explanation")
        if not self.uncertain and self.uncertainty_reason is not None:
            raise ValueError("Certain observations must have null uncertainty reason")
        if self.source_label is not None and not isinstance(self.source_label, str):
            raise ValueError("Literal source label must be text or null")
        if self.source_sha256 is not None and (not isinstance(self.source_sha256, str)
                or not re.fullmatch(r"[0-9a-f]{64}", self.source_sha256)):
            raise ValueError("Observation source SHA256 must be lowercase hexadecimal")


def _clipped(item: SourceCandidate) -> bool:
    # Two pixels tolerates normalization rounding without swallowing a large
    # fraction of a small symbol. A source-edge observation also needs review.
    return any(abs(a-b) <= 2 for a, b in zip(item.box, item.region_box))


def _center_distance(a: Box, b: Box) -> float:
    # Per-axis normalization keeps a thin adjacent object from merging solely
    # because its long side dominates a Euclidean diagonal.
    dx = abs(a[0]+a[2]-b[0]-b[2]) / (2*max(a[2]-a[0], b[2]-b[0]))
    dy = abs(a[1]+a[3]-b[1]-b[3]) / (2*max(a[3]-a[1], b[3]-b[1]))
    return max(dx, dy)


TARGET_KINDS = frozenset({"door", "window", "toilet", "shower", "bathtub", "bath_fixture",
                          "room", "floor", "schedule_row", "other"})


def _text_key(value: str) -> str:
    """Comparison-only normalization; source labels are never rewritten."""
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def _category_key(value: str, target_kind: str | None = None) -> str:
    key = re.sub(r"[\s-]+", "_", _text_key(value))
    aliases = {
        "toilet_bowl": "toilet", "toilet_fixture": "toilet", "wc_fixture": "toilet",
        "fitted_doorway": "door", "door_instance": "door", "window_assembly": "window",
    }
    key = aliases.get(key, key)
    # Large semantic objects and rows require the caller's declared count grain.
    # A room polygon must not become a schedule row merely because both carry
    # the same room number, and a WC room is distinct from a toilet fixture.
    typed_aliases = {
        "floor": {"floor", "floor_plan", "floorplan", "storey", "storey_plan"},
        "schedule_row": {"schedule_row", "room_schedule_row", "table_row", "row", "room"},
        "room": {"room", "space", "room_space"},
        "toilet": {"toilet", "wc", "toilet_bowl", "toilet_fixture", "wc_fixture"},
        "bath_fixture": {"shower", "bathtub", "bath", "bath_fixture"},
    }
    if key in typed_aliases.get(target_kind, set()):
        return target_kind
    return key


def _same_category(a: SourceCandidate, b: SourceCandidate, target_kind: str | None = None) -> bool:
    return _category_key(a.category, target_kind) == _category_key(b.category, target_kind)


def _row_identifier(value: str | None) -> str | None:
    if value is None:
        return None
    # Conservative leading printed identifier: preserves punctuation/alphabetic
    # suffixes such as 121.A; does not perform O/0 or other OCR substitutions.
    match = re.match(r"^(?:room\s+)?([a-z]?\d+(?:[.\-/][a-z0-9]+)*[a-z]?)(?=\s|$)", _text_key(value))
    return match.group(1) if match else None


def _labels_conflict(a: SourceCandidate, b: SourceCandidate, target_kind: str | None = None) -> bool:
    if a.source_label is None or b.source_label is None:
        return False
    left, right = _text_key(a.source_label), _text_key(b.source_label)
    if left == right or re.sub(r"\s+", "", left) == re.sub(r"\s+", "", right):
        return False
    if target_kind == "schedule_row":
        first, second = _row_identifier(a.source_label), _row_identifier(b.source_label)
        if first is not None and first == second:
            return False
    # Labels on a floor depiction can be an apartment name, elevation or floor
    # title. They are not competing object IDs when geometry establishes that
    # both observations describe the exact same panel.
    if target_kind == "floor" and box_iou(a.box, b.box) >= .85:
        return False
    return True


def _spatial_identity_note(a: SourceCandidate, b: SourceCandidate,
                           target_kind: str | None = None) -> str | None:
    """Recognize a bounded repeat hypothesis without normalizing source IDs.

    A geometric doorway/window observation may have conflicting OCR labels or a
    clipped extent. Those label readings remain literal alternatives, so merging
    this evidence must leave the physical-instance hypothesis uncertain.
    """
    if target_kind not in {"door", "window"} or not _same_category(a, b, target_kind):
        return None
    if a.source_label is None or b.source_label is None:
        return None
    first = re.sub(r"\s+", "", _text_key(a.source_label))
    second = re.sub(r"\s+", "", _text_key(b.source_label))
    if not first or not second:
        return None
    if (first != second and len(first) == len(second)
            and all(x == y or {x, y} == {"o", "0"} for x, y in zip(first, second))
            and box_iou(a.box, b.box) >= .9 and _center_distance(a.box, b.box) <= .1):
        return (f"Near-identical {target_kind} observations have conflicting literal label readings "
                f"{a.source_label!r} and {b.source_label!r} (O/0 ambiguity); retained one uncertain source-instance hypothesis.")
    if (first == second and (_clipped(a) or _clipped(b))
            and box_iou(a.box, b.box) >= .35 and _center_distance(a.box, b.box) <= .4):
        return (f"Clipped and complete {target_kind} observations share literal label "
                f"{a.source_label!r} and corroborating geometry; retained one uncertain source-instance hypothesis.")
    return None


def _duplicate(a: SourceCandidate, b: SourceCandidate, target_kind: str | None = None) -> bool:
    if a.region_id == b.region_id or not _same_category(a, b, target_kind):
        return False
    overlap = _intersection(a.box, b.box)
    if not overlap or not _intersection(a.region_box, b.region_box):
        return False
    if _spatial_identity_note(a, b, target_kind) is not None:
        return True
    if _labels_conflict(a, b, target_kind):
        return False
    distance = _center_distance(a.box, b.box)
    if box_iou(a.box, b.box) >= .55 and distance <= .3:
        return True
    if target_kind == "schedule_row":
        first, second = _row_identifier(a.source_label), _row_identifier(b.source_label)
        # A stable row ID anchors repeated table observations despite vertical
        # box jitter. Spatial evidence still prevents equal IDs in distant
        # panels/rows from merging.
        if first is not None and first == second and box_iou(a.box, b.box) >= .2 and distance <= .75:
            return True
    compact = {"door", "window", "toilet", "shower", "bathtub", "bath_fixture"}
    if _category_key(a.category, target_kind) in compact:
        # Fixture proposals often alternate between the bowl/leaf and complete
        # symbol extent. A centered, bounded containment is repeat evidence;
        # adjacent objects and broad room/panel boxes do not meet this rule.
        if (overlap/min(_area(a.box), _area(b.box)) >= .88 and distance <= .3
                and max(_area(a.box), _area(b.box))/min(_area(a.box), _area(b.box)) <= 4):
            return True
        if (target_kind in {"toilet", "shower", "bathtub", "bath_fixture"}
                and a.source_label is None and b.source_label is None
                and box_iou(a.box, b.box) >= .45 and distance <= .3):
            return True
    # A truncated observation may be only a small subset of a full view. Require
    # most of the smaller box, a close center, and actual crop-edge truncation.
    smaller, larger = (a, b) if _area(a.box) <= _area(b.box) else (b, a)
    return (_clipped(smaller) and not _clipped(larger)
            and overlap / _area(smaller.box) >= .85 and distance <= .45)


def _disputed(a: SourceCandidate, b: SourceCandidate, target_kind: str | None = None) -> bool:
    overlap = _intersection(a.box, b.box)
    if not overlap:
        return False
    if not _same_category(a, b, target_kind):
        return box_iou(a.box, b.box) >= .7
    return (box_iou(a.box, b.box) >= .2 and _center_distance(a.box, b.box) <= .65
            or overlap / min(_area(a.box), _area(b.box)) >= .75)


@dataclass(frozen=True)
class MergeRecord:
    selected_observation_id: str
    absorbed_observation_id: str
    reason: str
    iou: float
    absorbed_uncertain: bool
    absorbed_uncertainty_reason: str | None

    def to_dict(self) -> dict:
        return {name: getattr(self, name) for name in self.__dataclass_fields__}


@dataclass(frozen=True)
class ReconciledCandidate:
    candidate: SourceCandidate
    observation_ids: tuple[str, ...]
    clipped: bool
    uncertain: bool
    uncertainty_reason: str | None

    def to_dict(self, candidate_id: str | None = None) -> dict:
        c = self.candidate
        return {"id": candidate_id or c.observation_id, "category": c.category,
                "source_label": c.source_label,
                "geometry": {"kind": "box", "minimum": list(c.box[:2]), "maximum": list(c.box[2:])},
                "uncertain": self.uncertain, "uncertainty_reason": self.uncertainty_reason,
                "visual_cue": c.visual_cue,
                "provenance": {"selected_observation_id": c.observation_id,
                               "observation_ids": list(self.observation_ids), "region_id": c.region_id,
                               "region_box": list(c.region_box), "clipped": self.clipped}}


@dataclass(frozen=True)
class ReconciliationResult:
    source_sha256: str
    source_width: int
    source_height: int
    candidates: tuple[ReconciledCandidate, ...]
    merges: tuple[MergeRecord, ...]
    issues: tuple[str, ...]
    status: str
    inventory_completeness: str = "unverified"

    def to_dict(self) -> dict:
        return {"source_sha256": self.source_sha256, "source_width": self.source_width,
                "source_height": self.source_height, "status": self.status,
                "inventory_completeness": self.inventory_completeness,
                "candidates": [c.to_dict(f"candidate-{i:03d}") for i, c in enumerate(self.candidates, 1)],
                "merges": [m.to_dict() for m in self.merges], "issues": list(self.issues)}


def reconcile_candidates(observations: Sequence[SourceCandidate], *, source_sha256: str,
                         source_width: int, source_height: int,
                         target_kind: str | None = None) -> ReconciliationResult:
    """Conservatively merge crop repeats; retain ambiguous alternatives as partial.

    The caller must bind every observation to this one source hash/frame before
    calling. This pure function neither reads images nor verifies source truth.
    """
    if not isinstance(source_sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", source_sha256):
        raise ValueError("A lowercase source SHA256 is required")
    if target_kind is not None and target_kind not in TARGET_KINDS:
        raise ValueError("Unknown reconciliation target kind")
    if (type(source_width) is not int or type(source_height) is not int
            or source_width <= 0 or source_height <= 0):
        raise ValueError("Source dimensions must be positive integers")
    if len(observations) > 3200:
        raise ValueError("At most 3200 observations can be reconciled")
    if any(not isinstance(c, SourceCandidate) for c in observations):
        raise ValueError("Expected source candidate observations")
    if len({c.observation_id for c in observations}) != len(observations):
        raise ValueError("Observation IDs must be unique")
    for c in observations:
        if c.source_sha256 is not None and c.source_sha256 != source_sha256:
            raise ValueError("Observation belongs to a different source SHA256")
        if c.region_box[2] > source_width or c.region_box[3] > source_height:
            raise ValueError("Observation region lies outside this source frame")
    region_boxes: dict[str, Box] = {}
    for c in observations:
        if c.region_id in region_boxes and region_boxes[c.region_id] != c.region_box:
            raise ValueError("One region ID cannot identify different source regions")
        region_boxes[c.region_id] = c.region_box
    # Full, certain observations are preferred; ties are deterministic and never
    # depend on which concurrent provider call finished first.
    ordered = sorted(observations, key=lambda c: (_clipped(c), c.uncertain, _area(c.region_box), c.observation_id))
    groups: list[list[SourceCandidate]] = []
    ambiguous_assignments: dict[str, list[str]] = {}
    for candidate in ordered:
        # Each group has a fixed preferred source observation as its anchor.
        # Matching only that anchor prevents a chain of drifting boxes from
        # walking across separate instances, while letting different partial
        # extents share a centered, complete symbol. One crop cannot contribute
        # two independent detections to the same group.
        compatible = [group for group in groups
                      if not any(candidate.region_id == member.region_id for member in group)
                      and _duplicate(candidate, group[0], target_kind)]
        if len(compatible) == 1:
            compatible[0].append(candidate)
        elif compatible:
            # An observation that fits two existing source instances is an
            # ambiguous assignment, not evidence for a third instance. Preserve
            # its provenance with the best fixed anchor and flag all alternatives.
            selected = max(compatible, key=lambda group: (box_iou(candidate.box, group[0].box),
                           -_center_distance(candidate.box, group[0].box), group[0].observation_id))
            message = f"Observation {candidate.observation_id} has ambiguous membership among existing source instances."
            for group in compatible:
                ambiguous_assignments.setdefault(group[0].observation_id, []).append(message)
            selected.append(candidate)
        else:
            groups.append([candidate])
    issues: list[str] = list(dict.fromkeys(message for messages in ambiguous_assignments.values() for message in messages))
    disputed: dict[str, list[str]] = {}
    for i, group in enumerate(groups):
        for other in groups[i+1:]:
            a, b = group[0], other[0]
            if any(_disputed(x, y, target_kind) for x in group for y in other):
                message = f"Overlapping observations {a.observation_id} and {b.observation_id} require instance review."
                issues.append(message)
                disputed.setdefault(a.observation_id, []).append(message)
                disputed.setdefault(b.observation_id, []).append(message)
    merged: list[MergeRecord] = []
    survivors: list[ReconciledCandidate] = []
    for group in groups:
        selected = group[0]
        reasons = []
        if selected.uncertain:
            reasons.append(selected.uncertainty_reason)
        if _clipped(selected):
            message = f"Observation {selected.observation_id} reaches its crop boundary; inspect a recentered region."
            issues.append(message)
            reasons.append(message)
        reasons.extend(disputed.get(selected.observation_id, []))
        reasons.extend(ambiguous_assignments.get(selected.observation_id, []))
        reasons.extend(note for member in group[1:]
                       if (note := _spatial_identity_note(selected, member, target_kind)) is not None)
        survivors.append(ReconciledCandidate(selected, tuple(c.observation_id for c in group),
                                            _clipped(selected), bool(reasons), " ".join(reasons) if reasons else None))
        for absorbed in group[1:]:
            merged.append(MergeRecord(selected.observation_id, absorbed.observation_id,
                                      _spatial_identity_note(selected, absorbed, target_kind)
                                      or "Repeated cross-region observation; retained preferred original geometry.",
                                      box_iou(selected.box, absorbed.box), absorbed.uncertain, absorbed.uncertainty_reason))
    survivors.sort(key=lambda c: (c.candidate.box[1], c.candidate.box[0], c.candidate.observation_id))
    return ReconciliationResult(source_sha256, source_width, source_height, tuple(survivors),
                                tuple(merged), tuple(issues),
                                "partial" if issues or any(c.uncertain for c in survivors) else "ok")


@dataclass(frozen=True)
class ReinspectionRegion:
    id: str
    source_box: tuple[int, int, int, int]
    observation_ids: tuple[str, ...]
    reason: str

    def to_dict(self) -> dict:
        return {"id": self.id, "source_box": list(self.source_box),
                "observation_ids": list(self.observation_ids), "reason": self.reason}


@dataclass(frozen=True)
class ReinspectionPlan:
    source_sha256: str
    regions: tuple[ReinspectionRegion, ...]
    deferred_observation_ids: tuple[str, ...]


@dataclass(frozen=True)
class ReinspectionReplacement:
    superseded_observation_id: str
    fresh_observation_id: str
    iou: float
    reason: str = "Clipped observation replaced by corroborating, nonclipped fresh inspection."


@dataclass(frozen=True)
class ReinspectionApplication:
    observations: tuple[SourceCandidate, ...]
    superseded_ids: tuple[str, ...]
    replacements: tuple[ReinspectionReplacement, ...]
    result: ReconciliationResult


def partition_tile_observations(observations: Sequence[SourceCandidate],
                                regions: dict[str, Box]) -> tuple[tuple[SourceCandidate, ...], tuple[SourceCandidate, ...]]:
    """Partition crop-edge fragments by deterministic successful-tile ownership.

    ``regions`` must contain only native tiles whose detection call succeeded.
    At each candidate center, the containing tile with the greatest minimum
    distance to its edges owns that point. This splits equal-size overlap bands
    at their midpoint. An observation's own tile wins ties. Nonclipped proposals
    always survive; deferred fragments are returned intact, not disproven.
    """
    if not isinstance(regions, dict) or any(not isinstance(key, str) or not key.strip()
            or not _valid_box(box) for key, box in regions.items()):
        raise ValueError("Successful regions need nonblank IDs and valid source-pixel boxes")
    if any(not isinstance(c, SourceCandidate) for c in observations):
        raise ValueError("Expected source candidate observations")
    if len({c.observation_id for c in observations}) != len(observations):
        raise ValueError("Observation IDs must be unique")
    kept, deferred = [], []
    for item in observations:
        own = regions.get(item.region_id)
        if own is not None and tuple(own) != tuple(item.region_box):
            raise ValueError("Region ID does not match the observation source frame")
        if own is None or not _clipped(item):
            kept.append(item)
            continue
        x, y = (item.box[0]+item.box[2])/2, (item.box[1]+item.box[3])/2
        own_margin = min(x-own[0], y-own[1], own[2]-x, own[3]-y)
        deeper_successful_owner = any(
            region_id != item.region_id and box[0] <= x <= box[2] and box[1] <= y <= box[3]
            and min(x-box[0], y-box[1], box[2]-x, box[3]-y) > own_margin+1e-6
            for region_id, box in regions.items())
        (deferred if deeper_successful_owner else kept).append(item)
    return tuple(kept), tuple(deferred)


def apply_reinspection(observations: Sequence[SourceCandidate], fresh_observations: Sequence[SourceCandidate], *,
                       source_sha256: str, source_width: int, source_height: int,
                       reviewed_box: Box, target_kind: str | None = None) -> ReinspectionApplication:
    """Replace only corroborated old crop-edge fragments after a fresh inspection.

    Empty or uncertain new detections cannot delete an old observation. Full old
    detections survive and are reconciled with the fresh ones normally. A caller
    must retain these returned replacement records with its inference provenance.
    """
    if not _valid_box(reviewed_box) or reviewed_box[2] > source_width or reviewed_box[3] > source_height:
        raise ValueError("Reviewed crop must lie within the source frame")
    # Validate all identity, frame and ID constraints even when no replacement
    # can be made. A failed/empty inference is not evidence for physical absence.
    combined = tuple(observations) + tuple(fresh_observations)
    reconcile_candidates(combined, source_sha256=source_sha256,
                         source_width=source_width, source_height=source_height, target_kind=target_kind)
    for fresh in fresh_observations:
        if tuple(fresh.region_box) != tuple(reviewed_box):
            raise ValueError("Fresh observations must use the reviewed crop frame")
    replacements = []
    for old in observations:
        if not _clipped(old) or not (reviewed_box[0] <= old.box[0] and reviewed_box[1] <= old.box[1]
                                    and reviewed_box[2] >= old.box[2] and reviewed_box[3] >= old.box[3]):
            continue
        compatible = [fresh for fresh in fresh_observations if not _clipped(fresh) and not fresh.uncertain
                      and _same_category(old, fresh, target_kind) and not _labels_conflict(old, fresh, target_kind)
                      and box_iou(old.box, fresh.box) >= .35 and _center_distance(old.box, fresh.box) <= .35]
        if compatible:
            fresh = max(compatible, key=lambda c: (box_iou(old.box, c.box), c.observation_id))
            replacements.append(ReinspectionReplacement(old.observation_id, fresh.observation_id,
                                                       box_iou(old.box, fresh.box)))
    superseded_ids = tuple(sorted(r.superseded_observation_id for r in replacements))
    superseded = set(superseded_ids)
    retained = tuple(c for c in observations if c.observation_id not in superseded) + tuple(fresh_observations)
    result = reconcile_candidates(retained, source_sha256=source_sha256,
                                  source_width=source_width, source_height=source_height, target_kind=target_kind)
    return ReinspectionApplication(retained, superseded_ids, tuple(replacements), result)


def propose_reinspection_regions(result: ReconciliationResult, *, minimum_side: int = 384,
                                  max_side: int = 1280, max_regions: int = 8) -> ReinspectionPlan:
    """Propose native-detail context crops for a caller's bounded inspection loop.

    These are inspection requests, not inferred objects or completed repairs.
    Callers retain the raw observations until a new result supports resolution.
    """
    if not all(type(v) is int for v in (minimum_side, max_side, max_regions)) or not (
            32 <= minimum_side <= max_side <= 4096 and 1 <= max_regions <= 32):
        raise ValueError("Inspection size and region budgets are invalid")
    proposals: list[tuple[tuple[int, int, int, int], set[str]]] = []
    pending = sorted((c for c in result.candidates if c.uncertain or c.clipped),
                     key=lambda c: (not c.clipped, c.candidate.observation_id))
    for item in pending:
        box = item.candidate.box
        width = min(result.source_width, max_side, max(minimum_side, math.ceil(3*(box[2]-box[0]))))
        height = min(result.source_height, max_side, max(minimum_side, math.ceil(3*(box[3]-box[1]))))
        left = max(0, min(result.source_width-width, math.floor((box[0]+box[2]-width)/2)))
        top = max(0, min(result.source_height-height, math.floor((box[1]+box[3]-height)/2)))
        crop = (left, top, left+width, top+height)
        # Merge nearby inspection requests only if their union remains bounded.
        for i, (existing, ids) in enumerate(proposals):
            union = (min(crop[0], existing[0]), min(crop[1], existing[1]),
                     max(crop[2], existing[2]), max(crop[3], existing[3]))
            if box_iou(crop, existing) >= .1 and union[2]-union[0] <= max_side and union[3]-union[1] <= max_side:
                proposals[i] = (union, ids | set(item.observation_ids))
                break
        else:
            proposals.append((crop, set(item.observation_ids)))
    regions = tuple(ReinspectionRegion(
        f"reinspect-{i:03d}", crop, tuple(sorted(ids)),
        "Inspect native context to resolve a clipped or disputed observation; retain source scope.")
        for i, (crop, ids) in enumerate(proposals[:max_regions], 1))
    deferred = tuple(sorted({identifier for _, ids in proposals[max_regions:] for identifier in ids}))
    return ReinspectionPlan(result.source_sha256, regions, deferred)
