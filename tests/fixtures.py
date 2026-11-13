"""Illustrative records, not extracted measurements or benchmark answers."""
from copy import deepcopy

LENGTH = [1, 0, 0, 0, 0, 0, 0]
AREA = [2, 0, 0, 0, 0, 0, 0]


def provenance(*anchors, method="native"):
    return {"run_id": "run:r", "anchor_ids": list(anchors), "method": method}


def scope():
    return {
        "project_id": "project:p",
        "document_ids": ["doc:d"],
        "entity_ids": ["floor:1"],
        "view_ids": [],
        "universe": "depicted_objects",
    }


def policy():
    return {
        "grain": "logical_object",
        "hierarchy": "topmost_matches",
        "rule_key": "room.logical_space.v1",
    }


def area_value():
    return {
        "kind": "quantity",
        "magnitude": "19000000",
        "unit_id": "unit:mm2",
        "quantity_kind": "area",
        "basis": "net",
        "unit_resolution": "explicit",
        "unit_anchor_ids": ["anchor:room"],
        "normalized": {"magnitude": "19", "unit_id": "unit:m2"},
    }


def normalized_area_value():
    value = area_value()
    value.update(magnitude="19", unit_id="unit:m2", unit_resolution="derived")
    return value


def bundle_data():
    """A CAD room with one column hole and a calibrated raster rendering."""
    return {
        "projects": [{"id": "project:p", "name": "Illustrative contract fixture"}],
        "documents": [{"id": "doc:d", "project_id": "project:p", "logical_key": "plan:1", "revision": "A"}],
        "assets": [
            {"id": "cad:a", "document_id": "doc:d", "uri": "fixture://room.dxf", "sha256": "a" * 64,
             "format": "dxf", "media_type": "application/dxf", "source_collection": "illustrative_contract_fixture",
             "attribution": "Synthetic contract example", "license": "CC0-1.0"},
            {"id": "png:a", "document_id": "doc:d", "uri": "fixture://room.png", "sha256": "b" * 64,
             "format": "png", "media_type": "image/png", "source_collection": "illustrative_contract_fixture",
             "attribution": "Synthetic contract example", "license": "CC0-1.0"},
        ],
        "asset_links": [{"source_asset_id": "png:a", "target_asset_id": "cad:a", "kind": "rendered_from",
                         "provenance": provenance("anchor:room")}],
        "runs": [{"id": "run:r", "tool": "fixture", "version": "1", "config_sha256": "0" * 64,
                  "input_asset_ids": ["cad:a", "png:a"], "started_at": "2026-11-13T12:00:00Z"}],
        "concepts": [
            {"id": "concept:room", "labels": [{"text": "room", "language": "en"}, {"text": "huone", "language": "fi"}],
             "definition": "A logical room, not a drawing primitive."},
            {"id": "concept:storey", "labels": [{"text": "storey", "language": "en"}], "definition": "A building storey."},
        ],
        "properties": [{"key": "property:net_area", "labels": [{"text": "net area", "language": "en"}],
                        "value_kind": "quantity", "quantity_kind": "area", "dimension": AREA,
                        "definition": "Floor polygon area excluding column holes."}],
        "units": [
            {"id": "unit:m", "symbol": "m", "kind": "physical", "dimension": LENGTH, "si_multiplier": "1"},
            {"id": "unit:mm", "symbol": "mm", "kind": "physical", "dimension": LENGTH, "si_multiplier": "0.001"},
            {"id": "unit:m2", "symbol": "m2", "kind": "physical", "dimension": AREA, "si_multiplier": "1"},
            {"id": "unit:mm2", "symbol": "mm2", "kind": "physical", "dimension": AREA, "si_multiplier": "0.000001"},
            {"id": "unit:px", "symbol": "px", "kind": "presentation"},
        ],
        "frames": [
            {"id": "frame:metric", "asset_id": "cad:a", "dimension": 2, "space": "physical", "unit_id": "unit:m", "axes": ["right", "up"]},
            {"id": "frame:pixel", "asset_id": "png:a", "dimension": 2, "space": "presentation", "unit_id": "unit:px", "axes": ["right", "down"]},
        ],
        "transforms": [{"id": "transform:pixel_to_metric", "from_frame_id": "frame:pixel", "to_frame_id": "frame:metric",
                        "kind": "affine", "matrix": [[0.01, 0, 0], [0, -0.01, 4], [0, 0, 1]],
                        "provenance": provenance("anchor:scale", method="computed")}],
        "views": [
            {"id": "view:cad", "asset_id": "cad:a", "frame_id": "frame:metric", "kind": "floor_plan", "depicts_entity_ids": ["floor:1"]},
            {"id": "view:pixel", "asset_id": "png:a", "frame_id": "frame:pixel", "kind": "floor_plan", "depicts_entity_ids": ["floor:1"]},
        ],
        "geometries": [
            {"id": "geometry:room", "frame_id": "frame:metric", "shape": {"kind": "multipolygon", "polygons": [
                {"shell": [[0, 0], [5, 0], [5, 4], [0, 4], [0, 0]],
                 "holes": [[[1, 1], [2, 1], [2, 2], [1, 2], [1, 1]]]},
            ]}},
            {"id": "geometry:scale", "frame_id": "frame:pixel", "shape": {"kind": "box", "minimum": [0, 400], "maximum": [500, 420]}},
        ],
        "anchors": [
            {"id": "anchor:room", "asset_id": "cad:a", "view_id": "view:cad", "selector": {"kind": "dxf_handle", "value": "A5"},
             "geometry_id": "geometry:room", "quote": {"text": "7.16 Korridor", "language": "de"}},
            {"id": "anchor:scale", "asset_id": "png:a", "view_id": "view:pixel", "selector": {"kind": "image_region", "value": "scale-bar"},
             "geometry_id": "geometry:scale", "quote": {"text": "5 m", "language": "und"}},
        ],
        "calibrations": [{"id": "calibration:1", "view_id": "view:pixel", "transform_id": "transform:pixel_to_metric",
                          "method": "scale_bar", "provenance": provenance("anchor:scale")}],
        "entities": [
            {"id": "floor:1", "project_id": "project:p", "document_id": "doc:d", "kind": "storey",
             "concept_ids": ["concept:storey"], "provenance": provenance("anchor:room")},
            {"id": "room:1", "project_id": "project:p", "document_id": "doc:d", "kind": "space",
             "concept_ids": ["concept:room"], "labels": [{"text": "7.16", "language": "und"}], "provenance": provenance("anchor:room")},
        ],
        "representations": [{"id": "representation:room", "entity_id": "room:1", "asset_id": "cad:a", "view_id": "view:cad",
                             "anchor_ids": ["anchor:room"], "geometry_ids": ["geometry:room"], "provenance": provenance("anchor:room")}],
        "facts": [{"id": "fact:area", "subject_id": "room:1", "property_key": "property:net_area",
                   "status": "present", "value": area_value(), "provenance": provenance("anchor:room", method="computed")}],
        "relations": [{"id": "relation:floor_room", "subject_id": "floor:1", "predicate": "contains", "object_id": "room:1",
                       "provenance": provenance("anchor:room")}],
        "coverage": [{"id": "coverage:rooms", "scope": scope(), "concept_ids": ["concept:room"],
                      "property_keys": ["property:net_area"], "count_policy": policy(), "completeness": "complete",
                      "explanation": "Illustrative complete inventory for this source/view scope.", "provenance": provenance("anchor:room")}],
    }


