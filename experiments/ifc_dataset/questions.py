"""Load task inputs only; reference values are deliberately a separate module."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path

from scripts.classify_questions import ifc_quantitative

ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Task:
    line: int
    path: str
    question: str
    answer_type: str
    unit: str | None
    family: str
    question_scope: str

    def as_dict(self):
        return asdict(self)


def load_tasks(dataset: Path) -> tuple[list[Task], str]:
    """Select literal .ifc paths, never answer values or inferred PDF scopes."""
    taxonomy = json.loads((ROOT / "scripts/question_classification_taxonomy.json").read_text())["ifc_bench"]
    payload = (dataset / "questions.jsonl").read_bytes()
    result = []
    for line, raw in enumerate(payload.decode("utf-8-sig").splitlines(), 1):
        if not raw.strip():
            continue
        value = json.loads(raw)
        path = str(value["path"]).replace("\\", "/")
        parts = Path(path).parts
        if len(parts) < 3 or parts[:2] not in {("data", "ifc_bench"), ("data", "ifc_models")}:
            continue
        if Path(path).suffix.casefold() != ".ifc":
            continue
        if ".." in parts or Path(path).is_absolute():
            raise ValueError("Question paths must stay within the supplied dataset.")
        question, answer_type = value["question"], value["type"]
        if parts[1] == "ifc_bench":
            family = taxonomy[question]
            scope = "question-defined; preserve literal model/floor/room/object restrictions"
        else:
            family, _, scope = ifc_quantitative(question, answer_type)
        result.append(Task(line, path, question, answer_type, value.get("unit"), family, scope))
    return result, hashlib.sha256(payload).hexdigest()


def select_tasks(tasks: list[Task], *, lines=(), families=(), models=(), limit=None,
                 one_per_family=False) -> list[Task]:
    wanted = set(lines)
    if wanted - {task.line for task in tasks}:
        raise ValueError("Every selected line must reference an IFC question.")
    if set(families) - {task.family for task in tasks}:
        raise ValueError("An unknown exact family was selected; use --list to inspect families.")
    known_models = {task.path for task in tasks} | {Path(task.path).name for task in tasks}
    if set(models) - known_models:
        raise ValueError("An unknown source model was selected; use an exact relative path or basename.")
    selected = [task for task in tasks if (not wanted or task.line in wanted)
                and (not families or task.family in families)
                and (not models or task.path in models or Path(task.path).name in models)]
    if one_per_family:
        seen = set()
        selected = [task for task in selected if not (task.family in seen or seen.add(task.family))]
    if limit is not None:
        if limit < 1:
            raise ValueError("Limit must be positive.")
        selected = selected[:limit]
    if not selected:
        raise ValueError("The selectors matched no IFC questions.")
    return selected
