"""Render a source layout with ezdxf, without loading external drawing assets."""
from __future__ import annotations

from collections import Counter
from contextlib import redirect_stdout
import hashlib
import math
from pathlib import Path
import xml.etree.ElementTree as ET

from contracts.models import DxfPreviewResponse

MAX_DXF_BYTES = 35 * 1024 * 1024
MAX_DXF_BODY_BYTES = MAX_DXF_BYTES + 1024 * 1024
MAX_SVG_BYTES = 8 * 1024 * 1024
MAX_ENTITIES = 200_000


class PreviewError(Exception):
    """Only fixed, public messages cross the worker/HTTP boundary."""

    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


def render_dxf(path: Path, page: int = 1) -> DxfPreviewResponse:
    # Import lazily: image/IFC APIs still start without the optional DXF package.
    try:
        import ezdxf
        from ezdxf.addons.drawing import Frontend, RenderContext, layout, svg
        from ezdxf.addons.drawing.config import BackgroundPolicy, Configuration, ImagePolicy
    except ImportError:
        raise PreviewError(503, "dxf_not_installed", "Install the backend api extra to preview DXF files.") from None

    if not 0 < path.stat().st_size <= MAX_DXF_BYTES:
        raise PreviewError(413, "dxf_size", "Choose a nonempty DXF file no larger than 35 MiB.")
    try:
        # No recovery/audit mutation: invalid sources must be corrected explicitly.
        doc = ezdxf.readfile(path, errors="strict")
    except (OSError, ezdxf.DXFError, UnicodeError, ValueError):
        raise PreviewError(422, "invalid_dxf", "This DXF is damaged or unsupported. Try a fresh DXF or PDF export.") from None
    if len(doc.entitydb) > MAX_ENTITIES:
        raise PreviewError(413, "dxf_complexity", "This DXF exceeds the preview entity limit. Export a smaller layout.")
    # Empty default paper layouts do not become blank pages in the viewer.
    names = [name for name in doc.layouts.names_in_taborder() if len(doc.layouts.get(name))]
    if not names:
        raise PreviewError(422, "empty_dxf", "This DXF has no drawing entities in its layouts.")
    if len(names) > 128 or any(len(name) > 255 for name in names):
        raise PreviewError(413, "dxf_layouts", "This DXF exceeds the preview layout limit.")
    if not 1 <= page <= len(names):
        raise PreviewError(422, "invalid_layout", "Choose an available DXF layout.")

    omissions: Counter[str] = Counter()
    samples: list[str] = []
    messages: list[str] = []

    class RenderDiagnostics:
        def write(self, text):
            if text.strip() and not messages:
                messages.append("Some DXF features could not be rendered faithfully.")
            return len(text)

        def flush(self):
            pass

    class PreviewFrontend(Frontend):
        drawn = 0

        def draw_entity(self, entity, properties):
            self.drawn += 1
            if self.drawn > MAX_ENTITIES:
                raise PreviewError(413, "dxf_complexity", "Expanded DXF blocks exceed the preview entity limit.")
            kind = entity.dxftype()
            if kind in {"IMAGE", "PDFUNDERLAY", "DWFUNDERLAY", "DGNUNDERLAY", "OLE2FRAME",
                        "3DSOLID", "BODY", "REGION", "SURFACE", "PLANESURFACE",
                        "EXTRUDEDSURFACE", "LOFTEDSURFACE", "REVOLVEDSURFACE", "SWEPTSURFACE"}:
                self.skip_entity(entity, "external or embedded asset")
                return
            if kind == "INSERT":
                block = entity.block()
                if block is not None and (block.block.is_xref or block.block.is_xref_overlay):
                    self.skip_entity(entity, "external reference")
                    return
            super().draw_entity(entity, properties)

        def skip_entity(self, entity, msg):
            if msg == "invisible":
                return  # Respect the selected layout's source visibility.
            kind = entity.dxftype()
            omissions[kind] += 1
            handle = entity.dxf.get("handle")
            if handle and len(samples) < 12:
                samples.append(f"{kind} handle {handle}")

        def log_message(self, message):
            # Keep arbitrary library diagnostics (which may contain paths) private.
            if len(messages) < 1:
                messages.append("Some DXF features could not be rendered faithfully.")

    config = Configuration(background_policy=BackgroundPolicy.WHITE,
                           image_policy=ImagePolicy.IGNORE, pdsize=1,
                           hatching_timeout=5.0)
    backend = svg.SVGBackend()
    frontend = PreviewFrontend(RenderContext(doc), backend, config=config)
    try:
        selected = doc.layouts.get(names[page - 1])
        with redirect_stdout(RenderDiagnostics()):
            frontend.draw_layout(selected)
        box = backend.player().bbox()
        if not box.has_data:
            raise PreviewError(422, "empty_layout", "This DXF layout has no renderable visible geometry.")
        # Fit onto a useful plot size even when model units are metres. Treating
        # one model unit as one paper millimetre makes these plans' lines too wide.
        size = box.size
        longest = max(size.x, size.y, 1e-9)
        plot = layout.Page(420 * size.x / longest + 4, 420 * size.y / longest + 4,
                           margins=layout.Margins.all(2))
        root = backend.get_xml_root_element(plot)
        view_box = [float(n) for n in root.get("viewBox", "").split()]
        if len(view_box) != 4 or not all(math.isfinite(n) for n in view_box) or min(view_box[2:]) <= 0:
            raise PreviewError(422, "empty_layout", "This DXF layout has no renderable visible geometry.")
        extent_width, extent_height = view_box[2:]
        scale = min(4096 / max(extent_width, extent_height),
                    math.sqrt(8_000_000 / (extent_width * extent_height)))
        width = max(1, math.floor(extent_width * scale))
        height = max(1, math.floor(extent_height * scale))
        # Explicit pixels make browser preview and question rasterization agree.
        root.set("width", str(width))
        root.set("height", str(height))
        text = ET.tostring(root, encoding="unicode")
    except PreviewError:
        raise
    except Exception:
        raise PreviewError(422, "dxf_render_failed", "This DXF layout could not be rendered. Try a PDF export.") from None
    if len(text.encode("utf-8")) > MAX_SVG_BYTES:
        raise PreviewError(413, "dxf_output_size", "This DXF preview is too complex. Export a smaller layout.")
    warnings = []
    if omissions:
        warnings.append("Preview omitted source features: " + ", ".join(
            f"{kind} ({count})" for kind, count in sorted(omissions.items())) + ".")
        if samples:
            warnings.append("Example source anchors: " + ", ".join(samples) + ".")
    warnings.extend(messages)
    return DxfPreviewResponse(
        source_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        svg=text, width=width, height=height, page=page, layouts=names,
        insunits=doc.header.get("$INSUNITS"),
        status="partial" if warnings else "rendered", warnings=warnings,
    )
