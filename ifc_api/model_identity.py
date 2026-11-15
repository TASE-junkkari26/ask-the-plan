"""Conservative source-derived aliases for the single uploaded IFC context.

This does not select files. A descriptive title must bind an original source
name, or a strong literal filename core, with every stated role/version/variant
checked separately. No dataset display titles or QA mappings enter this module.
"""
from __future__ import annotations

import re
import unicodedata

from contracts import models as m
from ifc_engine.catalog import attribute_key

_ROLES = {
    "architectural": "architectural", "architecture": "architectural", "architektur": "architectural", "arc": "architectural", "arch": "architectural",
    "mechanical": "mechanical", "mechanisch": "mechanical", "mep": "mep",
    "electrical": "electrical", "elektrik": "electrical", "elektro": "electrical", "elektrotechnik": "electrical",
    "plumbing": "plumbing", "sanitär": "plumbing", "sanitaer": "plumbing", "san": "plumbing",
    "structural": "structural", "structure": "structural", "tragwerk": "structural", "str": "structural",
    "hvac": "hvac", "heating": "heating", "heizung": "heating", "ventilation": "ventilation", "lüftung": "ventilation",
}
_GENERIC = {"project", "projekt", "model", "modell", "building", "gebäude", "house", "clinic", "hospital", "office", "apartment", "number", "name", "test",
            "source", "fixture", "sample", "example", "default", "export", "unnamed", "unknown", "untitled", "ifc", "query", "regression"}
_GENERIC.update({"projectname", "projectnumber", "projektname", "projektnummer", "projectstatus", "projektstatus"})
_GENERIC.update({"renamed", "company", "organization", "organisation", "package", "data", "library", "original", "exported"})


def _fold(value):
    return unicodedata.normalize("NFC", value).casefold()


def _key(value):
    value = value[:-4] if value.casefold().endswith(".ifc") else value
    return "".join(character for character in _fold(value) if character.isalnum())


def _tokens(value):
    return re.findall(r"[^\W_]+", _fold(value))


def _basename(value):
    return value.replace("\\", "/").rsplit("/", 1)[-1]


def _texts(engine, identifiers, names, *, hydrate=True):
    keys = [attribute_key(name) for name in names if attribute_key(name) in engine.properties]
    if hydrate:
        engine.ensure_fields(identifiers, keys)
    output = {name: [] for name in names}
    for identifier in identifiers:
        for name in names:
            facts = engine.facts.get((identifier, attribute_key(name)), ())
            for fact in facts:
                if fact.status != "present":
                    continue
                values = fact.value.items if isinstance(fact.value, m.ListValue) else [fact.value]
                if name == "ApplicationIdentifiers":
                    values = [value.fields.get("ApplicationIdentifier") for value in values
                              if isinstance(value, m.RecordValue)
                              and isinstance(value.fields.get("status"), m.TextValue)
                              and value.fields["status"].value.text == "present"]
                output[name].extend(value.value.text for value in values if isinstance(value, m.TextValue))
    return output


def _qualifier(value):
    value = _fold(value).strip()
    value = re.sub(r"^fachmodell\s+", "", value)
    rooms = re.fullmatch(r"(.+?)\s*\(rooms and spaces\)", value)
    boundaries = re.fullmatch(r"(.+?)\s+(?:mit|with) space boundaries\s*\(ifc2sb\)", value)
    variant = "rooms_spaces" if rooms else "ifc2sb" if boundaries else None
    role = _ROLES.get((rooms or boundaries)[1].strip() if rooms or boundaries else value)
    return (role, variant) if role else None


def _source_roles(filenames, metadata):
    tokens = {token for filename in filenames for token in _tokens(filename)}
    roles = {_ROLES[token] for token in tokens if token in _ROLES}
    applications = " ".join(metadata["ApplicationFullName"] + metadata["OriginatingSystem"] + metadata["PreprocessorVersion"])
    app_roles = {_ROLES[token] for token in _tokens(applications) if token in _ROLES}
    # Authoring software alone does not establish model discipline. The
    # single-letter export convention needs both filename and application.
    for filename in filenames:
        if re.search(r"(?:^|[_-])a[_-]\d{8}(?:[_.-]|$)", _fold(filename)) and "architectural" in app_roles:
            roles.add("architectural")
        if re.search(r"(?:^|[_-])m[_-]\d{8}(?:[_.-]|$)", _fold(filename)) and "mep" in app_roles:
            roles.add("mechanical")
    return roles, tokens


def _role_matches(role, roles):
    if role == "mep":
        return roles == {"mep"}
    compatible = {role, "mep"} if role in {"mechanical", "electrical", "plumbing", "hvac", "heating", "ventilation"} else {role}
    return role in roles and not roles - compatible


