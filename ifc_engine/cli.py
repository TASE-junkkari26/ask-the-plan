"""Small local CLI for catalog discovery, query shortcuts, and contract plans."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from pydantic import ValidationError

from contracts.models import QueryPlan
from .engine import IfcQueryEngine


def _parser():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ["inspect", "ingest", "execute", "count", "sum", "mean", "min", "max", "lookup", "rank"]:
        command = commands.add_parser(name)
        command.add_argument("file", type=Path, help="Source IFC file")
        command.add_argument("--cache-dir", type=Path, help="Optional content/version-keyed extraction cache")
        command.add_argument("--output", "-o", type=Path, help="Write JSON here instead of stdout")
        command.add_argument("--bundle-out", type=Path, help="Export the knowledge/evidence bundle after execution")
        command.add_argument("--source-collection", default="local")
        command.add_argument("--attribution", default="unspecified")
        command.add_argument("--license", default="unspecified")
        if name == "execute":
            command.add_argument("--plan", required=True, type=Path, help="Shared QueryPlan JSON")
        if name not in {"inspect", "ingest", "execute"}:
            command.add_argument("target", help="IFC class (IfcDoor) or concept (door)")
            command.add_argument("--storey", help="Unambiguous storey name, GUID, STEP ID, or catalog ID")
            command.add_argument("--entity", help="Unambiguous entity name, GUID, STEP ID, or catalog ID")
            command.add_argument("--hierarchy", choices=["all_matches", "topmost_matches", "leaves"], default="all_matches")
            command.add_argument("--plan-out", type=Path, help="Export the resolved QueryPlan")
            if name != "count":
                command.add_argument("--property", required=True, help="Catalog property key or exact display path")
            if name in {"sum", "mean", "min", "max"}:
                command.add_argument("--unit", help="Output unit, e.g. m, m2, m3, mm, ft2")
            if name == "rank":
                command.add_argument("--limit", type=int, default=10)
                command.add_argument("--direction", choices=["ascending", "descending"], default="descending")
    return parser


def _write(value, output):
    text = value.model_dump_json(indent=2) if hasattr(value, "model_dump_json") else json.dumps(value, indent=2, ensure_ascii=False)
    if output:
        output.write_text(text + "\n", encoding="utf-8")
    else:
        print(text)


def main(argv=None):
    args = _parser().parse_args(argv)
    # An output typo must not overwrite the source model or input plan.
    inputs = {args.file.resolve()}
    if args.command == "execute":
        inputs.add(args.plan.resolve())
    outputs = [getattr(args, key, None) for key in ["output", "bundle_out", "plan_out"]]
    resolved = [p.resolve() for p in outputs if p is not None]
    if inputs.intersection(resolved) or len(set(resolved)) != len(resolved):
        print("Output paths must be distinct and must not overwrite input files.", file=sys.stderr)
        return 2
    try:
        engine = IfcQueryEngine.open(args.file, cache_dir=args.cache_dir, source_collection=args.source_collection,
                                     attribution=args.attribution, license=args.license)
        if args.command == "inspect":
            output = engine.inspect()
        elif args.command == "ingest":
            output = engine.bundle
        else:
            if args.command == "execute":
                plan = QueryPlan.model_validate_json(args.plan.read_text(encoding="utf-8"))
                output = engine.execute(plan)
            else:
                kwargs = {name: getattr(args, name) for name in
                          ["property", "storey", "entity", "hierarchy", "unit", "limit", "direction"] if hasattr(args, name)}
                if args.plan_out:
                    from .engine import QueryError
                    try:
                        plan = engine.plan(args.target, operation=args.command, **kwargs)
                    except QueryError:
                        output = engine.query(args.target, operation=args.command, **kwargs)
                    else:
                        _write(plan, args.plan_out)
                        output = engine.execute(plan)
                else:
                    output = engine.query(args.target, operation=args.command, **kwargs)
        if args.bundle_out:
            _write(engine.bundle, args.bundle_out)
        _write(output, args.output)
        return 0 if getattr(output, "status", "answered") == "answered" else 1
    except (OSError, ValueError, RuntimeError, ValidationError) as exc:
        print(json.dumps({"error": type(exc).__name__, "message": str(exc)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
