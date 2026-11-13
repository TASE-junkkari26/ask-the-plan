"""Check local Markdown links and heading anchors; no network access required."""
from __future__ import annotations

from collections import Counter
from pathlib import Path
import re
import sys
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
LINK = re.compile(r"(?<!!)\[[^\]]*\]\((<[^>]+>|[^)\n]+)\)")


def documents() -> list[Path]:
    # Distributed drawing archives and their attribution/license files are inputs.
    return sorted([
        ROOT / "AGENTS.md", ROOT / "README.md",
        *ROOT.glob("docs/*.md"), *ROOT.glob("dataset/*.md"),
        ROOT / "frontend/README.md", ROOT / "contracts/examples/README.md",
    ])


def anchors(path: Path) -> set[str]:
    found: set[str] = set()
    duplicates: Counter[str] = Counter()
    fence = None
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.lstrip()
        if stripped.startswith(("```", "~~~")):
            marker = stripped[:3]
            fence = None if fence == marker else (marker if fence is None else fence)
            continue
        if fence is not None:
            continue
        match = re.match(r"^#{1,6}\s+(.+?)(?:\s+#+)?\s*$", line)
        if not match:
            continue
        text = re.sub(r"<[^>]*>", "", match.group(1)).lower()
        slug = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE).replace(" ", "-")
        count = duplicates[slug]
        duplicates[slug] += 1
        found.add(f"{slug}-{count}" if count else slug)
    return found


def main() -> int:
    failures: list[str] = []
    optional = 0
    checked = 0
    anchor_cache: dict[Path, set[str]] = {}
    paths = documents()
    for doc in paths:
        content = doc.read_text(encoding="utf-8")
        for match in LINK.finditer(content):
            target = match.group(1).strip().strip("<>")
            if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", target):
                continue
            checked += 1
            location, _, fragment = unquote(target).partition("#")
            path = (doc.parent / location).resolve() if location else doc.resolve()
            line = content.count("\n", 0, match.start()) + 1
            label = f"{doc.relative_to(ROOT)}:{line}: {target}"
            if not path.exists():
                # Corpus links are optional on a fresh clone; check them when
                # the corresponding archive directory is actually installed.
                relative = path.relative_to(ROOT) if path.is_relative_to(ROOT) else None
                if (
                    relative
                    and len(relative.parts) > 2
                    and relative.parts[0] == "dataset"
                    and relative.parts[1].startswith("junction-dataset")
                    and not (ROOT / Path(*relative.parts[:2])).exists()
                ):
                    optional += 1
                    continue
                failures.append(f"Missing target: {label}")
            elif fragment and path.suffix.lower() == ".md":
                if path not in anchor_cache:
                    anchor_cache[path] = anchors(path)
                if fragment not in anchor_cache[path]:
                    failures.append(f"Missing heading: {label}")
    for failure in failures:
        print(failure)
    print(f"Checked {len(paths)} documents and {checked} local links; {optional} optional corpus links skipped; {len(failures)} errors.")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