def matches_model(engine, title, *, allow_metadata=True):
    if title is None:
        return True
    projects = [entity for entity in engine.entities.values() if "concept:project" in entity.concept_ids]
    buildings = [entity for entity in engine.entities.values() if entity.kind == "building"]
    names = [label.text for document in engine.bundle.documents for label in document.title]
    names += [label.text for entity in projects for label in entity.labels]
    if len(buildings) == 1:
        names += [label.text for label in buildings[0].labels]
    if _key(title) and _key(title) in {_key(name) for name in names if name}:
        return True
    metadata = _texts(engine, [entity.id for entity in projects],
                      ("NativeFilename", "ApplicationIdentifiers", "ApplicationFullName", "OriginatingSystem", "PreprocessorVersion"), hydrate=allow_metadata)
    filenames = [_basename(label.text) for document in engine.bundle.documents for label in document.title]
    filenames += [_basename(value) for value in metadata["NativeFilename"]]
    if _key(title) and _key(title) in {_key(filename) for filename in filenames if filename}:
        return True

    # Discipline qualifiers must be explicit and fully understood. Versions
    # remain in the core and must occur literally in the source filename.
    parts = re.split(r"\s+[–—-]\s+", title, maxsplit=1)
    core, qualifier = parts[0], _qualifier(parts[1]) if len(parts) == 2 else None
    if len(parts) == 2 and qualifier is None:
        return False
    schema = re.fullmatch(r"(.+?)\s+IFC\s*(\d)[.x_](\d)\s+(?:test\s+)?model", core, re.IGNORECASE)
    if schema:
        if not engine.schema.upper().startswith("IFC" + schema[2] + "X" + schema[3]):
            return False
        core = schema[1]
    elif qualifier is None:
        return False
    native_core = _key(core) in {_key(name) for name in names if name and not name.casefold().endswith(".ifc")}
    core_tokens = _tokens(core)
    strong = len(core_tokens) >= 2 and any(len(token) >= 5 and token.isalpha() and token not in _GENERIC for token in core_tokens)
    matching_files = [filename for filename in filenames if strong and set(core_tokens) <= set(_tokens(filename))]
    if not native_core and not matching_files:
        return False
    if qualifier is None:
        return bool(schema)
    role, variant = qualifier
    role_files = filenames if native_core else matching_files
    roles, tokens = _source_roles(role_files, metadata)
    if not _role_matches(role, roles):
        return False
    if variant == "rooms_spaces" and not {"rooms", "spaces"} <= tokens:
        return False
    if variant == "ifc2sb":
        boundary_name = {"space", "boundaries"} <= tokens or {"with", "sb"} <= tokens
        if not boundary_name or "ifc2sb" not in {_fold(value) for value in metadata["ApplicationIdentifiers"]}:
            return False
    return True


def assess_model(engine, title, *, allow_metadata=False):
    """Assess a quoted model label without selecting/broadening source scope.

    Default operation is read-only. Callers may explicitly allow project-only
    metadata hydration after enforcing their captured-scope/whole-model gate.
    UNKNOWN is deliberately distinct from conflicting identity: an unexplained
    descriptive alias is not proof that the current source is a different file.
    """
    if matches_model(engine, title, allow_metadata=allow_metadata):
        return {"status": "MATCH", "reason": "The title resolves to original source identity and its stated qualifiers."}
    projects = [entity for entity in engine.entities.values() if "concept:project" in entity.concept_ids]
    buildings = [entity for entity in engine.entities.values() if entity.kind == "building"]
    native_names = [label.text for entity in projects for label in entity.labels]
    if len(buildings) == 1:
        native_names += [label.text for label in buildings[0].labels]
    metadata = _texts(engine, [entity.id for entity in projects],
                      ("NativeFilename", "ApplicationIdentifiers", "ApplicationFullName", "OriginatingSystem", "PreprocessorVersion"), hydrate=allow_metadata)
    filenames = [_basename(label.text) for document in engine.bundle.documents for label in document.title]
    filenames += [_basename(value) for value in metadata["NativeFilename"]]
    parts = re.split(r"\s+[–—-]\s+", title, maxsplit=1)
    core = parts[0]
    qualifier = _qualifier(parts[1]) if len(parts) == 2 else None
    schema = re.fullmatch(r"(.+?)\s+IFC\s*(\d)[.x_](\d)\s+(?:test\s+)?model", core, re.IGNORECASE)
    if schema:
        core = schema[1]
    tokens = set(_tokens(core))
    versions = {token for token in tokens if re.fullmatch(r"v\d+", token)}
    unversioned = tokens - versions
    strong = {token for token in unversioned if token.isalpha() and len(token) >= 5 and token not in _GENERIC}
    source_files = [filename for filename in filenames if strong and unversioned <= set(_tokens(filename))]
    native_core = _key(core) in {_key(name) for name in native_names if name}
    same_core = native_core or bool(source_files)
    if same_core:
        if schema and not engine.schema.upper().startswith("IFC" + schema[2] + "X" + schema[3]):
            return {"status": "CONFLICTING", "reason": "The requested IFC schema descriptor conflicts with the source file's declared schema."}
        source_versions = {token for filename in source_files for token in _tokens(filename) if re.fullmatch(r"v\d+", token)}
        if len(versions) == len(source_versions) == 1 and versions != source_versions:
            return {"status": "CONFLICTING", "reason": "The explicitly requested model version conflicts with the literal source filename version."}
        if qualifier is not None:
            roles, _ = _source_roles(filenames if native_core else source_files, metadata)
            if roles and not _role_matches(qualifier[0], roles):
                return {"status": "CONFLICTING", "reason": "The requested discipline conflicts with verified source filename discipline metadata."}
    native_strong = [{token for token in _tokens(name) if token.isalpha() and len(token) >= 5 and token not in _GENERIC}
                     for name in native_names]
    # A packaged filename may have an organisation/library prefix. Consider
    # only its final underscore component for disjoint-core checks, and remove
    # discipline/export vocabulary. Ambiguous filename structures stay unknown.
    native_strong += [{token for token in _tokens(filename.rsplit("_", 1)[-1]) if token.isalpha() and len(token) >= 5
                       and token not in _GENERIC and token not in _ROLES} for filename in filenames]
    native_strong = [values for values in native_strong if values]
    if strong and native_strong and all(not (strong & values) for values in native_strong):
        return {"status": "CONFLICTING", "reason": "The explicitly named model has a disjoint strong identity from the original project/building names."}
    return {"status": "UNKNOWN", "reason": "The descriptive title is not resolved by available source identity metadata; request clarification or bounded source inspection."}