def request_data():
    return {"id": "request:area", "question": {"text": "Mikä on huoneen 7.16 nettoala?", "language": "fi"},
            "attachment_asset_ids": ["png:a"], "project_id": "project:p"}


def plan_data():
    return {
        "id": "plan:area", "request_id": "request:area", "scope": scope(),
        "steps": [
            {"id": "select", "operation": {"kind": "select", "concept_ids": ["concept:room"], "count_policy": policy(),
                                            "where": {"kind": "compare", "field": {"kind": "entity_id", "key": "id"},
                                                      "operator": "in", "value": {"kind": "references", "entity_ids": ["room:1"]}}}},
            {"id": "lookup", "operation": {"kind": "aggregate", "input_step_id": "select", "method": "sum",
                                            "field": {"kind": "property", "key": "property:net_area"}, "output_unit_id": "unit:m2"}},
        ],
        "outputs": {"area": "lookup"},
    }


def result_data():
    value = normalized_area_value()
    return {
        "id": "result:area", "request_id": "request:area", "plan_id": "plan:area", "status": "answered",
        "claims": [{"id": "claim:area", "output_key": "area", "name": "Net room area", "scope": scope(), "concept_ids": ["concept:room"],
                    "property_keys": ["property:net_area"], "value": value, "quality": "exact", "coverage_ids": ["coverage:rooms"],
                    "evidence": [{"calculation_id": "calculation:area", "anchor_ids": ["anchor:room"], "fact_ids": ["fact:area"]}]}],
        "calculations": [{"id": "calculation:area", "plan_step_id": "lookup", "operation": "sum", "fact_ids": ["fact:area"],
                          "anchor_ids": ["anchor:room"], "output": deepcopy(value), "quality": "exact"}],
        "executor_version": "fixture-1",
    }


def count_plan_data():
    data = plan_data()
    data["steps"][1] = {"id": "count", "operation": {"kind": "aggregate", "input_step_id": "select", "method": "count"}}
    data["outputs"] = {"count": "count"}
    return data


def count_result_data(members=("room:1",)):
    value = {"kind": "count", "value": len(members)}
    return {
        "id": "result:count", "request_id": "request:area", "plan_id": "plan:area", "status": "answered",
        "entity_sets": [{"id": "set:rooms", "scope": scope(), "count_policy": policy(), "count": len(members), "entity_ids": list(members)}],
        "claims": [{"id": "claim:count", "output_key": "count", "name": "Room count", "scope": scope(), "concept_ids": ["concept:room"],
                    "count_policy": policy(), "value": value, "quality": "exact", "coverage_ids": ["coverage:rooms"],
                    "evidence": [{"calculation_id": "calculation:count", "entity_set_ids": ["set:rooms"], "anchor_ids": ["anchor:room"]}]}],
        "calculations": [{"id": "calculation:count", "plan_step_id": "count", "operation": "count", "included_set_id": "set:rooms",
                          "anchor_ids": ["anchor:room"], "output": deepcopy(value), "quality": "exact", "rule_key": policy()["rule_key"]}],
        "executor_version": "fixture-1",
    }
