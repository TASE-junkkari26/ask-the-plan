"""Optional local source-label anchors, independent of model routing.

OCR words are observations. Their original spelling, confidence and source-pixel
boxes are retained; this tool does not correct IDs or prove a complete inventory.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from time import perf_counter
from typing import Sequence

from contracts.models import OCRResult, OCRTextSpan
from drawing_preprocessor.ocr import recognize, tesseract_version
from .images import PreparedImage
from .region_tools import _open_native


@dataclass(frozen=True)
class SourceLabels:
    source_sha256: str
    frame_id: str
    width: int
    height: int
    ocr: OCRResult
    elapsed_ms: float

    def to_metadata(self) -> dict:
        return {"source_sha256": self.source_sha256, "frame_id": self.frame_id,
                "width": self.width, "height": self.height,
                "coordinate_system": "display_pixels_top_left",
                "ocr": self.ocr.model_dump(mode="json"), "elapsed_ms": self.elapsed_ms}

    def near(self, box: Sequence[float], *, padding: float = 0,
             min_confidence: float = 0) -> tuple[OCRTextSpan, ...]:
        """Filter observed source words near a region without rewriting them."""
        if (not isinstance(box, (list, tuple)) or len(box) != 4
                or any(type(v) not in (int, float) or not math.isfinite(v) for v in box)):
            raise ValueError("Label lookup requires four finite source-pixel bounds")
        a,b,c,d = box
        if not (0 <= a < c <= self.width and 0 <= b < d <= self.height):
            raise ValueError("Label lookup must stay inside the source frame")
        if (type(padding) not in (int,float) or not math.isfinite(padding) or not 0 <= padding <= 1024
                or type(min_confidence) not in (int,float) or not math.isfinite(min_confidence)
                or not 0 <= min_confidence <= 1):
            raise ValueError("Label lookup padding or confidence threshold is invalid")
        result = []
        for span in self.ocr.spans:
            if min_confidence > 0 and (span.confidence is None or span.confidence < min_confidence):
                continue
            x0,y0,x1,y1 = span.bbox
            if x1 > a-padding and x0 < c+padding and y1 > b-padding and y0 < d+padding:
                result.append(span)
        return tuple(result)


def read_source_labels(image: PreparedImage, *, languages: str = "eng+fin",
                       timeout_seconds: float = 30) -> SourceLabels:
    """Read optional Tesseract words from a trusted native PreparedImage.

    Uses the existing preprocessor OCR adapter/discovery, with no installation,
    network request or credentials. The host owns source lifetime. Missing and
    failed OCR remain explicit statuses rather than successful empty extraction.
    """
    if (type(timeout_seconds) not in (int,float) or not math.isfinite(timeout_seconds)
            or not 0 < timeout_seconds <= 600):
        raise ValueError("OCR timeout must be finite and between zero and 600 seconds")
    started = perf_counter()
    # Verify source hash, original dimensions and native RGB format before OCR.
    with _open_native(image):
        pass
    frame = "display:sha256:" + image.sha256
    result = recognize(image.path, frame_id=frame, width=image.width, height=image.height,
        languages=languages, timeout=timeout_seconds, version=tesseract_version())
    if any(s.frame_id != frame or s.bbox[2] > image.width or s.bbox[3] > image.height
           for s in result.spans):
        raise ValueError("OCR words do not belong to the prepared source frame")
    return SourceLabels(image.sha256, frame, image.width, image.height, result,
                        (perf_counter()-started)*1000)
