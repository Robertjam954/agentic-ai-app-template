"""Load `*.eval.yaml` / `*.eval.yml` / `*.eval.json` cases."""

import json
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from app.evals.models import EvalCase, EvalConfig, EvalLoadError

_SUFFIXES = (".eval.yaml", ".eval.yml", ".eval.json")


def load_config(directory: Path) -> EvalConfig:
    """Read `evals.config.yaml` beside the cases. Missing file uses defaults."""
    path = directory / "evals.config.yaml"
    if not path.is_file():
        alternate = directory / "evals.config.yml"
        path = alternate if alternate.is_file() else path
    if not path.is_file():
        return EvalConfig()
    data = _read_data(path)
    if data is None:
        return EvalConfig()
    if not isinstance(data, dict):
        raise EvalLoadError(f"{_display(directory, path)}: config must be a mapping")
    try:
        return EvalConfig.model_validate(data)
    except ValidationError as exc:
        raise EvalLoadError(f"{_display(directory, path)}: {exc}") from exc


def load_cases(directory: Path) -> list[EvalCase]:
    """Load every case file under `directory`, sorted by id."""
    cases: list[EvalCase] = []
    for path in _case_files(directory):
        cases.extend(_load_file(directory, path))
    seen: dict[str, str] = {}
    for case in cases:
        previous = seen.get(case.id)
        if previous is not None:
            raise EvalLoadError(
                f"duplicate eval id {case.id!r} in {previous} and {case.source}"
            )
        seen[case.id] = case.source
    cases.sort(key=lambda case: case.id)
    return cases


def select_cases(
    cases: list[EvalCase], case_ids: list[str], tags: list[str]
) -> list[EvalCase]:
    """Keep cases matching any tag and any id prefix.

    An id query matches that id or any id under it (`word_count` matches
    `word_count` and `word_count/nyc`, and does not match `word_count_extra`).
    Tags and ids combine: a case must match both filters when both are set.
    """
    selected = cases
    if tags:
        wanted = set(tags)
        selected = [case for case in selected if wanted.intersection(case.tags)]
    if case_ids:
        selected = [case for case in selected if _id_matches(case.id, case_ids)]
    return selected


def _id_matches(case_id: str, queries: list[str]) -> bool:
    return any(case_id == query or case_id.startswith(query + "/") for query in queries)


def _case_files(directory: Path) -> list[Path]:
    found: list[Path] = []
    for pattern in ("*.eval.yaml", "*.eval.yml", "*.eval.json"):
        found.extend(directory.rglob(pattern))
    files: list[Path] = []
    for path in found:
        relative = path.relative_to(directory)
        if ".results" in relative.parts:
            continue
        files.append(path)
    files.sort()
    return files


def _load_file(directory: Path, path: Path) -> list[EvalCase]:
    display = _display(directory, path)
    data = _read_data(path)
    if data is None:
        raise EvalLoadError(f"{display}: file is empty")
    file_tags: list[str] = []
    file_description = ""
    raw_cases: Any
    if isinstance(data, list):
        raw_cases = data
    elif isinstance(data, dict) and "cases" in data:
        raw_cases = data.get("cases")
        extra = set(data) - {"cases", "tags", "description"}
        if extra:
            names = ", ".join(sorted(extra))
            raise EvalLoadError(
                f"{display}: unexpected top-level fields next to cases: {names}"
            )
        file_tags = _string_list(data.get("tags"), display, "tags")
        description = data.get("description", "")
        if not isinstance(description, str):
            raise EvalLoadError(f"{display}: description must be a string")
        file_description = description
    elif isinstance(data, dict):
        raw_cases = [data]
    else:
        raise EvalLoadError(
            f"{display}: expected a case, a cases list, or a list of cases"
        )
    if not isinstance(raw_cases, list) or not raw_cases:
        raise EvalLoadError(f"{display}: cases must be a non-empty list")

    rel_stem = _rel_stem(directory, path)
    single = len(raw_cases) == 1
    loaded: list[EvalCase] = []
    for index, raw in enumerate(raw_cases):
        if not isinstance(raw, dict):
            raise EvalLoadError(f"{display}: each case must be a mapping")
        body = dict(raw)
        _normalize_script(body)
        short_id = body.get("id")
        body["id"] = _full_id(rel_stem, short_id, index, single)
        body["source"] = display
        body["tags"] = _merge_tags(
            file_tags, _string_list(body.get("tags", []), display, "tags")
        )
        if not body.get("description") and file_description:
            body["description"] = file_description
        try:
            loaded.append(EvalCase.model_validate(body))
        except ValidationError as exc:
            raise EvalLoadError(f"{display}: {exc}") from exc
    return loaded


def _full_id(rel_stem: str, short_id: Any, index: int, single: bool) -> str:
    if isinstance(short_id, str) and short_id.strip():
        return f"{rel_stem}/{short_id.strip()}"
    if single:
        return rel_stem
    return f"{rel_stem}/{index:04d}"


def _normalize_script(body: dict[str, Any]) -> None:
    script = body.get("script")
    if not isinstance(script, list):
        return
    for turn in script:
        if isinstance(turn, dict) and turn.get("tools") and "stop_reason" not in turn:
            turn["stop_reason"] = "tool_use"


def _merge_tags(file_tags: list[str], case_tags: list[str]) -> list[str]:
    merged: list[str] = []
    for tag in [*file_tags, *case_tags]:
        if tag not in merged:
            merged.append(tag)
    return merged


def _string_list(value: Any, display: str, field: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise EvalLoadError(f"{display}: {field} must be a list of strings")
    return list(value)


def _rel_stem(directory: Path, path: Path) -> str:
    relative = path.relative_to(directory)
    name = relative.name
    stem_name = name
    for suffix in _SUFFIXES:
        if name.endswith(suffix):
            stem_name = name[: -len(suffix)]
            break
    parent = relative.parent.as_posix()
    if parent == ".":
        return stem_name
    return f"{parent}/{stem_name}"


def _display(directory: Path, path: Path) -> str:
    return path.relative_to(directory).as_posix()


def _read_data(path: Path) -> Any:
    text = path.read_text(encoding="utf-8")
    try:
        if path.suffix == ".json":
            return json.loads(text)
        return yaml.safe_load(text)
    except (yaml.YAMLError, json.JSONDecodeError) as exc:
        raise EvalLoadError(f"{path.name}: {exc}") from exc
