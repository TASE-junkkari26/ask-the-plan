"""Cross-record validation for the contracts, not a quantity executor.

These checks resolve typed references and enforce conservative scope/coverage
rules. They do not verify source truth, external member files/meshes, numerical
geometry measurements, or extraction completeness. Polygon topology checks are
limited to simple planar 2D rings; 3D mesh/face topology belongs to the extractor.
"""
from __future__ import annotations

from collections import defaultdict
from decimal import Decimal, localcontext
import re
from typing import Any, Iterable

from .models import CapabilityManifest, KnowledgeBundle, QueryPlan, QueryResult

LENGTH = (1, 0, 0, 0, 0, 0, 0)
DIMENSIONS = {
    "length": LENGTH, "distance": LENGTH, "perimeter": LENGTH,
    "area": (2, 0, 0, 0, 0, 0, 0), "union_area": (2, 0, 0, 0, 0, 0, 0),
    "volume": (3, 0, 0, 0, 0, 0, 0), "mass": (0, 1, 0, 0, 0, 0, 0),
    "time": (0, 0, 1, 0, 0, 0, 0), "temperature": (0, 0, 0, 0, 1, 0, 0),
    "angle": (0, 0, 0, 0, 0, 0, 0), "ratio": (0, 0, 0, 0, 0, 0, 0),
}
TABLES = (
    "projects", "documents", "assets", "runs", "concepts", "properties", "units",
    "frames", "transforms", "views", "geometries", "anchors", "calibrations",
    "features", "entities", "representations", "facts", "relations", "coverage", "space_boundaries",
)


def _fail(message: str) -> None:
    raise ValueError(message)


def _index(items: Iterable[Any], label: str, key: str = "id") -> dict[str, Any]:
    result = {}
    for item in items:
        identifier = getattr(item, key)
        if identifier in result:
            _fail(f"duplicate {label} ID: {identifier}")
        result[identifier] = item
    return result


def _get(index: dict[str, Any], identifier: str, label: str) -> Any:
    if identifier not in index:
        _fail(f"unknown {label}: {identifier}")
    return index[identifier]


def _refs(index: dict[str, Any], identifiers: Iterable[str], label: str) -> None:
    for identifier in identifiers:
        _get(index, identifier, label)


class _Context:
    def __init__(self, bundle: KnowledgeBundle):
        for name in TABLES:
            setattr(self, name, _index(getattr(bundle, name), name,
                                      "key" if name == "properties" else "id"))
        self.children: dict[str, set[str]] = defaultdict(set)
        self.parts: dict[str, set[str]] = defaultdict(set)
        self.asset_neighbors: dict[str, set[str]] = defaultdict(set)
        for relation in bundle.relations:
            if relation.predicate in {"contains", "aggregates"}:
                self.children[relation.subject_id].add(relation.object_id)
            if relation.predicate == "aggregates":
                self.parts[relation.subject_id].add(relation.object_id)
        for link in bundle.asset_links:
            self.asset_neighbors[link.source_asset_id].add(link.target_asset_id)
            self.asset_neighbors[link.target_asset_id].add(link.source_asset_id)

    def provenance(self, value: Any) -> None:
        _get(self.runs, value.run_id, "extraction run")
        _refs(self.anchors, value.anchor_ids, "evidence anchor")


def _reachable(graph: dict[str, set[str]], roots: Iterable[str]) -> set[str]:
    found, pending = set(), list(roots)
    while pending:
        current = pending.pop()
        if current in found:
            continue
        found.add(current)
        pending.extend(graph.get(current, ()))
    return found


def _acyclic(graph: dict[str, set[str]], label: str) -> None:
    # Iterative DFS avoids recursion failures on large model hierarchies.
    done, active = set(), set()
    for root in set(graph) | {n for children in graph.values() for n in children}:
        if root in done:
            continue
        stack = [(root, False)]
        while stack:
            node, leaving = stack.pop()
            if leaving:
                active.remove(node)
                done.add(node)
            elif node not in done:
                if node in active:
                    _fail(f"cycle in {label}: {node}")
                active.add(node)
                stack.append((node, True))
                stack.extend((child, False) for child in graph.get(node, ()))


def _scope(scope: Any, ctx: _Context) -> None:
    _get(ctx.projects, scope.project_id, "scope project")
    _refs(ctx.documents, scope.document_ids, "scope document")
    if len(set(scope.document_ids)) != len(scope.document_ids):
        _fail("scope has duplicate document IDs")
    for document_id in scope.document_ids:
        if ctx.documents[document_id].project_id != scope.project_id:
            _fail("scope document belongs to another project")
    exact = scope.exact_entity_ids
    if exact is not None and len(set(exact)) != len(exact):
        _fail("scope has duplicate exact entity IDs")
    for entity_id in [*scope.entity_ids, *(exact or [])]:
        entity = _get(ctx.entities, entity_id, "scope entity")
        if entity.project_id != scope.project_id or entity.document_id not in scope.document_ids:
            _fail("scope entity is outside the selected project/revisions")
    for view_id in scope.view_ids:
        view = _get(ctx.views, view_id, "scope view")
        if ctx.assets[view.asset_id].document_id not in scope.document_ids:
            _fail("scope view is outside the selected revisions")


def _scope_key(scope: Any) -> tuple:
    return (scope.project_id, frozenset(scope.document_ids), frozenset(scope.entity_ids),
            frozenset(scope.view_ids), scope.universe,
            None if scope.exact_entity_ids is None else frozenset(scope.exact_entity_ids))


