"""Check project Markdown links, images, headings and source-line anchors offline.

Uses Git's tracked/non-ignored Markdown inventory, including nested experiment
reports. Without Git, checks the maintained documentation directories. Drawing
archives are inputs, not project documentation. This checks the Markdown forms
used here, not every Markdown extension or external URL availability.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from html import unescape
from pathlib import Path
import os
import re
import subprocess
import sys
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
CORPORA = {"junction-dataset", "junction-dataset-preview"}
LABEL = re.compile(r"!?\[([^\]\n]*)\]")
DEFINITION = re.compile(r"(?m)^ {0,3}\[([^\]\n]+)\]:[ \t]*(<[^>\n]+>|\S+)")


def documents(root: Path = ROOT) -> list[Path]:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "ls-files", "--cached", "--others",
             "--exclude-standard", "-z", "--", "*.md"],
            check=True, capture_output=True,
        )
        paths = [root / name for name in result.stdout.decode("utf-8").split("\0") if name]
    except (OSError, subprocess.CalledProcessError):
        paths = [*root.glob("*.md"), *root.glob("dataset/*.md")]
        for directory in ("docs", "contracts", "experiments"):
            paths.extend((root / directory).rglob("*.md"))
        paths.extend(root.glob("frontend/*.md"))
    # Distributed archives are inputs, even if a drawing was accidentally added.
    return sorted({p for p in paths if p.is_file() and not (
        p.relative_to(root).parts[0] == "dataset" and len(p.relative_to(root).parts) > 2
    )})


def prose(content: str, *, inline_code: bool = True) -> str:
    """Mask code/comments while preserving offsets for useful line diagnostics."""
    lines = []
    fence = ""
    for line in content.splitlines(keepends=True):
        marker = re.match(r"^ {0,3}(`{3,}|~{3,})(.*)$", line.rstrip("\r\n"))
        in_fence = bool(fence)
        if marker:
            run, tail = marker.groups()
            if not fence:
                fence = run
            elif run[0] == fence[0] and len(run) >= len(fence) and not tail.strip():
                fence = ""
        if in_fence or fence or marker:
            lines.append(re.sub(r"[^\r\n]", " ", line))
        else:
            lines.append(line)
    visible = "".join(lines)
    visible = re.sub(r"<!--[\s\S]*?-->", lambda m: re.sub(r"[^\r\n]", " ", m[0]), visible)
    if inline_code:
        visible = re.sub(r"(?<!`)(`+)(?!`)([\s\S]*?)(?<!`)\1(?!`)",
                         lambda m: re.sub(r"[^\r\n]", " ", m[0]), visible)
    return visible


def _reference(label: str) -> str:
    return " ".join(label.split()).casefold()


def _destination(content: str, start: int) -> tuple[str, int]:
    """Read an angle-bracket or balanced-parenthesis Markdown destination."""
    index = start
    while index < len(content) and content[index] in " \t":
        index += 1
    if index < len(content) and content[index] == "<":
        end = content.find(">", index + 1)
        if end != -1:
            return content[index + 1:end], end + 1
        return "", index
    begin, depth = index, 0
    while index < len(content):
        char = content[index]
        if char == "\\" and index + 1 < len(content):
            index += 2
            continue
        if (char == ")" and depth == 0) or (char.isspace() and depth == 0):
            break
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
        index += 1
    return content[begin:index], index


def links(content: str):
    visible = prose(content)
    definitions = {_reference(m[1]): m[2].strip("<>") for m in DEFINITION.finditer(visible)}
    consumed = 0
    for match in LABEL.finditer(visible):
        if match.start() < consumed:
            continue
        end = match.end()
        if visible[end:end + 1] == ":":
            continue
        target = None
        if visible[end:end + 1] == "(":
            target, stop = _destination(visible, end + 1)
            closing = re.match(r'''^[ \t]*(?:"[^"\n]*"|'[^'\n]*'|\([^\n]*?\))?[ \t]*\)''', visible[stop:])
            if not closing:
                continue
            consumed = stop + closing.end()
        elif visible[end:end + 1] == "[":
            stop = visible.find("]", end + 1)
            if stop != -1:
                consumed = stop + 1
                label = visible[end + 1:stop] or match[1]
                target = definitions.get(_reference(label))
                if target is None:
                    yield None, content.count("\n", 0, match.start()) + 1, label
        else:
            target = definitions.get(_reference(match[1]))
        if target is not None:
            target = re.sub(r"\\([!\"#$%&'()*+,\-./:;<=>?@\[\]\\^_`{|}~])", r"\1", target)
            yield unescape(target), content.count("\n", 0, match.start()) + 1, ""


def anchors(path: Path) -> set[str]:
    content = path.read_text(encoding="utf-8")
    visible = prose(content, inline_code=False)
    found = set(re.findall(r'''<[a-zA-Z][^>]*\b(?:id|name)=["']([^"']+)["']''', prose(content)))
    lines = visible.splitlines()
    for index, line in enumerate(lines):
        match = re.match(r"^ {0,3}#{1,6}\s+(.+?)(?:\s+#+)?\s*$", line)
        text = match[1] if match else ""
        if not text and index + 1 < len(lines) and line.strip() and re.fullmatch(r" {0,3}(?:=+|-+)\s*", lines[index + 1]):
            text = line.strip()
        if not text:
            continue
        text = re.sub(r"!?\[([^\]]+)\]\([^)]*\)", r"\1", text)
        text = unescape(re.sub(r"<[^>]*>", "", text)).lower()
        base = re.sub(r"[^\w\s-]", "", text).replace(" ", "-")
        slug, suffix = base, 0
        while slug in found:
            suffix += 1
            slug = f"{base}-{suffix}"
        found.add(slug)
    return found


@dataclass
class Report:
    documents: int = 0
    checked: int = 0
    optional: int = 0
    failures: list[str] = field(default_factory=list)


def check(paths: list[Path], root: Path = ROOT) -> Report:
    report = Report(documents=len(paths))
    anchor_cache: dict[Path, set[str]] = {}
    line_counts: dict[Path, int] = {}
    directory_names: dict[Path, set[str]] = {}
    for doc in paths:
        content = doc.read_text(encoding="utf-8")
        for target, line, missing_reference in links(content):
            label = f"{doc.relative_to(root).as_posix()}:{line}: {target or missing_reference}"
            if target is None:
                report.failures.append(f"Missing reference definition: {label}")
                continue
            try:
                parsed = urlsplit(target)
            except ValueError:
                report.failures.append(f"Invalid target URL: {label}")
                continue
            if parsed.scheme or parsed.netloc:
                continue
            report.checked += 1
            location, fragment = unquote(parsed.path), unquote(parsed.fragment)
            base = root if location.startswith("/") else doc.parent
            requested = Path(os.path.abspath(base / location.lstrip("/"))) if location else doc
            path = requested.resolve()
            if not path.is_relative_to(root.resolve()):
                report.failures.append(f"Target outside repository: {label}")
                continue
            # Windows resolves wrong-case names; reject spellings that break on Linux.
            cursor = root.resolve()
            mismatch = False
            if requested.is_relative_to(cursor):
                for part in requested.relative_to(cursor).parts:
                    if not cursor.is_dir():
                        break
                    if cursor not in directory_names:
                        directory_names[cursor] = {item.name for item in cursor.iterdir()}
                    names = directory_names[cursor]
                    if part not in names:
                        if part.casefold() in {name.casefold() for name in names}:
                            report.failures.append(f"Case mismatch in target: {label}")
                            mismatch = True
                        break
                    cursor = cursor / part
            if mismatch:
                continue
            relative = path.relative_to(root.resolve())
            if not path.exists():
                if (len(relative.parts) > 2 and relative.parts[0] == "dataset"
                        and relative.parts[1] in CORPORA
                        and not (root / Path(*relative.parts[:2])).exists()):
                    report.optional += 1
                else:
                    report.failures.append(f"Missing target: {label}")
                continue
            if not fragment:
                continue
            source_lines = re.fullmatch(r"L(\d+)(?:-L(\d+))?", fragment)
            if source_lines and path.is_file():
                if path not in line_counts:
                    with path.open("rb") as stream:
                        line_counts[path] = sum(1 for _ in stream)
                first, last = int(source_lines[1]), int(source_lines[2] or source_lines[1])
                if not 1 <= first <= last <= line_counts[path]:
                    report.failures.append(f"Invalid source lines: {label}")
            elif path.suffix.lower() == ".md":
                if path not in anchor_cache:
                    anchor_cache[path] = anchors(path)
                if fragment not in anchor_cache[path]:
                    report.failures.append(f"Missing heading: {label}")
    return report


def main() -> int:
    report = check(documents())
    for failure in report.failures:
        print(failure)
    print(f"Checked {report.documents} documents and {report.checked} local links/images; "
          f"{report.optional} optional corpus links skipped; {len(report.failures)} errors.")
    return 1 if report.failures else 0


if __name__ == "__main__":
    sys.exit(main())
