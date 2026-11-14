"""Optional local OCR. Recognition never establishes scale or source truth."""
from __future__ import annotations

import csv
import io
import hashlib
import os
from pathlib import Path
import re
import shutil
import subprocess

from contracts.models import OCRResult, OCRTextSpan


def find_tesseract() -> str | None:
    """Prefer explicit backend configuration, then PATH, then local setup."""
    explicit = os.environ.get("TESSERACT_CMD")
    if explicit:
        return shutil.which(explicit)
    found = shutil.which("tesseract")
    if found:
        return found
    if os.name != "nt":
        return None
    local = Path(__file__).resolve().parents[1] / ".tools" / "tesseract" / "tesseract.exe"
    return str(local) if local.is_file() else None


def data_directory(executable: str) -> Path | None:
    configured = os.environ.get("TESSDATA_PREFIX")
    if configured:
        path = Path(configured)
        return path if path.is_dir() else None
    for path in (Path(executable).parent / "tessdata", Path("/usr/share/tesseract-ocr/5/tessdata"),
                 Path("/usr/share/tesseract-ocr/4.00/tessdata"), Path("/usr/share/tessdata")):
        if path.is_dir():
            return path
    return None


def language_fingerprint(languages: str) -> dict[str, str]:
    executable = find_tesseract()
    directory = data_directory(executable) if executable else None
    result = {}
    for language in languages.split("+"):
        path = directory / (language + ".traineddata") if directory else None
        if path is None or not path.is_file():
            result[language] = "not_located"
        else:
            digest = hashlib.sha256()
            with path.open("rb") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(chunk)
            result[language] = digest.hexdigest()
    return result


def tesseract_version() -> str | None:
    executable = find_tesseract()
    if executable is None:
        return None
    try:
        result = subprocess.run([executable, "--version"], capture_output=True, text=True,
                                encoding="utf-8", errors="replace", timeout=5, check=True)
        return result.stdout.splitlines()[0].strip() or "unknown"
    except (OSError, subprocess.SubprocessError, IndexError):
        return None


def recognize(image_path: Path, *, frame_id: str, width: int, height: int,
              languages: str, timeout: float, version: str | None) -> OCRResult:
    if not re.fullmatch(r"[A-Za-z0-9_]+(?:\+[A-Za-z0-9_]+)*", languages):
        raise ValueError("OCR languages must be Tesseract codes such as eng or eng+fin.")
    language_list = languages.split("+")
    executable = find_tesseract()
    if executable is None or version is None:
        return OCRResult(status="unavailable", engine="tesseract", languages=language_list,
                         warnings=["Tesseract is not available; install it and the requested language data to enable OCR."])
    try:
        directory = data_directory(executable)
        data_args = ["--tessdata-dir", str(directory)] if directory else []
        result = subprocess.run(
            [executable, str(image_path), "stdout", *data_args, "-l", languages, "--psm", "11", "tsv"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=timeout, check=True,
        )
    except subprocess.TimeoutExpired:
        return OCRResult(status="failed", engine="tesseract", version=version, languages=language_list,
                         warnings=["OCR exceeded its wall-time limit; image artifacts remain available."])
    except (OSError, subprocess.SubprocessError):
        return OCRResult(status="failed", engine="tesseract", version=version, languages=language_list,
                         warnings=["OCR failed; check the executable and requested language data."])
    spans = []
    invalid = False
    try:
        rows = csv.DictReader(io.StringIO(result.stdout), delimiter="\t")
        if not {"level", "text", "left", "top", "width", "height", "conf"}.issubset(rows.fieldnames or []):
            raise ValueError("Invalid TSV header")
        for row in rows:
            if row["level"] != "5" or not (row.get("text") or "").strip():
                continue
            try:
                left, top = int(row["left"]), int(row["top"])
                right, bottom = left + int(row["width"]), top + int(row["height"])
                score = float(row["conf"])
                spans.append(OCRTextSpan(
                    id=f"ocr-word-{len(spans) + 1}", text=row["text"], frame_id=frame_id,
                    bbox=(left, top, right, bottom), confidence=None if score < 0 else score / 100,
                    engine="tesseract",
                ))
                if left < 0 or top < 0 or right > width or bottom > height or right <= left or bottom <= top:
                    spans.pop()
                    invalid = True
            except (ValueError, TypeError, KeyError):
                invalid = True
    except (ValueError, csv.Error):
        invalid = True
    return OCRResult(status="partial" if invalid else "complete", engine="tesseract", version=version,
                     languages=language_list, spans=spans,
                     warnings=["Some OCR records were malformed or outside the source and were omitted."] if invalid else [])
