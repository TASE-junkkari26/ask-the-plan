"""Backend adapter for registering source inspection with an agent tool loop."""
from pathlib import Path

from contracts.models import InspectRegionArgs
from .core import inspect_region


def inspection_tool_spec() -> dict:
    return {"type": "function", "function": {
        "name": "inspect_region",
        "description": (
            "Inspect original raster detail in a registered view. bbox is [left, top, right, bottom] "
            "in that view's full-resolution pixels, or overview pixels when coordinate_space is overview. "
            "Use the supplied view ID and dimensions. Returns a crop artifact, source transform and existing OCR. "
            "It does not count objects or establish physical scale."
        ),
        "parameters": InspectRegionArgs.model_json_schema(),
    }}


def execute_inspection_tool(manifest_path: str | Path, arguments: dict) -> dict:
    """The host supplies a trusted manifest; model arguments contain no paths."""
    args = InspectRegionArgs.model_validate(arguments)
    return inspect_region(manifest_path, **args.model_dump())
