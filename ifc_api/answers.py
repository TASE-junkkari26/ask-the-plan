"""Readable answers composed only from executed, evidence-bound source values."""
from __future__ import annotations

from contracts import models as m
from ifc_engine.catalog import attribute_key


METADATA_SENTENCES = {attribute_key(key): template for key, template in {
    "FILE_SCHEMA": "The file declares IFC schema {value}.",
    "OriginatingSystem": "The recorded originating system is {value}.",
    "PreprocessorVersion": "The recorded preprocessor is {value}.",
    "ModelViewDefinition": "The recorded model view definition is {value}.",
    "ApplicationFullName": "The owning authoring application is {value}.",
    "ApplicationIdentifier": "The recorded application identifier is {value}.",
    "Version": "The recorded application version is {value}.",
    "Description": "The source description is: {value}.",
    "ObjectType": "The recorded object type is {value}.",
    "Phase": "The recorded project phase is {value}.",
    "LandTitleNumber": "The recorded land title number is {value}.",
    "RefLatitude": "The recorded site latitude is {value}, as an IFC degrees/minutes/seconds tuple with optional millionths of a second.",
    "RefLongitude": "The recorded site longitude is {value}, as an IFC degrees/minutes/seconds tuple with optional millionths of a second.",
    "RefElevation": "The recorded reference elevation is {value}.",
    "Address.AddressLines": "The recorded address is: {value}.",
    "Address.Town": "The recorded town is {value}.",
    "Address.Region": "The recorded region is {value}.",
    "Address.PostalCode": "The recorded postal code is {value}.",
    "Address.Country": "The recorded country is {value}.",
}.items()}


def summarize(engine, result: m.QueryResult) -> str | None:
    if not result.claims:
        return None

    def name(identifier):
        entity = engine.entities[identifier]
        label = " · ".join(item.text for item in entity.labels)
        steps = sorted({engine.anchors[a].selector.value for a in entity.provenance.anchor_ids
                        if engine.anchors[a].selector.kind == "step_id" and not engine.anchors[a].selector.property_path})
        return (label or entity.kind) + (f" [#{steps[0]}]" if steps else "")

    def value(item):
        if isinstance(item, m.ReferencesValue):
            return ", ".join(name(identifier) for identifier in item.entity_ids[:12]) + (" (more in source results)" if len(item.entity_ids) > 12 else "") or "none recorded"
        if isinstance(item, m.TextValue):
            return item.value.text
        if isinstance(item, m.BooleanValue):
            return "yes" if item.value else "no"
        if isinstance(item, m.CountValue):
            return str(item.value)
        if isinstance(item, m.QuantityValue):
            unit = engine.units.get(item.unit_id)
            return f"{item.magnitude} {unit.symbol if unit else '(unit unresolved)'} ({item.basis})"
        return "see structured source results"

    def field_label(key):
        definition = engine.properties.get(key)
        return definition.labels[0].text if definition and definition.labels else key

    statements = []
    for claim in result.claims:
        output = claim.value
        if isinstance(output, m.TableValue):
            if not output.rows:
                statements.append("No matching relationships were established from the inspected source records in the selected scope.")
            for row in output.rows[:12]:
                if set(row) == {"subject", "related", "via", "basis"}:
                    subject, related, via, basis = (value(row[key]) for key in ("subject", "related", "via", "basis"))
                    if basis.startswith("Native ") and basis.endswith(" containment"):
                        statements.append(f"{subject} is in {related}, according to native IFC containment.")
                    elif basis == "Shared physical door boundary":
                        statements.append(f"{subject} has a modeled door connection to {related}, via {via}.")
                    elif basis == "Native corresponding space boundaries":
                        statements.append(f"{subject} and {related} have corresponding native space boundaries.")
                    elif basis == "Geometry-verified overlapping boundary patches":
                        statements.append(f"{subject} and {related} have overlapping modeled boundary patches within the recorded tolerance, via {via}.")
                    elif basis == "Geometry-verified space containment":
                        statements.append(f"{subject} is contained in the modeled space {related}, according to the recorded geometry check.")
                    else:
                        statements.append(f"{subject} shares {via} with {related}; this is a candidate neighbor based on a shared boundary element.")
                else:
                    # Labels often duplicate a reference column; retain the
                    # source reference so repeated room names stay inspectable.
                    if METADATA_SENTENCES.keys() & row.keys():
                        for key, item in row.items():
                            if key in METADATA_SENTENCES:
                                statements.append(METADATA_SENTENCES[key].format(value=value(item)))
                            elif key != "label" or not any(isinstance(v, m.ReferencesValue) for v in row.values()):
                                statements.append(f"{field_label(key)}: {value(item)}.")
                    else:
                        entries = [f"{field_label(key)}: {value(item)}" for key, item in row.items() if key != "label" or not any(isinstance(v, m.ReferencesValue) for v in row.values())]
                        statements.append("; ".join(entries) + ".")
            if len(output.rows) > 12:
                statements.append(f"The summary shows 12 of {len(output.rows)} rows; the structured results and evidence contain the full result.")
        elif isinstance(output, m.CountValue):
            grain = claim.count_policy.grain.replace("_", " ") if claim.count_policy else "source object"
            qualifier = {"lower_bound": "at least ", "upper_bound": "at most ", "estimated": "approximately "}.get(claim.quality, "")
            statements.append(f"{claim.output_key}: {qualifier}{output.value} modeled {grain}(s) in the selected scope.")
        elif isinstance(output, m.ReferencesValue):
            statements.append("Modeled source objects in the selected scope: " + value(output) + ".")
        else:
            statements.append(f"{claim.output_key}: {value(output)}.")
    if result.explanation:
        statements.append(result.explanation.text)
    return " ".join(statements)
