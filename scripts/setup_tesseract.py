"""Install the pinned Windows OCR engine and official fast language data locally.

Usage: .venv\\Scripts\\python.exe scripts/setup_tesseract.py
       .venv\\Scripts\\python.exe scripts/setup_tesseract.py --check

The installer is from the official tesseract-ocr GitHub release. Its SHA-256 is
also published in https://github.com/ScoopInstaller/Main/blob/master/bucket/tesseract.json.
Language models: https://github.com/tesseract-ocr/tessdata_fast/tree/4.1.0
Engine and data are Apache-2.0 licensed. A pinned official 7-Zip MSI is unpacked
as an administrative image, then used to extract the OCR payload. The Tesseract
installer is never executed. No global PATH or product installation is needed.
7-Zip licensing: https://www.7-zip.org/license.txt
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request


ROOT = Path(__file__).resolve().parents[1]
INSTALL_DIRECTORY = ROOT / ".tools" / "tesseract"
DOWNLOAD_DIRECTORY = ROOT / "build" / "downloads"
INSTALLER_NAME = "tesseract-ocr-w64-setup-5.5.3.20260724.exe"
INSTALLER_URL = "https://github.com/tesseract-ocr/tesseract/releases/download/5.5.3/" + INSTALLER_NAME
INSTALLER_SHA256 = "bee9e3434bd94fd65387d9be28cd467a41f61b1275383b55b0f59a1331270ae4"
SEVENZIP_MSI_NAME = "7z2606-x64.msi"
SEVENZIP_MSI_URL = "https://github.com/ip7z/7zip/releases/download/26.06/" + SEVENZIP_MSI_NAME
SEVENZIP_MSI_SHA256 = "6dc822569e777d9a3ecd5ffcbc22b55600af87e6c5d9810a64e8566cf5a4af9f"
SEVENZIP_DIRECTORY = ROOT / ".tools" / "7zip-extract"
TESSDATA_REF = "4.1.0"
TESSDATA_BASE = f"https://raw.githubusercontent.com/tesseract-ocr/tessdata_fast/{TESSDATA_REF}"
DEFAULT_LANGUAGES = ("eng", "fin", "deu", "fra", "ita", "swe")


class SetupError(RuntimeError):
    pass


def _inside_workspace(path: Path) -> Path:
    """Verify every filesystem target before downloading or installing into it."""
    resolved = path.resolve()
    if not resolved.is_relative_to(ROOT.resolve()) or resolved == ROOT.resolve():
        raise SetupError("Setup target escapes the repository: " + str(path))
    # Dedicated directories should never alias another workspace location either.
    if resolved != path.absolute():
        raise SetupError("Setup targets must not be symlinks or redirected directories: " + str(path))
    return resolved


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _hidden() -> dict:
    if os.name != "nt":
        return {}
    info = subprocess.STARTUPINFO()
    info.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    info.wShowWindow = subprocess.SW_HIDE
    return {"startupinfo": info, "creationflags": subprocess.CREATE_NO_WINDOW}


def _run(arguments, *, timeout: float = 15) -> subprocess.CompletedProcess:
    return subprocess.run(arguments, check=True, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=timeout,
                          shell=False, **_hidden())


def _version(executable: Path) -> str | None:
    if not executable.is_file():
        return None
    try:
        result = _run([str(executable), "--version"])
        line = result.stdout.splitlines()[0].strip()
        return line if line.startswith("tesseract ") else None
    except (OSError, subprocess.SubprocessError, IndexError):
        return None


def _download(url: str, destination: Path, *, expected_sha256: str | None = None,
              maximum_bytes: int = 256 * 1024 * 1024) -> str:
    destination = _inside_workspace(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if expected_sha256 and destination.is_file() and _sha256(destination) == expected_sha256:
        return expected_sha256
    request = urllib.request.Request(url, headers={"User-Agent": "AskThePlan-OCR-Setup/1.0"})
    temporary_path = None
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            if not response.geturl().startswith("https://"):
                raise SetupError("Refusing a non-TLS download redirect.")
            with tempfile.NamedTemporaryFile(dir=destination.parent, suffix=".download", delete=False) as temporary:
                temporary_path = Path(temporary.name)
                digest, size = hashlib.sha256(), 0
                for chunk in iter(lambda: response.read(1024 * 1024), b""):
                    size += len(chunk)
                    if size > maximum_bytes:
                        raise SetupError("Download exceeds its explicit size limit.")
                    digest.update(chunk)
                    temporary.write(chunk)
        actual = digest.hexdigest()
        if size < 1024:
            raise SetupError("Downloaded file is unexpectedly small.")
        if expected_sha256 and actual != expected_sha256:
            raise SetupError("Installer checksum mismatch; the downloaded program will not be executed.")
        temporary_path.replace(destination)
        return actual
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def _load_provenance(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def _install_engine(target: Path) -> tuple[Path, str]:
    executable = _inside_workspace(target / "tesseract.exe")
    version = _version(executable)
    if version:
        print("Reusing local engine:", version)
        return executable, version
    if target.exists() and (not target.is_dir() or any(target.iterdir())):
        raise SetupError("The dedicated OCR directory is nonempty but has no working engine. "
                         "Inspect it before retrying: " + str(target))
    installer = DOWNLOAD_DIRECTORY / INSTALLER_NAME
    print("Downloading and verifying the pinned Windows installer...")
    _download(INSTALLER_URL, installer, expected_sha256=INSTALLER_SHA256)
    # Recheck immediately before extraction, including a previously cached file.
    if _sha256(installer) != INSTALLER_SHA256:
        raise SetupError("Installer changed after verification; extraction cancelled.")
    sevenzip = _portable_sevenzip()
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        # The NSIS archive is inspected by 7-Zip, never launched as a process.
        _run([str(sevenzip), "x", str(installer), "-o" + str(target), "-y"], timeout=120)
    except subprocess.TimeoutExpired:
        raise SetupError("Portable extraction exceeded 120 seconds. Inspect the dedicated OCR directory "
                         "before retrying; no directory was deleted.") from None
    version = _version(executable)
    if not version:
        raise SetupError("Portable extraction did not produce a working engine in " + str(target))
    return executable, version


def _portable_sevenzip() -> Path:
    """Unpack official MSI files without installing a Windows product globally."""
    target = _inside_workspace(SEVENZIP_DIRECTORY)
    executable = _inside_workspace(target / "Files" / "7-Zip" / "7z.exe")
    library = _inside_workspace(executable.parent / "7z.dll")
    if executable.is_file() and library.is_file():
        try:
            _run([str(executable), "i"])
            return executable
        except (OSError, subprocess.SubprocessError):
            pass
    if target.exists() and (not target.is_dir() or any(target.iterdir())):
        raise SetupError("The dedicated 7-Zip extraction directory is nonempty but unusable. "
                         "Inspect it before retrying: " + str(target))
    print("Downloading and verifying the official portable-extraction helper...")
    msi = DOWNLOAD_DIRECTORY / SEVENZIP_MSI_NAME
    _download(SEVENZIP_MSI_URL, msi, expected_sha256=SEVENZIP_MSI_SHA256)
    if _sha256(msi) != SEVENZIP_MSI_SHA256:
        raise SetupError("7-Zip MSI changed after verification; extraction cancelled.")
    target.parent.mkdir(parents=True, exist_ok=True)
    msiexec = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "msiexec.exe"
    try:
        _run([str(msiexec), "/a", str(msi), "/qn", "TARGETDIR=" + str(target)], timeout=120)
    except (OSError, subprocess.SubprocessError):
        raise SetupError("Windows could not create the local 7-Zip administrative image. "
                         "No global install or elevation was requested. Check environment policy "
                         "or use an approved portable 7-Zip distribution in: " + str(target)) from None
    if not executable.is_file() or not library.is_file():
        raise SetupError("7-Zip administrative extraction did not create Files/7-Zip/7z.exe and 7z.dll.")
    _run([str(executable), "i"])
    return executable


def _install_languages(target: Path, languages: list[str], version: str) -> None:
    tessdata = _inside_workspace(target / "tessdata")
    tessdata.mkdir(parents=True, exist_ok=True)
    provenance_path = _inside_workspace(target / "setup-provenance.json")
    provenance = _load_provenance(provenance_path)
    prior_models = provenance.get("models", {})
    models = dict(prior_models) if isinstance(prior_models, dict) else {}
    for language in languages:
        destination = _inside_workspace(tessdata / f"{language}.traineddata")
        url = f"{TESSDATA_BASE}/{language}.traineddata"
        prior = models.get(language, {})
        if (isinstance(prior, dict) and prior.get("url") == url
                and destination.is_file() and _sha256(destination) == prior.get("sha256")):
            print("Language already verified:", language)
            continue
        print("Downloading official fast language data:", language)
        cached = DOWNLOAD_DIRECTORY / f"tessdata-fast-{TESSDATA_REF}-{language}.traineddata"
        digest = _download(url, cached, maximum_bytes=64 * 1024 * 1024)
        # Atomic publication leaves an existing installed model intact on failure.
        with tempfile.NamedTemporaryFile(dir=tessdata, suffix=".traineddata", delete=False) as temporary:
            temporary_path = Path(temporary.name)
            with cached.open("rb") as incoming:
                for chunk in iter(lambda: incoming.read(1024 * 1024), b""):
                    temporary.write(chunk)
        try:
            if _sha256(temporary_path) != digest:
                raise SetupError("Language data changed during copy: " + language)
            temporary_path.replace(destination)
        finally:
            temporary_path.unlink(missing_ok=True)
        models[language] = {"url": url, "ref": TESSDATA_REF, "sha256": digest}
    # A working engine may have existed before this script. Record the observed
    # executable hash; the pinned installer is a reference, not proof of how that
    # pre-existing binary was originally installed.
    provenance.update({"engine_version": version, "engine_sha256": _sha256(target / "tesseract.exe"),
                       "installer_reference_url": INSTALLER_URL,
                       "installer_reference_sha256": INSTALLER_SHA256,
                       "sevenzip_reference_url": SEVENZIP_MSI_URL,
                       "sevenzip_reference_sha256": SEVENZIP_MSI_SHA256, "models": models})
    provenance_path.write_text(json.dumps(provenance, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _check(target: Path, languages: list[str]) -> bool:
    executable = _inside_workspace(target / "tesseract.exe")
    version = _version(executable)
    if not version:
        print("No working repository-local Tesseract. Run this script without --check.")
        return False
    print("Engine:", version)
    print("Executable:", executable)
    try:
        result = _run([str(executable), "--list-langs", "--tessdata-dir", str(target / "tessdata")])
    except (OSError, subprocess.SubprocessError):
        print("Cannot list local OCR languages; rerun setup.")
        return False
    available = {line.strip() for line in result.stdout.splitlines()[1:] if line.strip()}
    print("Languages:", ", ".join(sorted(available)) or "none")
    missing = set(languages) - available
    if missing:
        print("Missing requested languages:", ", ".join(sorted(missing)))
    return not missing


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--languages", nargs="+", default=list(DEFAULT_LANGUAGES), metavar="CODE",
                        help="Official tessdata_fast codes (default: eng fin deu fra ita swe).")
    parser.add_argument("--check", action="store_true", help="Report local engine/languages without downloading.")
    parser.add_argument("--engine-only", action="store_true", help="Install only the engine; skip language downloads.")
    args = parser.parse_args(argv)
    if any(not re.fullmatch(r"[a-z][a-z0-9_]*", language) for language in args.languages):
        parser.error("Language codes must contain lowercase letters, digits or underscores.")
    languages = list(dict.fromkeys(args.languages))
    if os.name != "nt":
        print("This bootstrap installs the Windows 64-bit build. On Debian/Ubuntu use:")
        print("  sudo apt install tesseract-ocr " + " ".join("tesseract-ocr-" + code for code in languages))
        print("On macOS use: brew install tesseract tesseract-lang")
        print("Then verify: tesseract --version; tesseract --list-langs")
        return 1 if args.check else 0
    if platform.machine().lower() not in {"amd64", "x86_64"}:
        parser.error("The pinned installer requires Windows x64.")
    try:
        target = _inside_workspace(INSTALL_DIRECTORY)
        _inside_workspace(DOWNLOAD_DIRECTORY)
        if args.check:
            return 0 if _check(target, languages) else 1
        _, version = _install_engine(target)
        if not args.engine_only:
            _install_languages(target, languages, version)
        return 0 if _check(target, [] if args.engine_only else languages) else 1
    except (SetupError, OSError, urllib.error.URLError, subprocess.SubprocessError) as exc:
        print("OCR setup failed:", str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