def _scope_members(scope: Any, ctx: _Context) -> set[str]:
    members = {e.id for e in ctx.entities.values()
               if e.project_id == scope.project_id and e.document_id in scope.document_ids}
    if scope.entity_ids:
        members &= _reachable(ctx.children, scope.entity_ids)
    if scope.exact_entity_ids is not None:
        members &= set(scope.exact_entity_ids)
    if scope.view_ids:
        # View restrictions mean depicted entities, not every object in the model.
        visible = {r.entity_id for r in ctx.representations.values()
                   if r.view_id in scope.view_ids}
        for view_id in scope.view_ids:
            visible.update(ctx.views[view_id].depicts_entity_ids)
        members &= visible
    return members


def _points(shape: Any) -> Iterable[list[float]]:
    if shape.kind == "point":
        yield shape.coordinates
    elif shape.kind == "polyline":
        yield from shape.coordinates
    elif shape.kind == "box":
        yield shape.minimum
        yield shape.maximum
    elif shape.kind == "multipolygon":
        for part in shape.polygons:
            yield from part.shell
            for hole in part.holes:
                yield from hole


def _cross(a: list[float], b: list[float], c: list[float]) -> float:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _on_segment(a: list[float], b: list[float], p: list[float]) -> bool:
    return abs(_cross(a, b, p)) < 1e-10 and all(
        min(a[i], b[i]) - 1e-10 <= p[i] <= max(a[i], b[i]) + 1e-10 for i in (0, 1))


def _intersects(a: list[float], b: list[float], c: list[float], d: list[float]) -> bool:
    ab_c, ab_d, cd_a, cd_b = _cross(a, b, c), _cross(a, b, d), _cross(c, d, a), _cross(c, d, b)
    return ((ab_c * ab_d < 0 and cd_a * cd_b < 0)
            or _on_segment(a, b, c) or _on_segment(a, b, d)
            or _on_segment(c, d, a) or _on_segment(c, d, b))


def _inside(point: list[float], ring: list[list[float]]) -> bool:
    inside = False
    for a, b in zip(ring, ring[1:]):
        if _on_segment(a, b, point):
            return False  # Holes touching a shell are rejected conservatively.
        if (a[1] > point[1]) != (b[1] > point[1]):
            x = a[0] + (point[1] - a[1]) * (b[0] - a[0]) / (b[1] - a[1])
            if point[0] < x:
                inside = not inside
    return inside


def _ring(ring: list[list[float]]) -> None:
    area2 = sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(ring, ring[1:]))
    if abs(area2) < 1e-12:
        _fail("polygon ring has zero planar area")
    edges = list(zip(ring, ring[1:]))
    for i, (a, b) in enumerate(edges):
        if a == b:
            _fail("polygon ring has a zero-length edge")
        for j in range(i + 1, len(edges)):
            if j == i + 1 or (i == 0 and j == len(edges) - 1):
                continue
            if _intersects(a, b, *edges[j]):
                _fail("polygon ring self-intersects")


def _rings_intersect(a: list[list[float]], b: list[list[float]]) -> bool:
    return any(_intersects(x, y, u, v)
               for x, y in zip(a, a[1:]) for u, v in zip(b, b[1:]))


def _geometry(geometry: Any, ctx: _Context) -> None:
    frame = _get(ctx.frames, geometry.frame_id, "geometry frame")
    if any(len(point) != frame.dimension for point in _points(geometry.shape)):
        _fail("geometry coordinates disagree with frame dimension")
    if geometry.shape.kind == "mesh" and frame.dimension != 3:
        _fail("mesh requires a 3D frame")
    if geometry.shape.kind == "multipolygon" and frame.dimension == 2:
        for part in geometry.shape.polygons:
            _ring(part.shell)
            for i, hole in enumerate(part.holes):
                _ring(hole)
                if not all(_inside(p, part.shell) for p in hole[:-1]) or _rings_intersect(hole, part.shell):
                    _fail("polygon hole must lie strictly inside its shell")
                for other in part.holes[:i]:
                    if (_rings_intersect(hole, other) or _inside(hole[0], other)
                            or _inside(other[0], hole)):
                        _fail("polygon holes overlap or contain one another")


def _matrix_rank(matrix: list[list[float]]) -> int:
    rows = [list(row) for row in matrix]
    pivot_row = 0
    for column in range(len(rows[0])):
        if pivot_row == len(rows):
            break
        selected = max(range(pivot_row, len(rows)), key=lambda r: abs(rows[r][column]))
        pivot = rows[selected][column]
        if pivot == 0:
            continue
        rows[pivot_row], rows[selected] = rows[selected], rows[pivot_row]
        for r in range(pivot_row + 1, len(rows)):
            ratio = rows[r][column] / pivot
            for c in range(column, len(rows[0])):
                rows[r][c] -= ratio * rows[pivot_row][c]
        pivot_row += 1
    return pivot_row


