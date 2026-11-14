"""One disposable renderer process, invoked by the local HTTP adapter."""
from __future__ import annotations

import json
from pathlib import Path
import sys

from .render import PreviewError, render_dxf


def main():
    source, output, page = sys.argv[1:]
    try:
        preview = render_dxf(Path(source), int(page))
        result = {"preview": preview.model_dump(mode="json")}
    except PreviewError as exc:
        result = {"error": {"status": exc.status, "code": exc.code, "message": exc.message}}
    except Exception:
        result = {"error": {"status": 422, "code": "dxf_render_failed",
                            "message": "This DXF layout could not be rendered. Try a PDF export."}}
    Path(output).write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
