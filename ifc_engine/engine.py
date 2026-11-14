"""A bounded, deterministic executor. Plans never contain executable code."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from decimal import Decimal, localcontext
import hashlib
import json
from pathlib import Path
from time import perf_counter

from contracts import models as m
from contracts.validation import validate_bundle, validate_plan, validate_result
from . import __version__
from .catalog import CLASS_KEY, CONCEPT_CLASSES, POLICIES, RELATIONS
from .ingest import load_ifc
from .units import SI_TARGETS, convert, decimal_string
from .scalar_math import ScalarArithmeticError, scalar_arithmetic

EXECUTOR_VERSION = "ifc-engine/" + __version__
OPERATIONS = ["select", "traverse", "spatial_query", "related_entities", "project", "rank", *["aggregate." + name for name in ["count", "sum", "mean", "min", "max"]],
              *["arithmetic." + name for name in ["add", "subtract", "multiply", "divide"]]]


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
        self.entities = {item.id: item for item in bundle.entities}
        self.properties = {item.key: item for item in bundle.properties}
        self.units = {item.id: item for item in bundle.units}
        self.anchors = {item.id: item for item in bundle.anchors}
        self.entity_anchors = defaultdict(set)
        for representation in bundle.representations:
            self.entity_anchors[representation.entity_id].update(representation.anchor_ids)
        self.facts = defaultdict(list)
        for fact in bundle.facts:
            self.facts[fact.subject_id, fact.property_key].append(fact)
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
        self.capabilities = m.CapabilityManifest(
            executor_version=EXECUTOR_VERSION, operations=OPERATIONS, relation_predicates=list(RELATIONS),
            property_keys=sorted(self.properties), concept_ids=sorted(self.concept_ids), supported_formats=["ifc"],
            limitations=[
                "Single IFC revision; only source_records and modeled_objects scopes are supported.",
                "Counts describe supported records in the supplied model, not physical building completeness.",
                "Only scalar attributes, single-value properties and simple quantities are extracted.",
                "Native spatial topology, bounded boundary/room geometry and scalar decimal arithmetic are supported when source prerequisites exist; metric spatial predicates and routes are not implemented.",
                "Scalar arithmetic preserves dimensions and uncertainty; unsupported currency products, unsourced factors and offset-unit arithmetic remain unavailable.",
                "Missing values fail explicitly; exterior-door lower-bound counts are supported, while unresolved topology aggregates and derived table-row counts are not.",
                "Only the registered IFC occurrence, topmost-assembly and leaf policies are supported.",
                "Ranking is bounded; ties use stable entity/row order and do not establish a unique extremum.",
            ])

    @classmethod
    def open(cls, path: str | Path, **kwargs):
        loaded = load_ifc(path, **kwargs)
        engine = cls(loaded.bundle, schema=loaded.schema, warnings=loaded.warnings, cache_hit=loaded.cache_hit)
        from .geometry import GeometryProvider
        engine.geometry = GeometryProvider(Path(path), loaded.bundle.assets[0].sha256)
        return engine

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
            capability = ("aggregate." + op.method if op.kind == "aggregate"
                          else "arithmetic." + op.operator if op.kind == "arithmetic" else op.kind)
            if capability not in OPERATIONS:
                raise QueryError("unsupported_operation", f"Operation {capability!r} has no local executor yet.")
            if op.kind == "select" and op.count_policy not in POLICIES.values():
                raise QueryError("unsupported_operation", "This counting rule has no registered IFC implementation.")
            if op.kind == "aggregate" and op.missing_values != "fail":
                raise QueryError("unsupported_operation", "Partial numeric aggregates are not implemented.")
            if op.kind == "select":
                self._check_predicate(op.where)
                self._check_predicate(op.exclude)
        try:
            validate_plan(plan, self.bundle, self.capabilities)
        except ValueError as exc:
            raise QueryError("execution_error", "Invalid query plan: " + str(exc)) from exc
        scope_members = {e.id for e in self.entities.values() if e.project_id == plan.scope.project_id and e.document_id in plan.scope.document_ids}
        if plan.scope.entity_ids:
            scope_members &= _reachable(self.children, plan.scope.entity_ids)
        if plan.scope.exact_entity_ids is not None:
            scope_members &= set(plan.scope.exact_entity_ids)
        states, calculations, sets = {}, [], []
        for step in plan.steps:
            op = step.operation
            excluded_id = None
            if op.kind == "select":
                allowed = _reachable(self.concept_children, op.concept_ids)
                members = {e for e in scope_members if (not allowed or allowed.intersection(self.entities[e].concept_ids))
                           and (not op.entity_kinds or self.entities[e].kind in op.entity_kinds)}
                state = _State(None, members, op.count_policy, set(op.concept_ids))
                selected = set()
                for entity_id in sorted(members):
                    included = True if op.where is None else self._predicate(entity_id, op.where, state, scope_members)
                    excluded = False if op.exclude is None else self._predicate(entity_id, op.exclude, state, scope_members)
                    # Unknown comparisons cannot establish exhaustive filtered
                    # counts. An explicit field_present condition can still
                    # deliberately restrict a query to known source values.
                    if included is None and excluded is not True or excluded is None and included is not False:
                        raise QueryError("missing_information", "A filter depends on a missing source value; a complete selection cannot be established.", [entity_id])
                    if included is True and excluded is False:
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
                operands = [states[key] for key in op.input_step_ids]
                if any(item.shape != "scalar" for item in operands):
                    raise QueryError("unsupported_operation", "Arithmetic currently accepts scalar results only.")
                try:
                    value, quality = scalar_arithmetic([item.value for item in operands], op.operator,
                        self.units, op.output_unit_id, ["estimated" if item.candidate_members else item.quality for item in operands])
                except ScalarArithmeticError as exc:
                    raise QueryError(exc.code, str(exc),
                        sorted(set().union(*(item.members for item in operands))),
                        sorted(set().union(*(item.facts for item in operands)))) from exc
                policies = [item.policy for item in operands]
                if isinstance(value, m.CountValue) and any(policy != policies[0] for policy in policies):
                    raise QueryError("needs_clarification", "Arithmetic counts require the same counting grain and hierarchy.")
                state = _State(value=value, members=set().union(*(item.members for item in operands)),
                    policy=policies[0] if all(policy == policies[0] for policy in policies) else POLICIES["all_matches"],
                    concepts=set().union(*(item.concepts for item in operands)),
                    properties=set().union(*(item.properties for item in operands)),
                    facts=set().union(*(item.facts for item in operands)),
                    anchors=set().union(*(item.anchors for item in operands)), shape="scalar", quality=quality,
                    notes=list(dict.fromkeys(note for item in operands for note in item.notes)),
                    issues=list({issue.message.text: issue for item in operands for issue in item.issues}.values()),
                    completeness="complete" if all(item.completeness == "complete" for item in operands) else "partial",
                    coverage_complete=all(item.coverage_complete for item in operands),
                    spatial_records=[record for item in operands for record in item.spatial_records],
                    unresolved=set().union(*(item.unresolved for item in operands)),
                    candidate_members=set().union(*(item.candidate_members for item in operands)),
                    operation_keys=list(dict.fromkeys(key for item in operands for key in item.operation_keys)))
                inputs = ["calculation:" + key for key in op.input_step_ids]
                if quality != 'exact' and not state.issues:
                    state.issues.append(m.Issue(code='incomplete_coverage', message=m.LocalizedText(
                        text='The arithmetic result is qualified because its source inputs are uncertain or finite decimal rounding was required.')))
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
                inputs = ["calculation:" + op.input_step_id]
                incomplete_membership = (state.unresolved or state.candidate_members or not state.coverage_complete
                                         or any(issue.code == "incomplete_coverage" for issue in state.issues))
                if state.quality != "exact" and incomplete_membership and (op.kind != "aggregate" or op.method != "count"):
                    raise QueryError("unsupported_operation", "An incomplete exterior-door selection supports occurrence counting only; other operations need complete membership.")
                if op.kind == "spatial_query":
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
                    graph = self.graphs[op.predicate, op.direction]
                    members, frontier = set(), set(state.members)
                    for _ in range(op.max_depth if op.recursive else 1):
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
                    state.value = self._aggregate(state, op)
                    state.shape = "table" if isinstance(state.value, m.TableValue) else "scalar"
                elif op.kind == "project":
                    if len({ref.key for ref in op.fields}) != len(op.fields):
                        raise QueryError("execution_error", "Projected field keys must be distinct.")
                    items = list(state.value.entity_ids) if state.shape == "entities" else state.value.rows
                    rows = [{ref.key: self._required(item, ref, state) for ref in op.fields} for item in items]
                    cells = [{ref.key: self._support(item, ref, state) for ref in op.fields} for item in items]
                    state.value = m.TableValue(kind="table", columns=[m.TableColumn(key=ref.key, label=m.LocalizedText(text=ref.key)) for ref in op.fields], rows=rows)
                    state.cells = cells
                    state.shape = "table"
                elif op.kind == "rank":
                    items = list(state.value.entity_ids) if state.shape == "entities" else state.value.rows
                    ranked = [(index, item, self._required(item, op.field, state)) for index, item in enumerate(items)]
                    if any(isinstance(value, m.QuantityValue) and value.quality != "exact" for _, _, value in ranked):
                        raise QueryError("incomplete_coverage", "Uncertain source quantities cannot establish an exact ranking.")
                    signatures = {self._comparison_signature(value) for _, _, value in ranked}
                    if len(signatures) > 1:
                        raise QueryError("conflicting_evidence", "Ranking values have incompatible types, dimensions or quantity definitions.")
                    ranked.sort(key=lambda pair: self._scalar(pair[2]), reverse=op.direction == "descending")
                    retained = [item for _, item, _ in ranked[:op.limit]]
                    if state.shape == "entities":
                        state.members = set(retained)
                        # References carry rank order; later projection preserves it.
                        state.value = m.ReferencesValue(kind="references", entity_ids=retained)
                    else:
                        state.cells = [state.cells[index] for index, _, _ in ranked[:op.limit]]
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
            operation = op.method if op.kind == "aggregate" else op.operator if op.kind == "arithmetic" else op.kind
            if op.kind == "aggregate" and op.group_by:
                operation = "group_by"
            for index, (converted, support) in enumerate(state.conversions):
                node_id = f"calculation:{step.id}:convert:{index}"
                calculations.append(m.CalculationNode(id=node_id, operation="convert_unit",
                    fact_ids=sorted(support.facts), anchor_ids=sorted(support.anchors), output=converted,
                    quality=converted.quality, rule_key="ifc.units.v1"))
                inputs.append(node_id)
            calculations.append(m.CalculationNode(id="calculation:" + step.id, plan_step_id=step.id,
                operation=operation, input_node_ids=inputs, fact_ids=sorted(state.facts),
                included_set_id=None if op.kind == 'arithmetic' else set_id,
                excluded_set_id=excluded_id, anchor_ids=sorted(state.anchors), output=state.value,
                quality="estimated" if state.candidate_members else state.quality,
                rule_key="ifc.scalar_arithmetic.v1:" + op.operator if op.kind == "arithmetic" else state.policy.rule_key,
                spatial_evidence=[m.SpatialEvaluation(**record) for record in state.spatial_records]))
            states[step.id] = state
        claims = []
        for output_key, step_id in plan.outputs.items():
            state = states[step_id]
            arithmetic_output = next(step.operation.kind for step in plan.steps if step.id == step_id) == 'arithmetic'
            coverage = self._coverage(plan, state)
            bindings = [m.EvidenceBinding(calculation_id="calculation:" + step_id, fact_ids=sorted(state.facts),
                        anchor_ids=sorted(state.anchors), entity_set_ids=[] if arithmetic_output else ["set:" + step_id],
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
            if isinstance(present[0].value, m.QuantityValue) and present[0].value.quality != "exact":
                quality = present[0].value.quality
                state.quality = quality if state.quality in {"exact", quality} else "estimated"
                state.issues.append(m.Issue(code="missing_information", entity_ids=[item], fact_ids=[fact.id for fact in present],
                    message=m.LocalizedText(text="A source quantity is qualified as " + quality.replace("_", " ") + "; an exact quantity is unavailable.")))
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
        facts = [f for f in self.facts[item, ref.key] if f.status == "present"] if ref.kind == "property" else []
        anchors = set(self.entity_anchors[item])
        anchors.update(a for f in facts for a in f.provenance.anchor_ids)
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
            values = [self._predicate(entity, p, state, scope_members) for p in predicate.operands]
            if predicate.kind == "not":
                return None if values[0] is None else not values[0]
            if predicate.kind == "all":
                return False if False in values else None if None in values else True
            return True if True in values else None if None in values else False
        if predicate.kind == "related_to":
            graph = self.graphs[predicate.predicate, predicate.direction]
            matches = graph[entity] & set(predicate.entity_ids) & scope_members
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

    def _compare(self, actual, expected, operator):
        if any(isinstance(value, m.QuantityValue) and value.quality != "exact" for value in (actual, expected)):
            raise QueryError("incomplete_coverage", "Filtering or ranking comparisons require exact values; uncertain bounds cannot establish exact membership.")
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
        if isinstance(value, m.QuantityValue) and value.unit_id is None:
            return value.kind, value.quantity_kind, value.basis, None, Decimal(value.magnitude), value.quality
        return (self._comparison_signature(value), self._scalar(value), value.quality) if isinstance(value, m.QuantityValue) else (self._comparison_signature(value), self._scalar(value))

    def _aggregate(self, state, op):
        if state.unresolved or state.candidate_members or not state.coverage_complete:
            raise QueryError("incomplete_coverage", "An exact aggregate cannot be established from unresolved or candidate spatial relationships.",
                             sorted(state.unresolved | state.candidate_members))
        if state.shape == "table" and op.method == "count":
            raise QueryError("unsupported_operation", "Counting derived table rows needs a separate evidence grain.")
        items = list(state.value.entity_ids) if state.shape == "entities" else state.value.rows
        groups = defaultdict(list)
        group_values = {}
        for item in items:
            values = [self._required(item, ref, state) for ref in op.group_by]
            key = tuple(self._value_key(value) for value in values)
            groups[key].append(item)
            group_values[key] = values
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
