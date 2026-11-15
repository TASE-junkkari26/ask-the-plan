"""A bounded, deterministic executor. Plans never contain executable code."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from decimal import Decimal, localcontext
import hashlib
import json
import math
from pathlib import Path
from time import perf_counter

from contracts import models as m
from contracts.validation import validate_bundle, validate_plan, validate_result
from . import __version__
from .catalog import CLASS_KEY, CONCEPT_CLASSES, POLICIES, RELATIONS, property_key
from .ingest import load_ifc
from .units import SI_TARGETS, convert, decimal_string

EXECUTOR_VERSION = "ifc-engine/" + __version__
OPERATIONS = ["select", "traverse", "spatial_query", "related_entities", "network_query", "material_quantity", "route_query", "project", "rank",
              *["aggregate." + name for name in ["count", "sum", "mean", "min", "max"]],
              *["arithmetic." + name for name in ["add", "subtract", "multiply", "divide"]],
              *["table_calculate." + name for name in ["add", "subtract", "multiply", "divide", "percent_of_total", "consecutive_difference"]],
              *["measure." + name for name in ["area", "union_area", "enclosed_area", "volume", "length", "perimeter", "distance", "height", "base_elevation", "horizontal_distance"]]]


class QueryError(ValueError):
    def __init__(self, code: str, message: str, entity_ids=(), fact_ids=(), options=(), anchor_ids=()):
        super().__init__(message)
        self.code, self.entity_ids, self.fact_ids, self.options = code, list(entity_ids), list(fact_ids), list(options)
        self.anchor_ids = list(anchor_ids)


@dataclass
class _Support:
    members: set[str] = field(default_factory=set)
    facts: set[str] = field(default_factory=set)
    anchors: set[str] = field(default_factory=set)
    operation: str = "lookup"
    evidence_kind: str = "verified"
    metadata: dict = field(default_factory=dict)
    input_node_ids: list[str] = field(default_factory=list)
    # Native quantity family, record index, source batch start and batch size.
    source_record: tuple[str, int, int, int] | None = None


@dataclass
class _State:
    value: object
    members: set[str]
    policy: m.CountPolicy
    concepts: set[str] = field(default_factory=set)
    properties: set[str] = field(default_factory=set)
    facts: set[str] = field(default_factory=set)
    anchors: set[str] = field(default_factory=set)
    shape: str = "entities"
    cells: list[dict[str, _Support]] = field(default_factory=list)
    conversions: list[tuple[m.QuantityValue, _Support]] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    issues: list[m.Issue] = field(default_factory=list)
    quality: str = "exact"
    completeness: str = "complete"
    coverage_explanation: str | None = None
    excluded: set[str] = field(default_factory=set)
    spatial_records: list[dict] = field(default_factory=list)
    unresolved: set[str] = field(default_factory=set)
    candidate_members: set[str] = field(default_factory=set)
    coverage_complete: bool = True
    operation_keys: list[str] = field(default_factory=list)
    measurement_records: list[dict] = field(default_factory=list)
    internal_nodes: list[m.CalculationNode] = field(default_factory=list)
    network_records: list[dict] = field(default_factory=list)
    material_records: list[dict] = field(default_factory=list)
    route_records: list[dict] = field(default_factory=list)


def _reachable(graph, roots):
    visited, pending = set(), list(roots)
    while pending:
        node = pending.pop()
        if node not in visited:
            visited.add(node)
            pending.extend(graph.get(node, ()))
    return visited


class IfcQueryEngine:
    def __init__(self, bundle: m.KnowledgeBundle, *, schema="unknown", warnings=(), cache_hit=False):
        validate_bundle(bundle)
        self.bundle, self.schema, self.warnings, self.cache_hit = bundle, schema, list(warnings), cache_hit
        self.geometry = None
        self.hydrator = None
        self.entities = {item.id: item for item in bundle.entities}
        self.properties = {item.key: item for item in bundle.properties}
        self.units = {item.id: item for item in bundle.units}
        self.anchors = {item.id: item for item in bundle.anchors}
        self._base_anchor_ids = set(self.anchors)
        self.entity_anchors = defaultdict(set)
        for representation in bundle.representations:
            self.entity_anchors[representation.entity_id].update(representation.anchor_ids)
        self.facts = defaultdict(list)
        for fact in bundle.facts:
            self.facts[fact.subject_id, fact.property_key].append(fact)
        self._fact_ids = {fact.id for fact in bundle.facts}
        self._hydrated_fact_ids = set()
        self._base_coverage_ids = {coverage.id for coverage in bundle.coverage}
        self.graphs = defaultdict(lambda: defaultdict(set))
        self.edge_anchors = defaultdict(set)
        self.children, self.parts, self.parents = defaultdict(set), defaultdict(set), defaultdict(set)
        for rel in bundle.relations:
            self.graphs[rel.predicate, "outgoing"][rel.subject_id].add(rel.object_id)
            self.graphs[rel.predicate, "incoming"][rel.object_id].add(rel.subject_id)
            self.edge_anchors[rel.predicate, "outgoing", rel.subject_id, rel.object_id].update(rel.provenance.anchor_ids)
            self.edge_anchors[rel.predicate, "incoming", rel.object_id, rel.subject_id].update(rel.provenance.anchor_ids)
            if rel.predicate in {"contains", "aggregates"}:
                self.children[rel.subject_id].add(rel.object_id)
            if rel.predicate == "aggregates":
                self.parts[rel.subject_id].add(rel.object_id)
                self.parents[rel.object_id].add(rel.subject_id)
        self.concept_children = defaultdict(set)
        for concept in bundle.concepts:
            for parent in concept.parent_ids:
                self.concept_children[parent].add(concept.id)
        self.concept_ids = {item.id for item in bundle.concepts}
        native_parents = {concept.id: concept.parent_ids for concept in bundle.concepts}
        self.type_alternatives = {}
        for identifier, candidates in self.graphs["typed_by", "outgoing"].items():
            if len(candidates) < 2:
                continue
            alternatives = []
            for native_type in sorted(candidates):
                classes = {name.removeprefix("ifc:").removesuffix("Type").removesuffix("Style")
                           for name in _reachable(native_parents, self.entities[native_type].concept_ids)}
                alternatives.append({"concept:" + name for name, native in CONCEPT_CLASSES.items() if native in classes})
            self.type_alternatives[identifier] = alternatives
        self.capabilities = m.CapabilityManifest(
            executor_version=EXECUTOR_VERSION, operations=OPERATIONS, relation_predicates=list(RELATIONS),
            property_keys=sorted(self.properties), concept_ids=sorted(self.concept_ids), supported_formats=["ifc"],
            limitations=[
                "Single IFC revision; only source_records and modeled_objects scopes are supported.",
                "Counts describe supported records in the supplied model, not physical building completeness.",
                "Scalar attributes, single-value properties, bounded enumeration/list properties, simple quantities and native material composition records are extracted; arbitrary nested source properties remain unsupported.",
                "Native topology, bounded geometry, typed arithmetic and qualified modeled walking routes are supported; general spatial predicates and certified egress compliance are not implemented.",
                "Missing values fail by default; explicit partial sums of proven nonnegative material-volume/area cells yield qualified lower bounds. Exterior-door lower-bound counts are supported; other unresolved topology aggregates and derived row counts are not.",
                "Only the registered IFC occurrence, topmost-assembly and leaf policies are supported.",
                "Ranking is bounded; ties use stable entity/row order and do not establish a unique extremum.",
            ])

    @classmethod
    def open(cls, path: str | Path, **kwargs):
        loaded = load_ifc(path, **kwargs)
        engine = cls(loaded.bundle, schema=loaded.schema, warnings=loaded.warnings, cache_hit=loaded.cache_hit)
        engine.hydrator = getattr(loaded, "hydrator", None)
        from .geometry import GeometryProvider
        engine.geometry = GeometryProvider(Path(path), loaded.bundle.assets[0].sha256)
        return engine

    def ensure_fields(self, entity_ids, property_keys):
        """Consult retained native data before classifying deferred facts absent.

        A hydrator reports newly checked pairs, including genuine absence. Its
        source and work-budget failures remain explicit non-answers; neither is
        interpreted as a missing property or a failed predicate.
        """
        if self.hydrator is None:
            return
        entities = set(entity_ids)
        keys = set(property_keys)
        if not entities or not keys:
            return
        if not entities <= self.entities.keys():
            raise QueryError("execution_error", "Deferred property inputs contain an unknown source entity.")
        try:
            batch = self.hydrator.ensure_fields(entities, keys)
        except ValueError as error:
            code = getattr(error, "code", "incomplete_coverage")
            if code not in {"unsupported_operation", "missing_source", "incomplete_coverage", "conflicting_evidence"}:
                code = "incomplete_coverage"
            raise QueryError(code, "The requested native source properties could not be fully inspected within the bounded hydration budget.", sorted(entities)) from None
        for anchor in batch.anchors:
            if anchor.id not in self.anchors:
                self.anchors[anchor.id] = anchor
                self.bundle.anchors.append(anchor)
        for unit in batch.units:
            if unit.id not in self.units:
                self.units[unit.id] = unit
                self.bundle.units.append(unit)
        for fact in batch.facts:
            if fact.id not in self._fact_ids:
                self.bundle.facts.append(fact)
                self.facts[fact.subject_id, fact.property_key].append(fact)
                self._fact_ids.add(fact.id)
                self._hydrated_fact_ids.add(fact.id)

    def clear_hydration(self):
        """Release request facts after its response proof has been captured.

        Call only between complete questions, never between discovery and plan
        execution. Existing API responses own their captured fact/anchor lists.
        Core native anchors and unit definitions remain stable; request-only
        property locators are recreated with the same IDs when queried again.
        """
        if self.hydrator is None:
            return
        removed = set(self.hydrator.reset()) & self._hydrated_fact_ids
        if removed:
            self.bundle.facts[:] = [fact for fact in self.bundle.facts if fact.id not in removed]
            for key in list(self.facts):
                retained = [fact for fact in self.facts[key] if fact.id not in removed]
                if retained:
                    self.facts[key] = retained
                else:
                    del self.facts[key]
            self._fact_ids.difference_update(removed)
        self._hydrated_fact_ids.clear()
        self.bundle.coverage[:] = [coverage for coverage in self.bundle.coverage if coverage.id in self._base_coverage_ids]
        for identifier in set(self.anchors) - self._base_anchor_ids:
            del self.anchors[identifier]
        self.bundle.anchors[:] = [anchor for anchor in self.bundle.anchors if anchor.id in self._base_anchor_ids]

    def _ensure_references(self, entity_ids, references):
        self.ensure_fields(entity_ids, {ref.key for ref in references if ref is not None and ref.kind == "property"})

    def _predicate_references(self, predicate):
        if predicate is None:
            return []
        if predicate.kind in {"all", "any", "not"}:
            return [ref for child in predicate.operands for ref in self._predicate_references(child)]
        return [predicate.field] if predicate.kind in {"compare", "field_present"} else []

    def scope(self, storey: str | None = None, entity: str | None = None) -> m.Scope:
        roots = []
        if storey is not None:
            roots = [self.resolve_entity(storey, kind="storey")]
        if entity is not None:
            identifier = self.resolve_entity(entity)
            if roots and identifier not in _reachable(self.children, roots):
                raise QueryError("needs_clarification", "Selected entity is outside the requested storey.")
            roots = [identifier]
        return m.Scope(project_id=self.bundle.projects[0].id,
                       document_ids=[self.bundle.documents[0].id], entity_ids=roots, universe="modeled_objects")

    def resolve_entity(self, value: str, *, kind: str | None = None) -> str:
        candidates = []
        for entity in self.entities.values():
            if kind and entity.kind != kind:
                continue
            selectors = [self.anchors[a].selector for a in self.entity_anchors[entity.id] | set(entity.provenance.anchor_ids)]
            labels = {label.text.casefold() for label in entity.labels}
            locators = {s.value for s in selectors if not s.property_path}
            locators |= {"#" + s.value for s in selectors if s.kind == "step_id" and not s.property_path}
            if value == entity.id or value in locators or value.casefold() in labels:
                candidates.append(entity.id)
        if len(candidates) != 1:
            raise QueryError("needs_clarification", f"Expected one {kind or 'entity'} matching {value!r}; found {len(candidates)}.",
                             options=[f"{e}: {', '.join(x.text for x in self.entities[e].labels)}" for e in candidates])
        return candidates[0]

    def resolve_concept(self, target: str) -> str:
        candidates = [target, "concept:" + target, "ifc:" + target]
        candidates += ["concept:" + name for name, cls in CONCEPT_CLASSES.items() if cls == target]
        for candidate in candidates:
            if candidate in self.concept_ids:
                return candidate
        raise QueryError("unsupported_operation", f"Unsupported IFC class/concept {target!r}; inspect the catalog first.")

    def resolve_property(self, name: str) -> str:
        if name in self.properties:
            return name
        candidates = [p.key for p in self.properties.values() if any(label.text == name for label in p.labels)]
        if len(candidates) == 1:
            return candidates[0]
        if candidates:
            raise QueryError("needs_clarification", f"Property {name!r} is ambiguous.", options=candidates)
        raise QueryError("missing_information", f"Property {name!r} is not present in the extracted catalog.")

    def plan(self, target: str, *, operation="count", property: str | None = None,
             storey: str | None = None, entity: str | None = None,
             hierarchy="all_matches", unit: str | None = None, limit=10,
             direction="descending", request_id="request:local") -> m.QueryPlan:
        if hierarchy not in POLICIES:
            raise QueryError("unsupported_operation", f"Unsupported hierarchy policy {hierarchy!r}.")
        scope = self.scope(storey, entity)
        concept = self.resolve_concept(target)
        steps = [m.PlanStep(id="objects", operation=m.SelectOperation(kind="select", concept_ids=[concept], count_policy=POLICIES[hierarchy]))]
        if operation == "count":
            op = m.AggregateOperation(kind="aggregate", input_step_id="objects", method="count")
        else:
            if property is None:
                raise QueryError("needs_clarification", "A property is required for this operation.")
            key = self.resolve_property(property)
            field_ref = m.FieldRef(kind="property", key=key)
            if operation in {"sum", "mean", "min", "max"}:
                unit_id = unit if unit is None or unit.startswith("unit:") else "unit:" + unit
                if unit_id is not None and unit_id not in self.units:
                    raise QueryError("needs_clarification", f"Unknown output unit {unit!r}.", options=sorted(self.units))
                op = m.AggregateOperation(kind="aggregate", input_step_id="objects", method=operation,
                                           field=field_ref, output_unit_id=unit_id)
            elif operation in {"lookup", "rank"}:
                input_id = "objects"
                if operation == "rank":
                    steps.append(m.PlanStep(id="ranked", operation=m.RankOperation(kind="rank", input_step_id=input_id,
                                     field=field_ref, direction=direction, limit=limit)))
                    input_id = "ranked"
                op = m.ProjectOperation(kind="project", input_step_id=input_id,
                     fields=[m.FieldRef(kind="entity_id", key="entity_id"), m.FieldRef(kind="label", key="label"), field_ref])
            else:
                raise QueryError("unsupported_operation", f"Unsupported query operation {operation!r}.")
        steps.append(m.PlanStep(id="answer", operation=op))
        payload = {"scope": scope.model_dump(), "steps": [step.model_dump() for step in steps], "request_id": request_id}
        identifier = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:24]
        return m.QueryPlan(id="plan:" + identifier, request_id=request_id, scope=scope,
                           steps=steps, outputs={"answer": "answer"})

    def query(self, target: str, **kwargs) -> m.QueryResult:
        try:
            return self.execute(self.plan(target, **kwargs))
        except QueryError as exc:
            return self._failure(exc, kwargs.get("request_id", "request:local"))

    def _failure(self, error, request_id, plan_id=None, latency=0):
        return m.QueryResult(id="result:" + hashlib.sha256((request_id + (plan_id or "") + str(error)).encode()).hexdigest()[:24],
            request_id=request_id, plan_id=plan_id, status=error.code,
            issues=[m.Issue(code=error.code, message=m.LocalizedText(text=str(error)),
                            entity_ids=error.entity_ids, fact_ids=error.fact_ids,
                            anchor_ids=error.anchor_ids,
                            options=[m.LocalizedText(text=text) for text in error.options])],
            executor_version=EXECUTOR_VERSION, metrics=m.ExecutionMetrics(latency_ms=latency, cache_hit=self.cache_hit))

    def execute(self, plan: m.QueryPlan) -> m.QueryResult:
        started = perf_counter()
        try:
            return self._execute(plan, started)
        except QueryError as exc:
            result = self._failure(exc, plan.request_id, plan.id, (perf_counter() - started) * 1000)
            validate_result(result, self.bundle, plan)
            return result

    def _execute(self, plan, started):
        if plan.scope.universe not in {"source_records", "modeled_objects"} or plan.scope.view_ids:
            raise QueryError("unsupported_operation", "This executor supports source/model scope without drawing views.")
        if not set(plan.required_capabilities) <= set(OPERATIONS):
            raise QueryError("unsupported_operation", "The plan requires capabilities unavailable in this executor.")
        for step in plan.steps:
            op = step.operation
            capability = ("aggregate." + op.method if op.kind == "aggregate" else
                          op.kind + "." + op.operator if op.kind in {"arithmetic", "table_calculate"} else
                          "measure." + op.metric if op.kind == "measure" else op.kind)
            if capability not in OPERATIONS:
                raise QueryError("unsupported_operation", f"Operation {capability!r} has no local executor yet.")
            if op.kind == "select" and op.count_policy not in POLICIES.values():
                raise QueryError("unsupported_operation", "This counting rule has no registered IFC implementation.")
            if op.kind == "aggregate" and op.missing_values == "partial" and (
                    op.method != "sum" or op.group_by or op.field.kind != "result_column"
                    or op.field.key not in {"volume", "value"}):
                raise QueryError("unsupported_operation", "Partial aggregation supports an explicit scalar SUM of proven material-volume or measured-area table cells only.")
            if op.kind == "select":
                self._check_predicate(op.where)
                self._check_predicate(op.exclude)
        scope_members = {e.id for e in self.entities.values() if e.project_id == plan.scope.project_id and e.document_id in plan.scope.document_ids}
        if plan.scope.entity_ids:
            scope_members &= _reachable(self.children, plan.scope.entity_ids)
        if plan.scope.exact_entity_ids is not None:
            scope_members &= set(plan.scope.exact_entity_ids)
        for step in plan.steps:
            if step.operation.kind == "measure":
                outside = set(step.operation.reference_entity_ids) - scope_members
                if outside:
                    raise QueryError("incomplete_coverage", "Required measurement reference objects are outside the captured scope.", sorted(outside))
        try:
            validate_plan(plan, self.bundle, self.capabilities)
        except ValueError as exc:
            raise QueryError("execution_error", "Invalid query plan: " + str(exc)) from exc
        states, calculations, sets = {}, [], []
        for step in plan.steps:
            op = step.operation
            excluded_id = None
            if op.kind == "select":
                allowed = _reachable(self.concept_children, op.concept_ids)
                members = {e for e in scope_members if (not allowed or allowed.intersection(self.entities[e].concept_ids))
                           and (not op.entity_kinds or self.entities[e].kind in op.entity_kinds)}
                uncertain = set()
                if allowed:
                    for identifier in scope_members & self.type_alternatives.keys():
                        if identifier in members or (op.entity_kinds and self.entities[identifier].kind not in op.entity_kinds):
                            continue
                        alternatives = self.type_alternatives[identifier]
                        if any(allowed & values for values in alternatives):
                            members.add(identifier)
                            if not all(allowed & values for values in alternatives):
                                uncertain.add(identifier)
                state = _State(None, members, op.count_policy, set(op.concept_ids))
                # Property-free identity/label/relation guards can often
                # resolve an occurrence before its deferred properties matter.
                # Hydrating every field on every occurrence first would spend
                # a whole-model budget to inspect one named object.
                guards, hydration_groups = {}, defaultdict(set)
                for entity_id in sorted(members):
                    included = True if op.where is None else self._predicate_guard(entity_id, op.where, state, scope_members)
                    excluded = False if op.exclude is None else self._predicate_guard(entity_id, op.exclude, state, scope_members)
                    guards[entity_id] = included, excluded
                    if included is False or excluded is True:
                        continue
                    references = [*(self._predicate_references(op.where) if included is None else []),
                                  *(self._predicate_references(op.exclude) if excluded is None else [])]
                    keys = tuple(sorted({ref.key for ref in references if ref.kind == "property"}))
                    if keys:
                        hydration_groups[keys].add(entity_id)
                for keys, identifiers in hydration_groups.items():
                    self.ensure_fields(identifiers, keys)
                selected = set()
                for entity_id in sorted(members):
                    included, excluded = guards[entity_id]
                    if included is False or excluded is True:
                        continue
                    if included is None:
                        included = self._predicate(entity_id, op.where, state, scope_members)
                    if excluded is None:
                        excluded = self._predicate(entity_id, op.exclude, state, scope_members)
                    # Unknown comparisons cannot establish exhaustive filtered
                    # counts. An explicit field_present condition can still
                    # deliberately restrict a query to known source values.
                    if included is None and excluded is not True or excluded is None and included is not False:
                        raise QueryError("missing_information", "A filter depends on a missing source value; a complete selection cannot be established.", [entity_id])
                    if included is True and excluded is False:
                        if entity_id in uncertain:
                            facts, anchors = self._typing_support(entity_id)
                            raise QueryError("conflicting_evidence", "Conflicting native type assignments leave this occurrence's requested semantic category unresolved.",
                                             [entity_id], sorted(facts), anchor_ids=sorted(anchors))
                        if entity_id in self.type_alternatives:
                            facts, anchors = self._typing_support(entity_id)
                            state.facts.update(facts)
                            state.anchors.update(anchors)
                        selected.add(entity_id)
                state.members = selected
                if op.count_policy.hierarchy == "topmost_matches":
                    state.members -= {e for e in state.members if (_reachable(self.parents, [e]) - {e}) & state.members}
                elif op.count_policy.hierarchy == "leaves":
                    state.members = {e for e in state.members if not self.parts[e]}
                excluded_id = "set:" + step.id + ":excluded"
                excluded = members - state.members
                sets.append(m.EntitySet(id=excluded_id, scope=plan.scope, count_policy=POLICIES["all_matches"],
                                        count=len(excluded), entity_ids=sorted(excluded)))
                state.value = m.ReferencesValue(kind="references", entity_ids=sorted(state.members))
                inputs = []
            elif op.kind == "arithmetic":
                from .arithmetic import ArithmeticError, evaluate
                operands = [states[identifier] for identifier in op.input_step_ids]
                if any(item.shape != "scalar" for item in operands):
                    raise QueryError("unsupported_operation", "Arithmetic requires numeric scalar query results.")
                if any(item.quality not in {"exact", "estimated"} or item.unresolved or item.candidate_members
                       or not item.coverage_complete or item.completeness != "complete" for item in operands):
                    raise QueryError("incomplete_coverage", "Arithmetic requires complete, supported operand inputs.",
                                     sorted(set().union(*(item.members for item in operands))))
                if any(item.policy != operands[0].policy for item in operands):
                    raise QueryError("conflicting_evidence", "Arithmetic operands use different counting policies.")
                state = _State(None, set().union(*(item.members for item in operands)), operands[0].policy,
                    concepts=set().union(*(item.concepts for item in operands)),
                    properties=set().union(*(item.properties for item in operands)),
                    facts=set().union(*(item.facts for item in operands)),
                    anchors=set().union(*(item.anchors for item in operands)), shape="scalar",
                    notes=list(dict.fromkeys(note for item in operands for note in item.notes)),
                    spatial_records=[record for item in operands for record in item.spatial_records],
                    measurement_records=[record for item in operands for record in item.measurement_records],
                    network_records=[record for item in operands for record in item.network_records],
                    material_records=[record for item in operands for record in item.material_records],
                    route_records=[record for item in operands for record in item.route_records],
                    quality="estimated" if any(item.quality == "estimated" for item in operands) else "exact",
                    operation_keys=list(dict.fromkeys(key for item in operands for key in item.operation_keys)))
                try:
                    state.value, conversions = evaluate([item.value for item in operands], op, self.units)
                except ArithmeticError as error:
                    raise QueryError(error.code, str(error), sorted(state.members), sorted(state.facts)) from None
                for index, converted in conversions:
                    operand = operands[index]
                    state.conversions.append((converted, _Support(set(operand.members), set(operand.facts), set(operand.anchors))))
                inputs = ["calculation:" + identifier for identifier in op.input_step_ids]
            else:
                previous = states[op.input_step_id]
                state = _State(previous.value, set(previous.members), previous.policy, set(previous.concepts),
                               set(previous.properties), set(previous.facts), set(previous.anchors), previous.shape,
                               cells=[dict(row) for row in previous.cells], notes=list(previous.notes), issues=list(previous.issues),
                               quality=previous.quality, completeness=previous.completeness,
                               coverage_explanation=previous.coverage_explanation,
                               spatial_records=list(previous.spatial_records), unresolved=set(previous.unresolved),
                               candidate_members=set(previous.candidate_members), coverage_complete=previous.coverage_complete,
                               operation_keys=list(previous.operation_keys))
                state.measurement_records = list(previous.measurement_records)
                state.network_records = list(previous.network_records)
                state.material_records = list(previous.material_records)
                state.route_records = list(previous.route_records)
                inputs = ["calculation:" + op.input_step_id]
                if state.shape == "entities":
                    references = ([*op.group_by, *([op.field] if op.field else [])] if op.kind == "aggregate" else
                                  op.fields if op.kind == "project" else [op.field] if op.kind == "rank" else [])
                    self._ensure_references(state.members, references)
                if state.quality in {"lower_bound", "upper_bound"} and (op.kind != "aggregate" or op.method != "count"):
                    raise QueryError("unsupported_operation", "An incomplete exterior-door selection supports occurrence counting only; other operations need complete membership.")
                if op.kind == "route_query":
                    from .route import execute_route
                    target_state = states[op.target_step_id] if op.target_step_id is not None else None
                    execute_route(self, state, op, scope_members, target_state=target_state)
                    if op.target_step_id is not None:
                        inputs.append("calculation:" + op.target_step_id)
                elif op.kind == "material_quantity":
                    from .material_quantities import execute_material_quantity
                    execute_material_quantity(self, state, op, scope_members)
                elif op.kind == "network_query":
                    from .network import execute_network
                    component_state = states[op.component_step_id] if op.component_step_id is not None else None
                    execute_network(self, state, op, scope_members, component_state=component_state)
                    if op.component_step_id is not None:
                        inputs.append("calculation:" + op.component_step_id)
                elif op.kind == "measure":
                    from .measurement import execute_measurement
                    execute_measurement(self, state, op, scope_members)
                elif op.kind == "table_calculate":
                    from .table_calculation import execute_table_calculation
                    execute_table_calculation(self, state, op, step.id)
                elif op.kind == "spatial_query":
                    if op.relation == "exterior_doors" and op.exterior_basis != "boundary":
                        external = property_key("Pset_DoorCommon", "IsExternal")
                        if external in self.properties:
                            self.ensure_fields(state.members, [external])
                    from .spatial import execute_spatial
                    execute_spatial(self, state, op, scope_members)
                    if state.excluded:
                        excluded_id = "set:" + step.id + ":excluded"
                        sets.append(m.EntitySet(id=excluded_id, scope=plan.scope, count_policy=state.policy,
                            count=len(state.excluded), entity_ids=sorted(state.excluded)))
                elif op.kind == "related_entities":
                    members = set()
                    for index, row in enumerate(previous.value.rows):
                        value = row[op.column]
                        if isinstance(value, m.UnavailableValue):
                            continue
                        if not isinstance(value, m.ReferencesValue):
                            raise QueryError("needs_clarification", "The requested result column does not contain source objects.")
                        support = previous.cells[index][op.column]
                        members.update(value.entity_ids)
                        state.anchors.update(support.anchors)
                        state.facts.update(support.facts)
                        if support.evidence_kind == "candidate":
                            state.candidate_members.update(value.entity_ids)
                    if not members <= scope_members:
                        raise QueryError("incomplete_coverage", "The related source objects include objects outside the captured scope.",
                                         sorted(previous.members))
                    state.members, state.shape, state.cells = members, "entities", []
                    state.concepts = {concept for item in members for concept in self.entities[item].concept_ids}
                    state.policy = POLICIES["all_matches"]
                    state.value = m.ReferencesValue(kind="references", entity_ids=sorted(members))
                elif op.kind == "traverse":
                    if op.predicate == "has_material" and op.direction == "outgoing":
                        for identifier in state.members:
                            self._material_typing(identifier, state)
                    graph = self.graphs[op.predicate, op.direction]
                    members, frontier = set(), set(state.members)
                    for _ in range(op.max_depth if op.recursive else 1):
                        outside = {(a, b) for a in frontier for b in graph[a] if b not in scope_members}
                        if outside:
                            anchors = {anchor for a, b in outside for anchor in self.edge_anchors[op.predicate, op.direction, a, b]}
                            raise QueryError("incomplete_coverage", "The relationship traversal requires next-hop objects outside the captured scope.",
                                             sorted(previous.members), anchor_ids=sorted(anchors))
                        edges = {(a, b) for a in frontier for b in graph[a] if b in scope_members}
                        state.anchors.update(anchor for a, b in edges for anchor in self.edge_anchors[op.predicate, op.direction, a, b])
                        frontier = {b for _, b in edges} - members
                        members.update(frontier)
                        if not frontier:
                            break
                    state.members = members - previous.members if op.recursive else members
                    if previous.candidate_members:
                        state.candidate_members.update(state.members)
                    state.concepts = set().union(*(self.entities[e].concept_ids for e in state.members)) if state.members else set()
                    state.value = m.ReferencesValue(kind="references", entity_ids=sorted(state.members))
                    # Traversal produces occurrences; do not imply the input's assembly policy still applies.
                    state.policy = POLICIES["all_matches"]
                elif op.kind == "aggregate":
                    if op.missing_values == "partial":
                        from .partial_totals import execute_partial_sum
                        state.value, quantity_inputs = execute_partial_sum(self, state, op, step.id, scope_members)
                        inputs.extend(quantity_inputs)
                    else:
                        state.value = self._aggregate(state, op)
                    state.shape = "table" if isinstance(state.value, m.TableValue) else "scalar"
                elif op.kind == "project":
                    if len({ref.key for ref in op.fields}) != len(op.fields):
                        raise QueryError("execution_error", "Projected field keys must be distinct.")
                    items = list(state.value.entity_ids) if state.shape == "entities" else state.value.rows
                    rows = [{ref.key: self._required(item, ref, state) for ref in op.fields} for item in items]
                    cells = [{ref.key: self._support(item, ref, state) for ref in op.fields} for item in items]
                    state.value = m.TableValue(kind="table", columns=[m.TableColumn(key=ref.key,
                        label=self.properties[ref.key].labels[0] if ref.kind == "property" and self.properties[ref.key].labels
                        else m.LocalizedText(text=ref.key)) for ref in op.fields], rows=rows)
                    state.cells = cells
                    state.shape = "table"
                elif op.kind == "rank":
                    items = list(state.value.entity_ids) if state.shape == "entities" else state.value.rows
                    ranked = [(index, item, self._required(item, op.field, state)) for index, item in enumerate(items)]
                    signatures = {self._comparison_signature(value) for _, _, value in ranked}
                    if len(signatures) > 1:
                        raise QueryError("conflicting_evidence", "Ranking values have incompatible types, dimensions or quantity definitions.")
                    ranked.sort(key=lambda pair: self._scalar(pair[2]), reverse=op.direction == "descending")
                    retained_ranked = ranked[:op.limit]
                    if ranked and len(ranked) > op.limit:
                        cutoff_value = ranked[op.limit - 1][2]
                        cutoff = self._scalar(cutoff_value)
                        extra_ties, roundoff_tolerance = 0, None
                        for candidate in ranked[op.limit:]:
                            _, _, value = candidate
                            if op.include_ties:
                                equal, tolerance = self._ranking_tie(value, cutoff_value)
                                if tolerance is not None:
                                    roundoff_tolerance = tolerance
                                extra_ties += equal
                                if equal:
                                    retained_ranked.append(candidate)
                            else:
                                extra_ties += self._scalar(value) == cutoff
                        if roundoff_tolerance is not None:
                            state.notes.append(f"Cutoff ties for estimated derived quantities allow {float(roundoff_tolerance):.17g} in normalized SI units for computation round-off (64 double-precision ULPs).")
                        if extra_ties:
                            if op.include_ties:
                                state.notes.append(f"{extra_ties} additional tied source row(s) are included at the requested ranking cutoff.")
                            else:
                                state.notes.append(f"{extra_ties} additional source row(s) tie at the requested ranking cutoff; stable source order determines which tied rows appear.")
                    if op.include_ties and len(retained_ranked) > 100:
                        raise QueryError("needs_clarification",
                            f"The ranking including every cutoff tie would return {len(retained_ranked)} rows, above the bounded 100-output limit. Narrow the source selection or request a smaller rank limit; tied rows have not been silently removed.",
                            fact_ids=sorted(state.facts), anchor_ids=sorted(state.anchors))
                    retained = [item for _, item, _ in retained_ranked]
                    if state.shape == "entities":
                        state.members = set(retained)
                        # References carry rank order; later projection preserves it.
                        state.value = m.ReferencesValue(kind="references", entity_ids=retained)
                    else:
                        state.cells = [state.cells[index] for index, _, _ in retained_ranked]
                        state.value = state.value.model_copy(update={"rows": retained})
                        state.members = set().union(*(support.members for row in state.cells for support in row.values()))
                        excluded_id = "set:" + step.id + ":excluded"
                        excluded = previous.members - state.members
                        sets.append(m.EntitySet(id=excluded_id, scope=plan.scope, count_policy=POLICIES["all_matches"],
                                                count=len(excluded), entity_ids=sorted(excluded)))
            set_id = "set:" + step.id
            operation_hash = hashlib.sha256(json.dumps(op.model_dump(mode="json"), sort_keys=True).encode()).hexdigest()[:24]
            state.operation_keys.append(op.kind + ":" + operation_hash)
            sets.append(m.EntitySet(id=set_id, scope=plan.scope, count_policy=state.policy,
                                    count=len(state.members), entity_ids=sorted(state.members)))
            state.anchors.update(a for e in state.members for a in self.entities[e].provenance.anchor_ids)
            if state.shape == "entities" and op.kind != "rank":
                state.value = m.ReferencesValue(kind="references", entity_ids=sorted(state.members))
            operation = (op.method if op.kind == "aggregate" else
                         op.operator if op.kind == "arithmetic" else "project" if op.kind == "table_calculate" else op.kind)
            if op.kind == "aggregate" and op.group_by:
                operation = "group_by"
            calculations.extend(state.internal_nodes)
            for index, (converted, support) in enumerate(state.conversions):
                node_id = f"calculation:{step.id}:convert:{index}"
                calculations.append(m.CalculationNode(id=node_id, operation="convert_unit",
                    fact_ids=sorted(support.facts), anchor_ids=sorted(support.anchors), output=converted,
                    quality=converted.quality, rule_key="ifc.units.v1"))
                inputs.append(node_id)
            calculations.append(m.CalculationNode(id="calculation:" + step.id, plan_step_id=step.id,
                operation=operation, input_node_ids=inputs, fact_ids=sorted(state.facts),
                included_set_id=set_id, excluded_set_id=excluded_id, anchor_ids=sorted(state.anchors), output=state.value,
                quality="estimated" if state.candidate_members else state.quality,
                rule_key="ifc.arithmetic.v1" if op.kind == "arithmetic" else
                         "ifc.partial-nonnegative-sum.v1" if op.kind == "aggregate" and op.missing_values == "partial" else
                         "ifc.rank.cutoff_ties.v1" if op.kind == "rank" and op.include_ties else state.policy.rule_key,
                spatial_evidence=[m.SpatialEvaluation(**record) for record in state.spatial_records],
                measurement_evidence=[m.MeasurementEvaluation(**record) for record in state.measurement_records],
                network_evidence=[m.NetworkEvaluation(**record) for record in state.network_records],
                material_evidence=[m.MaterialEvaluation(**record) for record in state.material_records],
                route_evidence=[m.RouteEvaluation(**record) for record in state.route_records]))
            states[step.id] = state
        claims = []
        for output_key, step_id in plan.outputs.items():
            state = states[step_id]
            coverage = self._coverage(plan, state)
            bindings = [m.EvidenceBinding(calculation_id="calculation:" + step_id, fact_ids=sorted(state.facts),
                        anchor_ids=sorted(state.anchors), entity_set_ids=["set:" + step_id],
                        evidence_kind="candidate" if state.candidate_members else "verified")]
            if isinstance(state.value, m.TableValue):
                for row_index, row in enumerate(state.value.rows):
                    for column, value in row.items():
                        support = state.cells[row_index][column]
                        suffix = hashlib.sha256((output_key + str(row_index) + column).encode()).hexdigest()[:24]
                        cell_set_id, cell_node_id = "set:cell:" + suffix, "calculation:cell:" + suffix
                        sets.append(m.EntitySet(id=cell_set_id, scope=plan.scope, count_policy=state.policy,
                            count=len(support.members), entity_ids=sorted(support.members)))
                        calculations.append(m.CalculationNode(id=cell_node_id, operation=support.operation,
                            input_node_ids=support.input_node_ids,
                            fact_ids=sorted(support.facts), included_set_id=cell_set_id, anchor_ids=sorted(support.anchors),
                            output=value, quality="estimated" if support.evidence_kind == "candidate" else state.quality, rule_key=state.policy.rule_key))
                        pointer = f"/rows/{row_index}/" + column.replace("~", "~0").replace("/", "~1")
                        bindings.append(m.EvidenceBinding(value_path=pointer, calculation_id=cell_node_id,
                            fact_ids=sorted(support.facts), anchor_ids=sorted(support.anchors), entity_set_ids=[cell_set_id],
                            evidence_kind=support.evidence_kind))
            claims.append(m.Claim(id="claim:" + output_key, output_key=output_key, name=output_key,
                scope=plan.scope, concept_ids=sorted(state.concepts), property_keys=sorted(state.properties),
                value=state.value, quality="estimated" if state.candidate_members else state.quality, coverage_ids=[coverage.id], count_policy=state.policy,
                evidence=bindings))
        issues = {issue.message.text: issue for step_id in plan.outputs.values() for issue in states[step_id].issues}
        notes = list(dict.fromkeys(note for step_id in plan.outputs.values() for note in states[step_id].notes))
        result = m.QueryResult(id="result:" + plan.id.removeprefix("plan:"), request_id=plan.request_id, plan_id=plan.id,
            status="partial" if issues else "answered", claims=claims, entity_sets=sets, calculations=calculations,
            issues=list(issues.values()), explanation=m.LocalizedText(text=" ".join(notes)) if notes else None,
            executor_version=EXECUTOR_VERSION, metrics=m.ExecutionMetrics(latency_ms=(perf_counter() - started) * 1000, cache_hit=self.cache_hit))
        validate_result(result, self.bundle, plan)
        return result

    def _coverage(self, plan, state):
        unresolved = state.unresolved | {entity_id for issue in state.issues
            if issue.code in {"incomplete_coverage", "missing_information", "conflicting_evidence"}
            for entity_id in issue.entity_ids}
        data = [plan.scope.model_dump(), sorted(state.concepts), sorted(state.properties), state.policy.model_dump(),
                state.completeness, state.coverage_explanation, sorted(state.anchors), state.operation_keys,
                state.spatial_records, sorted(unresolved), sorted(state.candidate_members), state.coverage_complete]
        identifier = "coverage:" + hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()[:24]
        existing = next((c for c in self.bundle.coverage if c.id == identifier), None)
        if existing:
            return existing
        coverage = m.Coverage(id=identifier, scope=plan.scope, concept_ids=sorted(state.concepts),
            property_keys=sorted(state.properties), count_policy=state.policy,
            completeness=state.completeness if state.coverage_complete and not unresolved and not state.candidate_members else "partial",
            operation_keys=state.operation_keys,
            examined_entity_ids=sorted({record["subject_id"] for record in state.spatial_records}),
            unresolved_entity_ids=sorted(unresolved), candidate_entity_ids=sorted(state.candidate_members),
            explanation=state.coverage_explanation or ("Evaluation of the specified operations and source inputs; unresolved and candidate spatial objects are listed separately. "
                        "Applies to this supplied model revision and query universe; physical building completeness is unverified."),
            provenance=m.Provenance(run_id=self.bundle.runs[0].id, method="computed", anchor_ids=sorted(state.anchors)))
        self.bundle.coverage.append(coverage)
        return coverage

    def _read(self, item, ref, state):
        if isinstance(item, dict):
            if ref.kind != "result_column" or ref.key not in item:
                raise QueryError("execution_error", "Table fields must reference an existing result_column.")
            return item[ref.key]
        entity = self.entities[item]
        if ref.kind == "property":
            self.ensure_fields([item], [ref.key])
            state.properties.add(ref.key)
            facts = self.facts[item, ref.key]
            if any(f.status in {"ambiguous", "unknown", "not_extracted"} for f in facts):
                raise QueryError("incomplete_coverage", f"Property {ref.key!r} could not be extracted unambiguously.", [item], [f.id for f in facts])
            present = [f for f in facts if f.status == "present"]
            if not present:
                return None
            values = {self._value_key(f.value) for f in present}
            if len(values) != 1 or any(f.status != "present" for f in facts):
                raise QueryError("conflicting_evidence", f"Conflicting values for {ref.key!r}.", [item], [f.id for f in facts])
            state.facts.update(f.id for f in present)
            state.anchors.update(a for f in present for a in f.provenance.anchor_ids)
            if isinstance(present[0].value, m.QuantityValue):
                state.anchors.update(present[0].value.unit_anchor_ids)
            if isinstance(present[0].value, m.QuantityValue) and present[0].value.quality not in {"exact", "estimated"}:
                raise QueryError("unsupported_operation", "Estimated source quantities need quality propagation before execution.")
            if isinstance(present[0].value, m.QuantityValue) and present[0].value.quality == "estimated":
                state.quality = "estimated"
            return present[0].value
        if ref.kind == "entity_id":
            return m.ReferencesValue(kind="references", entity_ids=[item])
        if ref.kind == "label":
            return m.TextValue(kind="text", value=m.LocalizedText(text=entity.labels[0].text if entity.labels else ""))
        if ref.kind == "native_identifier":
            if ref.key not in {"step_id", "ifc_guid"}:
                raise QueryError("unsupported_operation", f"Unsupported native identifier {ref.key!r}.")
            selectors = [self.anchors[a].selector for a in self.entity_anchors[item]]
            values = {s.value for s in selectors if s.kind == ref.key and not s.property_path}
            if len(values) > 1:
                raise QueryError("conflicting_evidence", "Multiple native identifiers.", [item])
            return m.TextValue(kind="text", value=m.LocalizedText(text=next(iter(values)))) if values else None
        raise QueryError("unsupported_operation", f"Unsupported field kind {ref.kind!r}.")

    def _required(self, item, ref, state):
        value = self._read(item, ref, state)
        if value is None:
            raise QueryError("missing_information", f"Field {ref.key!r} is missing; a complete answer cannot be calculated.",
                             [item] if isinstance(item, str) else [])
        return value

    def _support(self, item, ref, state):
        if isinstance(item, dict):
            for row, cells in zip(state.value.rows, state.cells):
                if row is item:
                    return cells[ref.key]
            raise QueryError("execution_error", "Derived cell has no source evidence.")
        source_facts = self.facts[item, ref.key] if ref.kind == "property" else []
        facts = [fact for fact in source_facts if fact.status == "present"]
        anchors = set(self.entity_anchors[item])
        # Unavailable group cells can cite the observed null/unextracted source
        # record while successful numeric calculations consume present facts only.
        anchors.update(a for f in source_facts for a in f.provenance.anchor_ids)
        anchors.update(a for f in facts if isinstance(f.value, m.QuantityValue) for a in f.value.unit_anchor_ids)
        return _Support({item}, {f.id for f in facts}, anchors,
                        evidence_kind="candidate" if item in state.candidate_members else "verified")

    def _combined_support(self, items, ref, state, operation="lookup"):
        supports = [self._support(item, ref, state) if ref else _Support({item} if isinstance(item, str) else set()) for item in items]
        return _Support(set().union(*(s.members for s in supports)), set().union(*(s.facts for s in supports)),
                        set().union(*(s.anchors for s in supports)), operation,
                        evidence_kind="candidate" if any(s.evidence_kind == "candidate" for s in supports) else "verified")

    def _check_predicate(self, predicate):
        if predicate is None:
            return
        if predicate.kind == "spatial":
            raise QueryError("unsupported_operation", "Spatial predicates require a geometry executor.")
        if predicate.kind in {"all", "any", "not"}:
            for operand in predicate.operands:
                self._check_predicate(operand)

    def _predicate(self, entity, predicate, state, scope_members):
        if predicate.kind in {"all", "any", "not"}:
            if predicate.kind == "not":
                value = self._predicate(entity, predicate.operands[0], state, scope_members)
                return None if value is None else not value
            unknown, errors = False, []
            for child in predicate.operands:
                try:
                    value = self._predicate(entity, child, state, scope_members)
                except QueryError as error:
                    if error.code not in {"missing_information", "incomplete_coverage", "conflicting_evidence"}:
                        raise
                    # A different decisive operand can establish the Boolean
                    # result without resolving this source field. Otherwise
                    # retain its real error rather than converting it to false.
                    errors.append(error)
                    value = None
                if predicate.kind == "all" and value is False:
                    return False
                if predicate.kind == "any" and value is True:
                    return True
                unknown |= value is None
            if errors:
                raise errors[0]
            return None if unknown else predicate.kind == "all"
        if predicate.kind == "related_to":
            if predicate.predicate == "has_material" and predicate.direction == "outgoing":
                self._material_typing(entity, state)
            graph = self.graphs[predicate.predicate, predicate.direction]
            matches = graph[entity] & set(predicate.entity_ids) & scope_members
            if not matches and set(predicate.entity_ids) - scope_members:
                raise QueryError("incomplete_coverage", "The relationship filter requires target objects outside the captured scope.",
                                 [entity], anchor_ids=sorted(self.entity_anchors[entity]))
            state.anchors.update(anchor for related in matches
                for anchor in self.edge_anchors[predicate.predicate, predicate.direction, entity, related])
            return bool(matches)
        if predicate.kind == "spatial":
            raise QueryError("unsupported_operation", "Spatial predicates require a geometry executor.")
        actual = self._read(entity, predicate.field, state)
        if predicate.kind == "field_present":
            return actual is not None
        if actual is None:
            return None  # Three-valued logic: NOT(missing = x) is still unknown.
        expected = predicate.value
        if predicate.operator == "in":
            if not isinstance(expected, m.ListValue):
                raise QueryError("execution_error", "The 'in' operator requires a typed list.")
            return any(self._compare(actual, value, "eq") for value in expected.items)
        return self._compare(actual, expected, predicate.operator)

    def _predicate_guard(self, entity, predicate, state, scope_members):
        """Three-valued result before consulting deferred source properties."""
        if predicate.kind in {"all", "any", "not"}:
            values = [self._predicate_guard(entity, child, state, scope_members) for child in predicate.operands]
            if predicate.kind == "not":
                return None if values[0] is None else not values[0]
            if predicate.kind == "all":
                return False if False in values else None if None in values else True
            return True if True in values else None if None in values else False
        if predicate.kind in {"compare", "field_present"} and predicate.field.kind == "property":
            return None
        if predicate.kind == "related_to" and predicate.predicate == "has_material" and entity in self.type_alternatives:
            # Resolving contradictory inherited materials can require deferred
            # source fields; let a cheaper identity guard exclude the object.
            return None
        if predicate.kind == "related_to" and set(predicate.entity_ids) - scope_members:
            matches = self.graphs[predicate.predicate, predicate.direction][entity] & set(predicate.entity_ids) & scope_members
            if not matches:
                return None
        return self._predicate(entity, predicate, state, scope_members)

    def _typing_support(self, identifier):
        candidates = self.graphs["typed_by", "outgoing"].get(identifier, ())
        anchors = {anchor for candidate in candidates for anchor in self.entity_anchors[candidate]}
        anchors.update(anchor for candidate in candidates for anchor in self.edge_anchors["typed_by", "outgoing", identifier, candidate])
        facts = {fact.id for candidate in candidates for fact in self.facts[candidate, CLASS_KEY] if fact.status == "present"}
        return facts, anchors

    def _material_typing(self, identifier, state):
        if identifier not in self.type_alternatives:
            return
        key = property_key("SourceMaterial", "CompositionComplete")
        if key not in self.properties:
            return
        self.ensure_fields([identifier], [key])
        facts = self.facts.get((identifier, key), ())
        if any(fact.status in {"ambiguous", "unknown", "not_extracted"} for fact in facts):
            support, anchors = self._typing_support(identifier)
            anchors.update(anchor for fact in facts for anchor in fact.provenance.anchor_ids)
            raise QueryError("conflicting_evidence", "Conflicting native type assignments do not establish one inherited material composition.",
                             [identifier], [*sorted(support), *[fact.id for fact in facts]], anchor_ids=sorted(anchors))

    def _compare(self, actual, expected, operator):
        if self._comparison_signature(actual) != self._comparison_signature(expected):
            raise QueryError("conflicting_evidence", "Cannot compare incompatible types, dimensions or quantity definitions.")
        left, right = self._scalar(actual), self._scalar(expected)
        if operator == "contains":
            if not isinstance(left, str) or not isinstance(right, str):
                raise QueryError("unsupported_operation", "contains currently supports text fields only.")
            return right in left
        operations = {"eq": lambda: left == right, "ne": lambda: left != right,
                      "lt": lambda: left < right, "lte": lambda: left <= right,
                      "gt": lambda: left > right, "gte": lambda: left >= right}
        return operations[operator]()

    def _comparison_signature(self, value):
        if isinstance(value, m.QuantityValue):
            if value.unit_id is None:
                raise QueryError("missing_information", "A measurement has unresolved units.")
            return value.kind, value.quantity_kind, value.basis, self.units[value.unit_id].dimension
        return value.kind,

    def _ranking_tie(self, value, cutoff):
        """Exact source ties, plus bounded round-off for estimated derivations."""
        left, right = self._scalar(value), self._scalar(cutoff)
        if left == right:
            return True, None
        if not all(isinstance(item, m.QuantityValue) and item.quality == "estimated"
                   and item.unit_resolution == "derived" and item.source_value_type is None
                   for item in (value, cutoff)):
            return False, None
        try:
            numeric = float(left), float(right)
        except (OverflowError, ValueError):
            return False, None
        if (not all(math.isfinite(item) for item in numeric)
                or any(number == 0 and original != 0 for number, original in zip(numeric, (left, right)))):
            return False, None
        tolerance = Decimal.from_float(64 * math.ulp(numeric[1]))
        with localcontext() as context:
            context.prec = 80
            return abs(left - right) <= tolerance, tolerance

    def _scalar(self, value):
        if isinstance(value, m.QuantityValue):
            self._comparison_signature(value)
            unit = self.units[value.unit_id]
            with localcontext() as context:
                context.prec = 80
                return Decimal(value.magnitude) * Decimal(unit.si_multiplier) + Decimal(unit.si_offset)
        if isinstance(value, m.CountValue):
            return Decimal(value.value)
        if isinstance(value, m.TextValue):
            return value.value.text
        if isinstance(value, m.BooleanValue):
            return value.value
        if isinstance(value, m.ReferencesValue):
            return tuple(value.entity_ids)
        raise QueryError("unsupported_operation", "This value type has no scalar comparison.")

    def _value_key(self, value):
        if isinstance(value, (m.ListValue, m.RecordValue, m.TableValue, m.UnavailableValue)):
            return value.kind, json.dumps(value.model_dump(mode="json"), ensure_ascii=False, sort_keys=True)
        if isinstance(value, m.QuantityValue) and value.unit_id is None:
            return value.kind, value.quantity_kind, value.basis, None, Decimal(value.magnitude)
        return self._comparison_signature(value), self._scalar(value)

    def _aggregate(self, state, op):
        if state.unresolved or state.candidate_members or not state.coverage_complete:
            raise QueryError("incomplete_coverage", "An exact aggregate cannot be established from unresolved or candidate spatial relationships.",
                             sorted(state.unresolved | state.candidate_members))
        if state.shape == "table" and op.method == "count":
            raise QueryError("unsupported_operation", "Counting derived table rows needs a separate evidence grain.")
        items = list(state.value.entity_ids) if state.shape == "entities" else state.value.rows
        groups = defaultdict(list)
        group_values = {}
        missing_groups = set()
        for item in items:
            values = []
            for ref in op.group_by:
                try:
                    value = self._required(item, ref, state)
                except QueryError as error:
                    if op.missing_groups != "unclassified" or error.code not in {"missing_information", "incomplete_coverage", "conflicting_evidence"}:
                        raise
                    source_facts = self.facts[item, ref.key] if isinstance(item, str) and ref.kind == "property" else []
                    reason = ("ambiguous" if error.code in {"incomplete_coverage", "conflicting_evidence"} else
                              "explicit_null" if source_facts and all(fact.status == "explicit_null" for fact in source_facts) else "not_in_source")
                    value = m.UnavailableValue(kind="unavailable", reason=reason,
                        explanation=f"Unclassified: no unambiguous recorded value for {ref.key}.")
                    if isinstance(item, str):
                        missing_groups.add(item)
                    else:
                        missing_groups.update(member for support in state.cells[state.value.rows.index(item)].values() for member in support.members)
                    state.anchors.update(anchor for fact in source_facts for anchor in fact.provenance.anchor_ids)
                values.append(value)
            key = tuple(self._value_key(value) for value in values)
            groups[key].append(item)
            group_values[key] = values
        if missing_groups:
            state.issues.append(m.Issue(code="needs_clarification", entity_ids=sorted(missing_groups),
                message=m.LocalizedText(text="The distribution includes explicit unclassified bins for missing, null or ambiguous group values. Bin counts cover every selected occurrence; the source classification needs clarification.")))
            state.notes.append("Unclassified bins retain selected objects with missing source group labels; they are included in the inventory counts.")
        if not op.group_by:
            return self._reduce(items, state, op)
        rows = []
        cells = []
        for key in sorted(groups, key=repr):
            row = {ref.key: value for ref, value in zip(op.group_by, group_values[key])}
            row[op.value_key] = self._reduce(groups[key], state, op)
            rows.append(row)
            evidence = {ref.key: self._combined_support(groups[key], ref, state) for ref in op.group_by}
            evidence[op.value_key] = self._combined_support(groups[key], op.field, state, op.method)
            cells.append(evidence)
        state.cells = cells
        return m.TableValue(kind="table", columns=[m.TableColumn(key=key, label=m.LocalizedText(text=key))
                           for key in [*[ref.key for ref in op.group_by], op.value_key]], rows=rows)

    def _reduce(self, items, state, op):
        if op.method == "count":
            return m.CountValue(kind="count", value=len(items))
        if not items:
            raise QueryError("missing_information", "No matching objects supply a measurement.")
        values = [self._required(item, op.field, state) for item in items]
        if not all(isinstance(value, (m.QuantityValue, m.CountValue)) for value in values):
            raise QueryError("unsupported_operation", "Numeric aggregation requires numeric values.")
        signatures = {self._comparison_signature(value) for value in values}
        if len(signatures) != 1:
            raise QueryError("conflicting_evidence", "Aggregate values have incompatible dimensions or quantity definitions.")
        first = values[0]
        target = None
        if isinstance(first, m.QuantityValue):
            target_id = op.output_unit_id or SI_TARGETS.get(first.quantity_kind) or first.unit_id
            target = self.units[target_id]
            numbers = [convert(value.magnitude, self.units[value.unit_id], target) for value in values]
            for item, value, number in zip(items, values, numbers):
                if value.unit_id != target.id:
                    converted = m.QuantityValue(kind="quantity", magnitude=decimal_string(number), unit_id=target.id,
                        quantity_kind=value.quantity_kind, basis=value.basis, unit_resolution="derived", quality=value.quality)
                    state.conversions.append((converted, self._support(item, op.field, state)))
        else:
            numbers = [Decimal(value.value) for value in values]
        with localcontext() as context:
            context.prec = max(80, sum(len(str(value)) for value in numbers) + 32)
            total = sum(numbers, Decimal(0))
            number = {"sum": lambda: total, "mean": lambda: total / len(numbers),
                      "min": lambda: min(numbers), "max": lambda: max(numbers)}[op.method]()
        if target is None and op.method != "mean":
            return m.CountValue(kind="count", value=int(number))
        if target is None:
            target = self.units["unit:1"]
        return m.QuantityValue(kind="quantity", magnitude=decimal_string(number), unit_id=target.id,
            quantity_kind=first.quantity_kind if isinstance(first, m.QuantityValue) else "number",
            basis=first.basis if isinstance(first, m.QuantityValue) else "modeled", unit_resolution="derived", quality=state.quality)

    def inspect(self) -> dict:
        classes = defaultdict(int)
        storeys = []
        for entity in self.entities.values():
            for fact in self.facts[entity.id, CLASS_KEY]:
                if isinstance(fact.value, m.TextValue):
                    classes[fact.value.value.text] += 1
            if entity.kind == "storey":
                storeys.append({"id": entity.id, "names": [label.text for label in entity.labels]})
        return {"schema": self.schema, "asset": self.bundle.assets[0].model_dump(mode="json"),
                "project_id": self.bundle.projects[0].id, "document_id": self.bundle.documents[0].id,
                "classes": dict(sorted(classes.items())), "storeys": storeys,
                "properties": [p.model_dump(mode="json") for p in self.bundle.properties],
                "capabilities": self.capabilities.model_dump(mode="json"), "warnings": self.warnings,
                "cache_hit": self.cache_hit}
