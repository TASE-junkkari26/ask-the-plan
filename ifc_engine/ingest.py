"""Extract an immutable IFC revision into the project's KnowledgeBundle."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

import ifcopenshell
import ifcopenshell.util.element as element_util
import ifcopenshell.util.unit as unit_util

from contracts import models as m
from contracts.validation import validate_bundle
from . import __version__
from .catalog import ATTRIBUTES, CLASS_KEY, CONCEPT_CLASSES, LENGTH_ATTRIBUTES, attribute_key, property_key
from .units import DIMENSIONS, SI_TARGETS, UNIT_TYPES, convert, decimal_string, source_unit, standard_units


def file_sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest() if hasattr(hashlib, "file_digest") else _hash_stream(stream)


def _hash_stream(stream) -> str:
    digest = hashlib.sha256()
    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
        digest.update(chunk)
    return digest.hexdigest()


def _id(kind: str, value: str) -> str:
    return kind + ":" + uuid5(NAMESPACE_URL, value).hex


@dataclass
class LoadedModel:
    bundle: m.KnowledgeBundle
    schema: str
    warnings: list[str]
    cache_hit: bool = False


def load_ifc(path: str | Path, *, cache_dir: str | Path | None = None,
             source_collection: str = "local", attribution: str = "unspecified",
             license: str = "unspecified") -> LoadedModel:
    """No network, geometry generation, or changes to the original IFC."""
    path = Path(path).resolve(strict=True)
    digest = file_sha256(path)
    config = {"engine": __version__, "ifcopenshell": ifcopenshell.version,
              "uri": path.as_uri(), "sha256": digest, "source_collection": source_collection,
              "attribution": attribution, "license": license}
    config_hash = hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()
    cached = Path(cache_dir) / (config_hash + ".json") if cache_dir else None
    if cached and cached.exists():
        data = json.loads(cached.read_text())
        bundle = m.KnowledgeBundle.model_validate(data["bundle"])
        validate_bundle(bundle)
        return LoadedModel(bundle, data["schema"], data["warnings"], True)
    model = ifcopenshell.open(str(path))
    result = _Extractor(model, path, digest, config_hash, config).extract()
    # Detect concurrent edits rather than attaching an old hash to new content.
    if file_sha256(path) != digest:
        raise ValueError("IFC changed during extraction; retry with an immutable revision")
    validate_bundle(result.bundle)
    if cached:
        cached.parent.mkdir(parents=True, exist_ok=True)
        from tempfile import NamedTemporaryFile
        with NamedTemporaryFile(mode="w", dir=cached.parent, suffix=".tmp", delete=False) as stream:
            temporary = Path(stream.name)
            json.dump({"schema": result.schema, "warnings": result.warnings,
                       "bundle": result.bundle.model_dump(mode="json")}, stream)
        temporary.replace(cached)
    return result


class _Extractor:
    def __init__(self, model, path, digest, config_hash, config):
        self.model, self.path, self.digest = model, path, digest
        self.schema = ifcopenshell.ifcopenshell_wrapper.schema_by_name(model.schema_identifier)
        projects = model.by_type("IfcProject")
        if len(projects) != 1:
            raise ValueError("initial IFC extractor requires exactly one IfcProject")
        project = projects[0]
        self.project_id = _id("project", project.GlobalId or path.as_uri())
        self.document_id = _id("document", path.as_uri() + digest)
        self.asset_id = _id("asset", path.as_uri() + digest)
        self.run_id = _id("run", config_hash)
        self.anchors, self.units, self.entities = {}, standard_units(), {}
        self.facts, self.relations, self.representations = [], [], []
        self.warnings = set()
        self.class_chains = {}
        self.property_labels = {}
        self.bundle_base = dict(
            projects=[m.Project(id=self.project_id, name=project.Name or path.stem)],
            documents=[m.Document(id=self.document_id, project_id=self.project_id,
                                  logical_key=_id("logical", path.as_uri()), revision=digest,
                                  title=[m.LocalizedText(text=path.name)])],
            assets=[m.Asset(id=self.asset_id, document_id=self.document_id, uri=path.as_uri(),
                            sha256=digest, format="ifc", media_type="application/x-step",
                            source_collection=config["source_collection"], attribution=config["attribution"],
                            license=config["license"])],
            runs=[m.ExtractionRun(id=self.run_id, tool="ask-the-plan.ifc_engine", version=__version__,
                                  model_revision=ifcopenshell.version, config_sha256=config_hash,
                                  input_asset_ids=[self.asset_id], started_at=datetime.now(timezone.utc))])

    def provenance(self, *anchors, method="native"):
        return m.Provenance(run_id=self.run_id, anchor_ids=list(anchors), method=method)

    def anchor(self, record, path=()):
        identifier = _id("anchor", self.asset_id + str(record.id()) + json.dumps(path))
        if identifier not in self.anchors:
            self.anchors[identifier] = m.EvidenceAnchor(
                id=identifier, asset_id=self.asset_id,
                selector=m.NativeSelector(kind="step_id", value=str(record.id()), property_path=list(path)))
        return identifier

    def entity_id(self, record):
        return _id("entity", self.asset_id + ":" + str(record.id()))

    def chain(self, name):
        if name not in self.class_chains:
            declaration = self.schema.declaration_by_name(name)
            chain = []
            while declaration:
                chain.append(declaration.name())
                declaration = declaration.supertype()
            self.class_chains[name] = chain
        return self.class_chains[name]

    def concepts(self):
        supported = {}
        roots = {"IfcProduct", "IfcTypeObject", "IfcSystem", "IfcZone", "IfcMaterial"}
        for declaration in self.schema.declarations():
            if hasattr(declaration, "supertype"):
                chain = self.chain(declaration.name())
                if roots.intersection(chain):
                    supported[declaration.name()] = chain
        concepts = [m.Concept(id="ifc:" + name, labels=[m.LocalizedText(text=name)],
                              parent_ids=["ifc:" + chain[1]] if len(chain) > 1 and chain[1] in supported else [],
                              definition="Native IFC class (including subtypes): " + name)
                    for name, chain in supported.items()]
        concepts += [m.Concept(id="concept:" + name, labels=[m.LocalizedText(text=name)],
                               definition="IFC occurrence classified directly or through its type as " + cls)
                     for name, cls in CONCEPT_CLASSES.items()]
        return concepts

    def add_fact(self, subject, key, path, source, value=None, status="present"):
        anchor = self.anchor(source, path)
        self.property_labels[key] = ".".join(path)
        self.facts.append(m.Fact(id=_id("fact", subject + key + anchor), subject_id=subject,
                                 property_key=key, original_property_path=list(path),
                                 status=status, value=value, provenance=self.provenance(anchor)))

    def quantity(self, value, kind, source, *, unit=None, measure_class=None, basis="modeled", explicit=False):
        unit_id, resolution, unit_anchors, normalized = None, "unknown", [], None
        if unit is not None:
            unit_anchors = [self.anchor(unit)]
            try:
                parsed = source_unit(unit)
                if kind in DIMENSIONS and parsed.dimension != DIMENSIONS[kind]:
                    raise ValueError("unit dimensions disagree with source measure")
                self.units[parsed.id] = parsed
                unit_id = parsed.id
                resolution = "explicit" if explicit else "project_default"
                if kind in SI_TARGETS:
                    target = self.units[SI_TARGETS[kind]]
                    normalized = m.NormalizedQuantity(
                        magnitude=decimal_string(convert(decimal_string(value), parsed, target)), unit_id=target.id)
            except (ValueError, KeyError) as exc:
                self.warnings.add("Unresolved source unit: " + str(exc))
        elif kind in {"ratio", "number"} and measure_class != "IfcReal":
            unit_id, resolution = "unit:1", "explicit"
        return m.QuantityValue(kind="quantity", magnitude=decimal_string(value), unit_id=unit_id,
                               quantity_kind=kind, basis=basis, unit_resolution=resolution,
                               unit_anchor_ids=unit_anchors, source_value_type=measure_class,
                               normalized=normalized)

    def property_value(self, prop):
        if prop.is_a("IfcPropertySingleValue"):
            raw = prop.NominalValue
            if raw is None:
                return None, "explicit_null"
            value, cls = raw.wrappedValue, raw.is_a()
            if isinstance(value, bool):
                return m.BooleanValue(kind="boolean", value=value), "present"
            if isinstance(value, str):
                return m.TextValue(kind="text", value=m.LocalizedText(text=value)), "present"
            if not isinstance(value, (int, float)):
                return None, "not_extracted"
            if cls == "IfcCountMeasure" and float(value).is_integer() and value >= 0:
                return m.CountValue(kind="count", value=int(value)), "present"
            unit = unit_util.get_property_unit(prop, self.model)
            kind = UNIT_TYPES.get(getattr(unit, "UnitType", None))
            # Measure type establishes semantics even if a unit is unavailable.
            for term, candidate in [("Length", "length"), ("Area", "area"), ("Volume", "volume"),
                                    ("Mass", "mass"), ("Time", "time"), ("Angle", "angle"), ("Ratio", "ratio")]:
                if term in cls:
                    kind = candidate
                    break
            return self.quantity(value, kind or "number", prop, unit=unit,
                                 measure_class=cls, explicit=prop.Unit is not None), "present"
        quantities = {"IfcQuantityLength": ("length", "LengthValue"),
                      "IfcQuantityArea": ("area", "AreaValue"),
                      "IfcQuantityVolume": ("volume", "VolumeValue"),
                      "IfcQuantityWeight": ("mass", "WeightValue"),
                      "IfcQuantityTime": ("time", "TimeValue")}
        if prop.is_a() in quantities:
            kind, field = quantities[prop.is_a()]
            name = prop.Name.casefold()
            basis = "net" if name.startswith("net") else "gross" if name.startswith("gross") else "modeled"
            return self.quantity(getattr(prop, field), kind, prop,
                                 unit=unit_util.get_property_unit(prop, self.model),
                                 measure_class="Ifc" + kind.title() + "Measure", basis=basis,
                                 explicit=prop.Unit is not None), "present"
        if prop.is_a("IfcQuantityCount"):
            value = prop.CountValue
            if value is not None and float(value).is_integer() and value >= 0:
                return m.CountValue(kind="count", value=int(value)), "present"
        return None, "not_extracted"

    def extract(self):
        concepts = self.concepts()
        objects = {obj.id(): obj for root in ["IfcProduct", "IfcTypeObject", "IfcSystem", "IfcZone", "IfcMaterial"]
                   for obj in self.model.by_type(root)}
        definitions = defaultdict(list)
        for rel in self.model.by_type("IfcRelDefinesByProperties"):
            value = rel.RelatingPropertyDefinition
            for obj in rel.RelatedObjects:
                definitions[obj.id()].extend(value if isinstance(value, tuple) else [value])
        types = {}
        for rel in self.model.by_type("IfcRelDefinesByType"):
            for obj in rel.RelatedObjects:
                if obj.id() in types and types[obj.id()].id() != rel.RelatingType.id():
                    raise ValueError(f"multiple type definitions for IFC record #{obj.id()}")
                types[obj.id()] = rel.RelatingType
                self.add_relation(obj, "typed_by", rel.RelatingType, rel, objects)
        parents, children = set(), set()
        for root, predicate, parent_field, child_field in [
            ("IfcRelAggregates", "aggregates", "RelatingObject", "RelatedObjects"),
            ("IfcRelNests", "aggregates", "RelatingObject", "RelatedObjects"),
            ("IfcRelContainedInSpatialStructure", "contains", "RelatingStructure", "RelatedElements")]:
            for rel in self.model.by_type(root):
                for child in getattr(rel, child_field):
                    parent = getattr(rel, parent_field)
                    self.add_relation(parent, predicate, child, rel, objects)
                    if predicate == "aggregates":
                        parents.add(parent.id())
                        children.add(child.id())
        for rel in self.model.by_type("IfcRelAssignsToGroup"):
            if rel.RelatingGroup.is_a("IfcSystem"):
                for obj in rel.RelatedObjects:
                    self.add_relation(obj, "assigned_to_system", rel.RelatingGroup, rel, objects)
        for obj in objects.values():
            identifier = self.entity_id(obj)
            chain = self.chain(obj.is_a())
            kind = next((kind for cls, kind in [("IfcSite", "site"), ("IfcBuilding", "building"),
                        ("IfcBuildingStorey", "storey"), ("IfcSpace", "space"), ("IfcTypeObject", "type"),
                        ("IfcSystem", "system"), ("IfcZone", "zone"), ("IfcMaterial", "material")]
                         if cls in chain), "assembly" if obj.id() in parents else "part" if obj.id() in children else "element")
            entity_concepts = ["ifc:" + obj.is_a()]
            if kind not in {"type", "system", "material", "zone"}:
                semantic_classes = set(chain)
                if obj.id() in types:
                    semantic_classes.update(name.removesuffix("Type").removesuffix("Style")
                                            for name in self.chain(types[obj.id()].is_a()))
                entity_concepts += ["concept:" + name for name, cls in CONCEPT_CLASSES.items() if cls in semantic_classes]
            anchor = self.anchor(obj)
            self.entities[identifier] = m.Entity(id=identifier, project_id=self.project_id,
                document_id=self.document_id, kind=kind, concept_ids=entity_concepts,
                labels=[m.LocalizedText(text=obj.Name)] if getattr(obj, "Name", None) else [],
                provenance=self.provenance(anchor))
            anchors = [anchor]
            if getattr(obj, "GlobalId", None):
                guid_anchor = _id("anchor", self.asset_id + ":guid:" + str(obj.id()))
                self.anchors[guid_anchor] = m.EvidenceAnchor(id=guid_anchor, asset_id=self.asset_id,
                    selector=m.NativeSelector(kind="ifc_guid", value=obj.GlobalId))
                anchors.append(guid_anchor)
            self.representations.append(m.Representation(id=_id("representation", identifier), entity_id=identifier,
                asset_id=self.asset_id, anchor_ids=anchors, provenance=self.provenance(anchor)))
            self.add_fact(identifier, CLASS_KEY, ["class"], obj,
                          m.TextValue(kind="text", value=m.LocalizedText(text=obj.is_a())))
            for name in ATTRIBUTES:
                if hasattr(obj, name):
                    value = getattr(obj, name)
                    self.add_fact(identifier, attribute_key(name), [name], obj,
                        m.TextValue(kind="text", value=m.LocalizedText(text=str(value))) if value is not None else None,
                        "present" if value is not None else "explicit_null")
            for name in LENGTH_ATTRIBUTES:
                if hasattr(obj, name):
                    value = getattr(obj, name)
                    self.add_fact(identifier, attribute_key(name), [name], obj,
                        self.quantity(value, "length", obj, unit=unit_util.get_project_unit(self.model, "LENGTHUNIT"),
                                      measure_class="IfcLengthMeasure") if value is not None else None,
                        "present" if value is not None else "explicit_null")
            own = self.property_records([*definitions[obj.id()], *(getattr(obj, "HasPropertySets", None) or [])])
            inherited = self.property_records(getattr(types.get(obj.id()), "HasPropertySets", None) or [])
            for key, entries in (inherited | own).items():
                for path, record in entries:
                    value, status = self.property_value(record)
                    self.add_fact(identifier, key, path, record, value, status)
            if obj.is_a("IfcObjectDefinition"):
                associations = [rel for rel in (getattr(obj, "HasAssociations", None) or []) if rel.is_a("IfcRelAssociatesMaterial")]
                if not associations and obj.id() in types:
                    associations = [rel for rel in (getattr(types[obj.id()], "HasAssociations", None) or []) if rel.is_a("IfcRelAssociatesMaterial")]
                for material in element_util.get_materials(obj):
                    for association in associations:
                        self.add_relation(obj, "has_material", material, association, objects)
        properties = self.property_definitions()
        bundle = m.KnowledgeBundle(**self.bundle_base, concepts=concepts, properties=properties,
            units=list(self.units.values()), anchors=list(self.anchors.values()),
            entities=list(self.entities.values()), facts=self.facts,
            relations=list({relation.id: relation for relation in self.relations}.values()), representations=self.representations)
        return LoadedModel(bundle, self.model.schema_identifier, sorted(self.warnings))

    def add_relation(self, subject, predicate, obj, source, objects):
        if subject.id() in objects and obj.id() in objects:
            self.relations.append(m.Relation(id=_id("relation", self.asset_id + f":{source.id()}:{predicate}:{subject.id()}:{obj.id()}"),
                subject_id=self.entity_id(subject), predicate=predicate, object_id=self.entity_id(obj),
                native_predicate=source.is_a(), provenance=self.provenance(self.anchor(source))))

    def property_records(self, definitions):
        result = defaultdict(list)
        seen = set()
        for definition in definitions:
            records = getattr(definition, "HasProperties", None) or getattr(definition, "Quantities", None) or []
            for record in records:
                path = [definition.Name or f"#{definition.id()}", record.Name or f"#{record.id()}"]
                key = property_key(*path)
                if (key, record.id()) not in seen:
                    result[key].append((path, record))
                    seen.add((key, record.id()))
        return result

    def property_definitions(self):
        grouped = defaultdict(list)
        for fact in self.facts:
            grouped[fact.property_key].append(fact)
        definitions = []
        for key, facts in grouped.items():
            shapes = {(fact.value.kind, getattr(fact.value, "quantity_kind", None))
                      for fact in facts if fact.value is not None}
            if len(shapes) > 1:
                self.warnings.add("Inconsistent source types for " + self.property_labels[key])
                for fact in facts:
                    fact.value, fact.status = None, "ambiguous"
                shapes = set()
            value_kind, quantity_kind = next(iter(shapes), ("text", None))
            definitions.append(m.PropertyDefinition(key=key, labels=[m.LocalizedText(text=self.property_labels[key])],
                value_kind=value_kind, quantity_kind=quantity_kind, dimension=DIMENSIONS.get(quantity_kind),
                definition="Native IFC attribute/property; original path and source record are retained."))
        # Deduplicate repeat references to the same property record.
        self.facts = list({fact.id: fact for fact in self.facts}.values())
        return definitions
