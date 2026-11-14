"""Source-only checks for this pilot, not a general PDF/DXF production parser.

No questions.jsonl or reference answers are read. The DXF probe supports only
closed, straight, 2D ROOM_OUTLINE polylines, with one containing outline and no
other nested room outlines. A real importer must handle broader source geometry.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import time

from .run import digest, write_json


def attr(entity, code, default=None):
    return next((value for key, value in entity["pairs"] if key == code), default)


def vertices(entity):
    points = []
    for code, value in entity["pairs"]:
        if code == 10:
            points.append([float(value), None])
        elif code == 20:
            points[-1][1] = float(value)
    return points


def contains(points, point):
    x, y = point
    hit = False
    for (x1, y1), (x2, y2) in zip(points, points[1:] + points[:1]):
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            hit = not hit
    return hit


def room_area(source, room_id):
    lines = source.read_text(encoding="utf-8").splitlines()
    pairs = [(int(lines[i]), lines[i + 1].strip()) for i in range(0, len(lines) - 1, 2)]
    unit_index = next(i for i, item in enumerate(pairs) if item == (9, "$INSUNITS"))
    if pairs[unit_index + 1] != (70, "6"):
        raise ValueError("This probe requires explicit metre units")
    entities, current, inside = [], None, False
    for code, value in pairs:
        if code == 2 and value == "ENTITIES":
            inside = True
        if not inside:
            continue
        if code == 0:
            if current:
                entities.append(current)
            current = {"type": value, "pairs": []}
            if value == "ENDSEC":
                break
        elif current:
            current["pairs"].append((code, value))
    label = next(e for e in entities if e["type"] == "TEXT"
                 and attr(e, 8) == "ROOM_TEXT" and attr(e, 1) == room_id)
    point = [float(attr(label, 10)), float(attr(label, 20))]
    outlines = [e for e in entities if e["type"] == "LWPOLYLINE" and attr(e, 8) == "ROOM_OUTLINE"]
    selected = [e for e in outlines if contains(vertices(e), point)]
    if len(selected) != 1:
        raise ValueError("Room label does not map to exactly one outline")
    entity = selected[0]
    if not int(attr(entity, 70, "0")) & 1 or any(float(v) for k, v in entity["pairs"] if k == 42):
        raise ValueError("Probe requires closed straight outline")
    points = vertices(entity)
    if any(e is not entity and any(contains(points, p) for p in vertices(e)) for e in outlines):
        raise ValueError("Nested/overlapping outlines require explicit topology handling")
    area = abs(sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2)
                   in zip(points, points[1:] + points[:1]))) / 2
    return {"room_id": room_id, "label_handle": attr(label, 5), "label_point": point,
            "outline_handle": attr(entity, 5), "vertices": points,
            "area": area, "unit": "m2", "unit_source": "$INSUNITS=6",
            "method": "Shoelace area of the one straight closed ROOM_OUTLINE containing the literal room ID"}


def run(base, dataset):
    started = time.perf_counter()
    cases = {c["id"]: c for c in json.loads((base / "cases.json").read_text(encoding="utf-8"))["cases"]}
    swiss = json.loads((base / "Q05/native-anchors.json").read_text(encoding="utf-8"))
    bedrooms = [a for a in swiss if a["text"] == "Schlafzimmer"]
    dxf = (dataset / cases["Q06"]["path"]).with_suffix(".dxf")
    area = room_area(dxf, "2.09")
    area.update(source=str(dxf), source_sha256=digest(dxf))
    anchors = json.loads((base / "Q07/native-anchors.json").read_text(encoding="utf-8"))
    doors = [a for a in anchors if re.fullmatch(r"\d{3}\.[A-Z]\d?", a["text"])]
    if len({a["text"] for a in doors}) != len(doors):
        raise ValueError("Repeated schedule IDs require layout disambiguation")
    target = next(a for a in doors if a["text"] == "121.A")
    row = sorted([a for a in anchors if abs(a["matrix"][5] - target["matrix"][5]) < 2
                  and a["box"][0] < 1030], key=lambda a: a["box"][0])
    # This pilot's header/column order was visually reviewed, not inferred by a model.
    width = row[3]
    checks = {}
    for relative, offset in [("Q07", (0, 0)), ("diagnostics/D04", (140, 110))]:
        result = json.loads((base / relative / "api-response.json").read_text(encoding="utf-8"))
        native = {a["text"]: a for a in doors}
        matches, hits, comparisons = [], [], []
        for candidate in result["candidates"]:
            label = candidate["source_label"]
            if label not in native:
                continue
            matches.append(label)
            box = native[label]["box"]
            center = [(box[0] + box[2]) / 2 - offset[0], (box[1] + box[3]) / 2 - offset[1]]
            minimum, maximum = candidate["geometry"]["minimum"], candidate["geometry"]["maximum"]
            if all(minimum[i] <= center[i] <= maximum[i] for i in range(2)):
                hits.append(label)
            comparisons.append({"label": label, "native_center": center,
                                "candidate_box": [minimum, maximum]})
        checks[relative] = {"literal_matches": matches, "matching_id_center_inside_box": hits,
                            "comparisons": comparisons}
    output = {"Q05": {"count": len(bedrooms), "anchors": bedrooms}, "Q06": area,
              "Q07": {"count": len(doors), "anchors": doors},
              "Q08": {"width": width["text"], "width_anchor": width, "row": row},
              "anchor_checks": checks,
              "elapsed_seconds_excluding_pdf_extraction": time.perf_counter() - started,
              "provider_requests": 0, "references_read": False,
              "scope": "Same selected Swiss floor via paired DXF; same A-801 PDF page"}
    write_json(base / "native-probe.json", output)
    print(json.dumps({"Q05": len(bedrooms), "Q06": area["area"], "Q07": len(doors),
                      "Q08": width["text"], "elapsed_seconds": output["elapsed_seconds_excluding_pdf_extraction"]}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--dataset", type=Path, default=Path("dataset/junction-dataset"))
    args = parser.parse_args()
    run(args.run_dir, args.dataset)