def _quantity(value: Any, ctx: _Context, expected_dimension: Any = None,
              expected_kind: str | None = None) -> None:
    _refs(ctx.anchors, value.unit_anchor_ids, "quantity unit evidence")
    if expected_kind is not None and value.quantity_kind != expected_kind:
        _fail("quantity kind disagrees with property definition")
    if value.unit_id is None:
        return
    unit = _get(ctx.units, value.unit_id, "quantity unit")
    if unit.kind != "physical":
        _fail("building quantities cannot use presentation units")
    dimension = expected_dimension or DIMENSIONS.get(value.quantity_kind)
    if dimension is not None and tuple(unit.dimension) != tuple(dimension):
        _fail("quantity unit dimension is incompatible with its meaning")
    if value.unit_resolution in {"project_default", "calibrated"} and not value.unit_anchor_ids:
        _fail("project-default/calibrated units require unit assignment evidence")
    if value.normalized:
        target = _get(ctx.units, value.normalized.unit_id, "normalized unit")
        if target.kind != "physical" or target.dimension != unit.dimension:
            _fail("normalized quantity has incompatible dimensions")
        # Do not silently round long valid decimal strings at Decimal's default
        # 28-digit context. Normalized values are exact conversion values here.
        parts = [value.magnitude, unit.si_multiplier, unit.si_offset,
                 target.si_offset, target.si_multiplier, value.normalized.magnitude]
        with localcontext() as decimal_context:
            decimal_context.prec = max(64, sum(len(p) for p in parts) + 32)
            actual = (Decimal(value.magnitude) * Decimal(unit.si_multiplier) + Decimal(unit.si_offset)
                      - Decimal(target.si_offset)) / Decimal(target.si_multiplier)
        if actual != Decimal(value.normalized.magnitude):
            _fail("normalized quantity does not match the declared unit conversion")


def _values(value: Any) -> Iterable[Any]:
    yield value
    if value.kind == "list":
        for item in value.items:
            yield from _values(item)
    elif value.kind == "record":
        for item in value.fields.values():
            yield from _values(item)
    elif value.kind == "table":
        for row in value.rows:
            for item in row.values():
                yield from _values(item)


def _value(value: Any, ctx: _Context, definition: Any = None) -> None:
    if definition is not None and value.kind != definition.value_kind:
        _fail("fact value kind disagrees with property definition")
    for item in _values(value):
        if item.kind == "quantity":
            _quantity(item, ctx, definition.dimension if definition and item is value else None,
                      definition.quantity_kind if definition and item is value else None)
        elif item.kind == "references":
            _refs(ctx.entities, item.entity_ids, "value entity")


def validate_bundle(bundle: KnowledgeBundle) -> None:
    """Validate resolved references, units, geometry frames, and hierarchies."""
    ctx = _Context(bundle)
    revisions = set()
    supersession, parents, view_parents = defaultdict(set), defaultdict(set), defaultdict(set)
    for document in bundle.documents:
        _get(ctx.projects, document.project_id, "document project")
        revision_key = (document.project_id, document.logical_key, document.revision)
        if revision_key in revisions:
            _fail("duplicate logical document revision")
        revisions.add(revision_key)
        if document.supersedes_document_id:
            prior = _get(ctx.documents, document.supersedes_document_id, "superseded document")
            if (prior.project_id, prior.logical_key) != (document.project_id, document.logical_key):
                _fail("supersession must stay within one project/logical document")
            supersession[document.id].add(prior.id)
    _acyclic(supersession, "document supersession")
    for asset in bundle.assets:
        _get(ctx.documents, asset.document_id, "asset document")
    for run in bundle.runs:
        _refs(ctx.assets, run.input_asset_ids, "run input asset")
    for link in bundle.asset_links:
        a = _get(ctx.assets, link.source_asset_id, "linked source asset")
        b = _get(ctx.assets, link.target_asset_id, "linked target asset")
        if a.id == b.id:
            _fail("asset links cannot link an asset to itself")
        if link.kind == "byte_duplicate" and a.sha256 != b.sha256:
            _fail("byte duplicate assets must have identical hashes")
        if link.kind == "equivalent_representation" and a.document_id != b.document_id:
            _fail("equivalent representations must belong to the same document revision")
        ctx.provenance(link.provenance)
    for concept in bundle.concepts:
        _refs(ctx.concepts, concept.parent_ids, "parent concept")
        parents[concept.id].update(concept.parent_ids)
    _acyclic(parents, "concept hierarchy")
    for frame in bundle.frames:
        _get(ctx.assets, frame.asset_id, "frame asset")
        if frame.unit_id is None:
            if frame.space == "physical":
                _fail("physical coordinate frames require explicit length units")
        else:
            unit = _get(ctx.units, frame.unit_id, "frame unit")
            if frame.space != unit.kind:
                _fail("frame space and unit kind disagree")
            if frame.space == "physical" and unit.dimension != LENGTH:
                _fail("physical frame coordinates require length units")
    for geometry in bundle.geometries:
        _geometry(geometry, ctx)
    for view in bundle.views:
        _get(ctx.assets, view.asset_id, "view asset")
        frame = _get(ctx.frames, view.frame_id, "view frame")
        if frame.asset_id != view.asset_id:
            _fail("view and coordinate frame belong to different assets")
        if view.parent_view_id:
            parent = _get(ctx.views, view.parent_view_id, "parent view")
            if ctx.assets[parent.asset_id].document_id != ctx.assets[view.asset_id].document_id:
                _fail("parent/child views must stay in one document revision")
            view_parents[view.id].add(parent.id)
        if view.boundary_geometry_id:
            geometry = _get(ctx.geometries, view.boundary_geometry_id, "view boundary")
            if geometry.frame_id != view.frame_id:
                _fail("view boundary must use the view's coordinate frame")
        _refs(ctx.entities, view.depicts_entity_ids, "depicted entity")
        project = ctx.documents[ctx.assets[view.asset_id].document_id].project_id
        if any(ctx.entities[e].project_id != project for e in view.depicts_entity_ids):
            _fail("view depicts an entity from another project")
    _acyclic(view_parents, "view hierarchy")
    for anchor in bundle.anchors:
        asset = _get(ctx.assets, anchor.asset_id, "evidence asset")
        if anchor.view_id and _get(ctx.views, anchor.view_id, "evidence view").asset_id != asset.id:
            _fail("evidence view belongs to another asset")
        if anchor.geometry_id:
            geometry = _get(ctx.geometries, anchor.geometry_id, "evidence geometry")
            if ctx.frames[geometry.frame_id].asset_id != asset.id:
                _fail("evidence geometry belongs to another asset")
            if anchor.view_id and geometry.frame_id != ctx.views[anchor.view_id].frame_id:
                _fail("evidence geometry must use its view's frame")
        selector = anchor.selector
        if not selector.value:
            _fail("native evidence selectors require a value")
        formats = {"ifc_guid": {"ifc"}, "step_id": {"ifc"}, "dxf_handle": {"dxf", "dwg"},
                   "svg_id": {"svg"}, "pdf_span": {"pdf"}}
        if selector.kind in formats and asset.format not in formats[selector.kind]:
            _fail("native evidence selector is incompatible with asset format")
        if selector.kind == "table_cell" and (selector.row_index is None or selector.column_index is None):
            _fail("table-cell selectors need row and column indices")
        if selector.kind == "image_region" and (not anchor.view_id or not anchor.geometry_id):
            _fail("image-region selectors need a view and geometry")
    for transform in bundle.transforms:
        source = _get(ctx.frames, transform.from_frame_id, "transform source frame")
        target = _get(ctx.frames, transform.to_frame_id, "transform target frame")
        expected = (target.dimension + 1, source.dimension + 1)
        if len(transform.matrix) != expected[0] or any(len(row) != expected[1] for row in transform.matrix):
            _fail("transform matrix dimensions disagree with source/target frames")
        if transform.kind == "homography" and (source.dimension != 2 or target.dimension != 2):
            _fail("homography requires two 2D frames")
        if transform.kind == "affine":
            if source.dimension != target.dimension:
                _fail("affine transforms must preserve dimension")
            if transform.matrix[-1] != [0.0] * source.dimension + [1.0]:
                _fail("affine transform requires a homogeneous final row")
        if transform.kind == "projection" and (source.dimension != 3 or target.dimension != 2):
            _fail("projection must map a 3D frame to a 2D frame")
        if _matrix_rank(transform.matrix) < target.dimension + 1:
            _fail("transform is singular or loses more dimensions than declared")
        ctx.provenance(transform.provenance)
    for calibration in bundle.calibrations:
        view = _get(ctx.views, calibration.view_id, "calibration view")
        transform = _get(ctx.transforms, calibration.transform_id, "calibration transform")
        source, target = ctx.frames[transform.from_frame_id], ctx.frames[transform.to_frame_id]
        if source.id != view.frame_id or target.space != "physical":
            _fail("calibration must map its own view frame into a physical frame")
        if source.space != "presentation" and calibration.method != "native_units":
            _fail("non-native calibration requires a presentation source frame")
        if source.dimension != 2 or target.dimension != 2 or transform.kind == "projection":
            _fail("plan calibration must be a 2D-to-2D mapping")
        if not calibration.provenance.anchor_ids:
            _fail("calibration needs scale or unit evidence")
        ctx.provenance(calibration.provenance)
        if not any(ctx.anchors[a].asset_id == view.asset_id for a in calibration.provenance.anchor_ids):
            _fail("calibration needs evidence from its source asset")
    for feature in bundle.features:
        _get(ctx.assets, feature.asset_id, "feature asset")
        if feature.view_id and _get(ctx.views, feature.view_id, "feature view").asset_id != feature.asset_id:
            _fail("feature view belongs to another asset")
        _refs(ctx.anchors, feature.anchor_ids, "feature evidence")
        if any(ctx.anchors[a].asset_id != feature.asset_id for a in feature.anchor_ids):
            _fail("feature evidence belongs to another asset")
        if feature.table_id:
            table = _get(ctx.features, feature.table_id, "feature table")
            if table.kind != "table" or table.asset_id != feature.asset_id:
                _fail("table feature must reference a table in its asset")
        if feature.kind == "table_cell" and (feature.table_id is None or feature.row_index is None or feature.column_index is None):
            _fail("table cells need a table, row, and column")
        _refs(ctx.features, feature.header_feature_ids, "table header feature")
        ctx.provenance(feature.provenance)
    for entity in bundle.entities:
        document = _get(ctx.documents, entity.document_id, "entity document")
        if document.project_id != entity.project_id:
            _fail("entity and document project disagree")
        _refs(ctx.concepts, entity.concept_ids, "entity concept")
        ctx.provenance(entity.provenance)
    for representation in bundle.representations:
        entity = _get(ctx.entities, representation.entity_id, "represented entity")
        asset = _get(ctx.assets, representation.asset_id, "representation asset")
        if ctx.documents[asset.document_id].project_id != entity.project_id:
            _fail("representation asset belongs to another project")
        if asset.document_id != entity.document_id:
            source_assets = [a.id for a in ctx.assets.values() if a.document_id == entity.document_id]
            if asset.id not in _reachable(ctx.asset_neighbors, source_assets):
                _fail("cross-document representation needs an explicit asset link")
        if representation.view_id and _get(ctx.views, representation.view_id, "representation view").asset_id != asset.id:
            _fail("representation view belongs to another asset")
        for feature_id in representation.feature_ids:
            if _get(ctx.features, feature_id, "representation feature").asset_id != asset.id:
                _fail("representation feature belongs to another asset")
        for anchor_id in representation.anchor_ids:
            if _get(ctx.anchors, anchor_id, "representation evidence").asset_id != asset.id:
                _fail("representation evidence belongs to another asset")
        for geometry_id in representation.geometry_ids:
            geometry = _get(ctx.geometries, geometry_id, "representation geometry")
            if ctx.frames[geometry.frame_id].asset_id != asset.id:
                _fail("representation geometry belongs to another asset")
        ctx.provenance(representation.provenance)
    for fact in bundle.facts:
        _get(ctx.entities, fact.subject_id, "fact subject")
        definition = _get(ctx.properties, fact.property_key, "fact property")
        if fact.value is not None:
            _value(fact.value, ctx, definition)
        if fact.supersedes_fact_id:
            prior = _get(ctx.facts, fact.supersedes_fact_id, "superseded fact")
            if (prior.subject_id, prior.property_key) != (fact.subject_id, fact.property_key):
                _fail("fact supersession must preserve subject and property")
        ctx.provenance(fact.provenance)
    for relation in bundle.relations:
        subject = _get(ctx.entities, relation.subject_id, "relation subject")
        obj = _get(ctx.entities, relation.object_id, "relation object")
        if subject.project_id != obj.project_id and relation.predicate != "same_as":
            _fail("relation joins entities from different projects")
        expected = {"typed_by": "type", "assigned_to_system": "system", "has_material": "material", "belongs_to_unit": "unit"}.get(relation.predicate)
        if expected and obj.kind != expected:
            _fail("relation target has an incompatible entity kind")
        if relation.predicate == "custom" and not relation.native_predicate:
            _fail("custom relations need a native predicate")
        ctx.provenance(relation.provenance)
    _acyclic(ctx.children, "contains/aggregates hierarchy")
    boundary_locators = set()
    for boundary in bundle.space_boundaries:
        space = _get(ctx.entities, boundary.space_id, "boundary space")
        locator = space.document_id, boundary.native_step_id
        if locator in boundary_locators:
            _fail("duplicate native space boundary locator")
        boundary_locators.add(locator)
        if space.kind != "space" and "ifc:IfcExternalSpatialElement" not in space.concept_ids:
            _fail("space boundary must belong to a space")
        if boundary.element_id:
            element = _get(ctx.entities, boundary.element_id, "boundary element")
            if element.document_id != space.document_id:
                _fail("space boundary joins different source revisions")
        for linked_id in [boundary.corresponding_boundary_id, boundary.parent_boundary_id]:
            if linked_id:
                linked = _get(ctx.space_boundaries, linked_id, "linked space boundary")
                if ctx.entities[linked.space_id].document_id != space.document_id:
                    _fail("linked boundaries belong to different source revisions")
        ctx.provenance(boundary.provenance)
        if not boundary.provenance.anchor_ids:
            _fail("space boundary needs source evidence")
        if not any(ctx.anchors[anchor_id].selector.kind == "step_id"
                   and ctx.anchors[anchor_id].selector.value == str(boundary.native_step_id)
                   and not ctx.anchors[anchor_id].selector.property_path
                   for anchor_id in boundary.provenance.anchor_ids):
            _fail("space boundary STEP locator must match its native evidence")
        for anchor_id in boundary.provenance.anchor_ids:
            if ctx.assets[ctx.anchors[anchor_id].asset_id].document_id != space.document_id:
                _fail("boundary evidence belongs to another source revision")
    for coverage in bundle.coverage:
        _scope(coverage.scope, ctx)
        _refs(ctx.concepts, coverage.concept_ids, "coverage concept")
        _refs(ctx.properties, coverage.property_keys, "coverage property")
        members = _scope_members(coverage.scope, ctx)
        for identifiers in [coverage.examined_entity_ids, coverage.unresolved_entity_ids, coverage.candidate_entity_ids]:
            if not set(identifiers) <= members:
                _fail("spatial coverage objects are outside scope")
        if coverage.completeness == "complete" and (coverage.unresolved_entity_ids or coverage.candidate_entity_ids):
            _fail("complete coverage cannot contain unresolved spatial objects")
        ctx.provenance(coverage.provenance)


def _field(field: Any, ctx: _Context, capabilities: CapabilityManifest | None,
           columns: dict[str, tuple[str, Any]] | None = None) -> tuple[str, Any]:
    if field.kind == "result_column":
        if columns is None or field.key not in columns:
            _fail(f"unknown derived result column: {field.key}")
        return columns[field.key]
    if columns is not None:
        _fail("table operations must reference derived columns using result_column")
    if field.kind == "property":
        definition = _get(ctx.properties, field.key, "query property")
        if capabilities is not None and field.key not in capabilities.property_keys:
            _fail(f"unsupported property: {field.key}")
        return definition.value_kind, definition.dimension
    return ("references" if field.kind == "entity_id" else "text"), None


def _predicate(predicate: Any, ctx: _Context, capabilities: CapabilityManifest | None) -> None:
    if predicate is None:
        return
    if predicate.kind in {"all", "any", "not"}:
        for child in predicate.operands:
            _predicate(child, ctx, capabilities)
    elif predicate.kind in {"compare", "field_present"}:
        _field(predicate.field, ctx, capabilities)
        if predicate.kind == "compare":
            definition = ctx.properties[predicate.field.key] if predicate.field.kind == "property" else None
            _value(predicate.value, ctx, definition if predicate.operator != "in" else None)
    elif predicate.kind == "related_to":
        _refs(ctx.entities, predicate.entity_ids, "predicate entity")
        if capabilities is not None and predicate.predicate not in capabilities.relation_predicates:
            _fail(f"unsupported relation: {predicate.predicate}")
    elif predicate.kind == "spatial":
        _get(ctx.geometries, predicate.geometry_id, "predicate geometry")
        if predicate.distance:
            _quantity(predicate.distance, ctx, LENGTH, "length")
            if predicate.distance.unit_id is None or Decimal(predicate.distance.magnitude) < 0:
                _fail("near distance needs a resolved nonnegative length")


def _operation_key(operation: Any) -> str:
    detail = {"aggregate": "method", "measure": "metric", "arithmetic": "operator"}.get(operation.kind)
    return f"{operation.kind}.{getattr(operation, detail)}" if detail else operation.kind


def _measure(operation: Any, candidates: set[str], scope: Any, ctx: _Context) -> None:
    unit = _get(ctx.units, operation.output_unit_id, "measurement output unit")
    if unit.kind != "physical" or unit.dimension != DIMENSIONS[operation.metric]:
        _fail("measurement output unit has incompatible dimensions")
    _refs(ctx.entities, operation.reference_entity_ids, "measurement reference entity")
    for identifier in operation.calibration_ids:
        calibration = _get(ctx.calibrations, identifier, "measurement calibration")
        if scope.view_ids and calibration.view_id not in scope.view_ids:
            _fail("measurement calibration is outside the selected views")
    for entity_id in candidates:
        representations = [r for r in ctx.representations.values()
                           if r.entity_id == entity_id and (not scope.view_ids or r.view_id in scope.view_ids)]
        geometries = [(r.view_id, ctx.geometries[g]) for r in representations for g in r.geometry_ids]
        if not geometries:
            _fail(f"measurement has no explicit geometry for {entity_id}")
        usable = False
        for view_id, geometry in geometries:
            frame = ctx.frames[geometry.frame_id]
            if operation.metric == "volume" and frame.dimension != 3:
                continue
            if frame.space == "physical":
                usable = True
            elif any(ctx.calibrations[c].view_id == view_id and
                     ctx.transforms[ctx.calibrations[c].transform_id].from_frame_id == frame.id
                     for c in operation.calibration_ids):
                usable = operation.metric != "volume"
            if usable:
                break
        if not usable:
            _fail(f"insufficient calibration or measurement geometry for {entity_id}")


def validate_plan(plan: QueryPlan, bundle: KnowledgeBundle,
                  capabilities: CapabilityManifest | None = None) -> None:
    """Validate references and supported operations; never execute model code.

    Candidate sets are conservative: arbitrary predicates are not executed here.
    An executor must resolve them, verify measurement geometry, and recompute all
    quantities. Call validate_bundle once when loading an immutable bundle.

    Traversal never expands the explicit scope. For floor-specific questions
    needing external type/material entities, use model-wide scope with an
    explicit floor selection, or preserve inherited facts on the occurrence
    together with their original type/property evidence.
    """
    ctx = _Context(bundle)
    _scope(plan.scope, ctx)
    if capabilities is not None:
        _refs({name: name for name in capabilities.operations}, plan.required_capabilities, "required capability")
    scope_members = _scope_members(plan.scope, ctx)
    candidates: dict[str, set[str]] = {}
    shapes: dict[str, str] = {}
    result_columns: dict[str, dict[str, tuple[str, Any]]] = {}
    concept_children: dict[str, set[str]] = defaultdict(set)
    for concept in bundle.concepts:
        for parent in concept.parent_ids:
            concept_children[parent].add(concept.id)
    for step in plan.steps:
        op = step.operation
        if capabilities is not None and _operation_key(op) not in capabilities.operations:
            _fail(f"unsupported operation: {_operation_key(op)}")
        current = set(scope_members)
        shape = "entities"
        columns = None
        if hasattr(op, "input_step_id"):
            current = candidates[op.input_step_id]
            shape = shapes[op.input_step_id]
            columns = result_columns.get(op.input_step_id)
        if op.kind == "select":
            _refs(ctx.concepts, op.concept_ids, "selected concept")
            if capabilities is not None and not set(op.concept_ids) <= set(capabilities.concept_ids):
                _fail("unsupported selected concept")
            allowed_concepts = _reachable(concept_children, op.concept_ids)
            if op.concept_ids:
                current &= {e.id for e in ctx.entities.values() if set(e.concept_ids) & allowed_concepts}
            if op.entity_kinds:
                allowed_kinds = {"site", "building", "storey", "unit", "space", "element", "assembly", "part", "type", "system", "material", "zone", "site_feature", "schedule_row"}
                if not set(op.entity_kinds) <= allowed_kinds:
                    _fail("unknown entity kind in selection")
                current &= {e.id for e in ctx.entities.values() if e.kind in op.entity_kinds}
            _predicate(op.where, ctx, capabilities)
            _predicate(op.exclude, ctx, capabilities)
        elif op.kind == "traverse":
            if shape != "entities":
                _fail("traversal requires an entity-set input")
            if capabilities is not None and op.predicate not in capabilities.relation_predicates:
                _fail(f"unsupported traversal relation: {op.predicate}")
            graph: dict[str, set[str]] = defaultdict(set)
            for relation in bundle.relations:
                if relation.predicate == op.predicate:
                    a, b = relation.subject_id, relation.object_id
                    if op.direction == "incoming":
                        a, b = b, a
                    graph[a].add(b)
            current = (_reachable(graph, current) - current if op.recursive
                       else {b for a in current for b in graph.get(a, ())}) & scope_members
        elif op.kind == "aggregate":
            if shape == "scalar":
                _fail("aggregation requires entities or table rows, not a scalar")
            for field in [*op.group_by, *([op.field] if op.field else [])]:
                _field(field, ctx, capabilities, columns)
            value_kind, dimension = ("count", None)
            if op.field:
                value_kind, dimension = _field(op.field, ctx, capabilities, columns)
                if value_kind not in {"quantity", "count"}:
                    _fail("numeric aggregation requires a numeric property")
                if op.output_unit_id:
                    unit = _get(ctx.units, op.output_unit_id, "aggregate output unit")
                    if value_kind != "quantity" or unit.kind != "physical" or (dimension is not None and unit.dimension != dimension):
                        _fail("aggregate output unit has incompatible dimensions")
            if op.group_by:
                result_columns[step.id] = {
                    field.key: _field(field, ctx, capabilities, columns) for field in op.group_by}
                result_columns[step.id][op.value_key] = value_kind, dimension
                shape = "table"
            else:
                shape = "scalar"
        elif op.kind == "spatial_query":
            if shape != "entities":
                _fail("native spatial queries require an entity-set input")
            if op.relation not in {"outdoor_access", "exterior_doors"}:
                shape = "table"
                result_columns[step.id] = {
                    "subject": ("references", None), "related": ("references", None),
                    "via": ("references", None), "basis": ("text", None),
                }
                # Conservative candidates; the executor resolves native paths.
                current = set(scope_members)
        elif op.kind == "related_entities":
            if shape != "table" or columns is None:
                _fail("related_entities requires a table input")
            if op.column not in columns or columns[op.column][0] != "references":
                _fail("related_entities requires a references column")
            shape = "entities"
        elif op.kind == "project":
            if shape == "scalar":
                _fail("projection requires entities or table rows")
            result_columns[step.id] = {
                field.key: _field(field, ctx, capabilities, columns) for field in op.fields}
            shape = "table"
        elif op.kind == "rank":
            if shape == "scalar":
                _fail("ranking requires entities or table rows")
            _field(op.field, ctx, capabilities, columns)
            if columns is not None:
                result_columns[step.id] = columns
        elif op.kind == "measure":
            if shape != "entities":
                _fail("measurement requires an entity-set input")
            _measure(op, current, plan.scope, ctx)
            shape = "scalar"
        elif op.kind == "arithmetic":
            if any(shapes[i] != "scalar" for i in op.input_step_ids):
                _fail("arithmetic requires scalar inputs")
            if op.output_unit_id:
                unit = _get(ctx.units, op.output_unit_id, "arithmetic output unit")
                if unit.kind != "physical":
                    _fail("arithmetic output cannot use presentation units")
            current = set().union(*(candidates[i] for i in op.input_step_ids))
            shape = "scalar"
        candidates[step.id] = current
        shapes[step.id] = shape


def _pointer(value: Any, pointer: str) -> Any:
    current = value.model_dump(mode="json")
    if not pointer:
        return current
    if not pointer.startswith("/"):
        _fail("evidence value_path must be a JSON Pointer")
    for raw in pointer[1:].split("/"):
        token = raw.replace("~1", "/").replace("~0", "~")
        try:
            if isinstance(current, list):
                if re.fullmatch(r"0|[1-9][0-9]*", token) is None:
                    _fail("JSON Pointer array index must be a nonnegative canonical integer")
                current = current[int(token)]
            else:
                current = current[token]
        except (KeyError, IndexError, TypeError, ValueError):
            _fail(f"evidence value_path does not resolve: {pointer}")
    return current


def validate_result(result: QueryResult, bundle: KnowledgeBundle,
                    plan: QueryPlan | None = None) -> None:
    """Validate trace references and conservative exact-claim coverage.

    Exact numeric claims need one complete coverage declaration matching their
    exact scope and covering all requested concepts/properties/count policy.
    External set members and arbitrary arithmetic are executor responsibilities.
    """
    ctx = _Context(bundle)
    sets = _index(result.entity_sets, "result entity set")
    nodes = _index(result.calculations, "calculation")
    _index(result.claims, "claim")
    if plan is not None and (result.plan_id != plan.id or result.request_id != plan.request_id):
        _fail("result request/plan identity mismatch")
    for entity_set in result.entity_sets:
        _scope(entity_set.scope, ctx)
        if entity_set.entity_ids is not None:
            _refs(ctx.entities, entity_set.entity_ids, "set member")
            if not set(entity_set.entity_ids) <= _scope_members(entity_set.scope, ctx):
                _fail("entity set contains members outside its scope")
            members = set(entity_set.entity_ids)
            for member in members:
                descendants = _reachable(ctx.parts, [member]) - {member}
                if entity_set.count_policy.hierarchy == "topmost_matches" and descendants & members:
                    _fail("topmost count policy includes both assembly and part")
                if entity_set.count_policy.hierarchy == "leaves" and ctx.parts.get(member):
                    _fail("leaf count policy includes an assembly with parts")
    prior = set()
    for node in result.calculations:
        if not set(node.input_node_ids) <= prior:
            _fail("calculation inputs must refer to earlier nodes (DAG order)")
        prior.add(node.id)
        for spatial in node.spatial_evidence:
            _refs(ctx.entities, [spatial.subject_id, *spatial.related_ids], "spatial evidence object")
            _refs(ctx.anchors, spatial.anchor_ids, "spatial evidence anchor")
            if plan is not None and not {spatial.subject_id, *spatial.related_ids} <= _scope_members(plan.scope, ctx):
                _fail("spatial evidence objects are outside the captured scope")
        if node.operation in {"count", "sum", "mean", "min", "max", "group_by"} and node.quality == "exact" and any(
                spatial.status in {"candidate", "unavailable"} for spatial in node.spatial_evidence):
            _fail("exact aggregation cannot consume unresolved spatial evidence")
        if plan is not None and node.plan_step_id is not None:
            _refs({step.id: step for step in plan.steps}, [node.plan_step_id], "calculation plan step")
        _refs(ctx.facts, node.fact_ids, "calculation fact")
        if any(ctx.facts[f].status != "present" for f in node.fact_ids):
            _fail("successful calculations cannot consume absent facts")
        _refs(ctx.anchors, node.anchor_ids, "calculation evidence")
        _refs(ctx.calibrations, node.calibration_ids, "calculation calibration")
        for identifier in [node.included_set_id, node.excluded_set_id]:
            if identifier:
                _get(sets, identifier, "calculation entity set")
        _value(node.output, ctx)
        if node.operation == "count":
            if node.included_set_id is None or node.output.kind != "count":
                _fail("count trace needs an entity set and count output")
            if node.output.value != sets[node.included_set_id].count:
                _fail("count output disagrees with included entity-set cardinality")
        if node.quality == "exact" and any(nodes[i].quality != "exact" for i in node.input_node_ids):
            _fail("exact calculation depends on an inexact calculation")
        if node.quality == "exact" and any(
                value.kind == "quantity" and value.quality != "exact"
                for f in node.fact_ids for value in _values(ctx.facts[f].value)):
            _fail("exact calculation consumes an inexact fact quantity")
        if node.quality == "exact" and any(v.kind == "quantity" and v.quality != "exact" for v in _values(node.output)):
            _fail("exact calculation contains an inexact quantity")
    for issue in result.issues:
        _refs(ctx.entities, issue.entity_ids, "issue entity")
        _refs(ctx.facts, issue.fact_ids, "issue fact")
        _refs(ctx.anchors, issue.anchor_ids, "issue evidence")
    for claim in result.claims:
        _scope(claim.scope, ctx)
        _refs(ctx.concepts, claim.concept_ids, "claim concept")
        _refs(ctx.properties, claim.property_keys, "claim property")
        _value(claim.value, ctx)
        if plan is not None:
            if _scope_key(claim.scope) != _scope_key(plan.scope):
                _fail("claim scope must match the explicit plan scope")
            if claim.output_key not in plan.outputs:
                _fail("claim output_key does not identify a requested plan output")
        numeric = any(v.kind in {"count", "quantity"} for v in _values(claim.value))
        has_count = any(v.kind == "count" for v in _values(claim.value))
        if has_count and claim.count_policy is None:
            _fail("count claims require an explicit count policy")
        qualifying = []
        for identifier in claim.coverage_ids:
            coverage = _get(ctx.coverage, identifier, "claim coverage")
            if _scope_key(coverage.scope) != _scope_key(claim.scope):
                _fail("claim coverage scope differs from claim scope")
            if (set(claim.concept_ids) <= set(coverage.concept_ids)
                    and set(claim.property_keys) <= set(coverage.property_keys)
                    and (claim.count_policy is None or coverage.count_policy == claim.count_policy)):
                qualifying.append(coverage)
        complete = any(c.completeness == "complete" for c in qualifying)
        if numeric and claim.quality == "exact" and not complete:
            _fail("exact numeric claim requires complete matching coverage")
        if numeric and not complete and result.status != "partial":
            _fail("incomplete numeric claim must be an explicitly partial outcome")
        if claim.quality == "exact" and any(v.kind == "quantity" and v.quality != "exact" for v in _values(claim.value)):
            _fail("exact claim contains an inexact quantity")
        root_bound = False
        for binding in claim.evidence:
            _refs(ctx.anchors, binding.anchor_ids, "claim evidence")
            _refs(ctx.facts, binding.fact_ids, "claim fact")
            _refs(sets, binding.entity_set_ids, "claim entity set")
            node = _get(nodes, binding.calculation_id, "claim calculation")
            target = _pointer(claim.value, binding.value_path)
            if target != node.output.model_dump(mode="json"):
                _fail("claim evidence calculation output disagrees with bound value")
            if not binding.value_path:
                root_bound = True
                if plan is not None and node.plan_step_id != plan.outputs[claim.output_key]:
                    _fail("claim root calculation must identify its requested output step")
                if node.operation == "count":
                    entity_set = sets[node.included_set_id]
                    if _scope_key(entity_set.scope) != _scope_key(claim.scope):
                        _fail("root count entity set has a different scope")
                    if entity_set.count_policy != claim.count_policy:
                        _fail("root count policy disagrees with claim count policy")
            if claim.quality == "exact" and node.quality != "exact":
                _fail("exact claim depends on an inexact calculation")
            for identifier in binding.entity_set_ids:
                entity_set = sets[identifier]
                if _scope_key(entity_set.scope) != _scope_key(claim.scope):
                    _fail("claim entity-set scope mismatch")
                if claim.count_policy is not None and entity_set.count_policy != claim.count_policy:
                    _fail("claim/entity-set count policies disagree")
        if not root_bound:
            _fail("claim needs a root evidence binding for its complete output")
