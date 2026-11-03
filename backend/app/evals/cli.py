"""Command line for the local eval runner.

uv run --directory backend agent-eval --list
uv run --directory backend agent-eval
uv run --directory backend agent-eval --tag smoke
uv run --directory backend agent-eval word_count
uv run --directory backend agent-eval --json
uv run --directory backend agent-eval --live --tag live
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

from app.evals.clinical import ClinicalNoteError, explain, outcome, structure_path
from app.evals.loader import load_cases, load_config, select_cases
from app.evals.models import EvalCase, EvalLoadError
from app.evals.runner import CaseResult, run_cases, write_failure_reports


def default_evals_dir() -> Path:
    """Repo-root `evals/`, independent of the process cwd."""
    return Path(__file__).resolve().parents[3] / "evals"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agent-eval",
        description=(
            "Run local agent eval cases. Scripted cases call the real tools "
            "and a fake model, so they need no API key. Cases with no script "
            "call Claude only when you pass --live."
        ),
    )
    parser.add_argument(
        "case_ids",
        nargs="*",
        help="Case id or path prefix to run (word_count, live). Default: all cases.",
    )
    parser.add_argument(
        "--dir",
        type=Path,
        default=None,
        help="Directory of *.eval.yaml cases (default: the evals/ directory at the repo root).",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List cases and exit.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print one JSON document on stdout.",
    )
    parser.add_argument(
        "--tag",
        dest="tags",
        action="append",
        default=[],
        help="Keep cases that have this tag. Repeat to match any of the tags.",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Also run cases that have no script (calls the model; needs ANTHROPIC_API_KEY).",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit 1 when a selected case is skipped.",
    )
    parser.add_argument(
        "--clinical-note",
        type=Path,
        default=None,
        help=(
            "Path to a saved note example. Writes the structured eval JSON "
            "(source transcript, clinical note, field scores) instead of "
            "running the scripted cases."
        ),
    )
    parser.add_argument(
        "--write-json",
        type=Path,
        default=None,
        help="With --clinical-note, also write the structured JSON to this path.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.clinical_note is not None:
        return _run_clinical_note(args.clinical_note, args.write_json, args.json)
    directory = args.dir if args.dir is not None else default_evals_dir()
    if not directory.is_dir():
        return _fail(
            args.json, f"eval directory not found: {directory}", "not_found", 2
        )
    try:
        config = load_config(directory)
        cases = load_cases(directory)
    except EvalLoadError as exc:
        return _fail(args.json, str(exc), "invalid", 1)

    selected = select_cases(cases, args.case_ids, args.tags)
    if args.list:
        _emit_list(selected, as_json=args.json)
        return 0
    if not selected:
        return _fail(args.json, "no eval cases matched", "not_found", 2)

    results = asyncio.run(
        run_cases(selected, live=args.live, concurrency=config.max_concurrency)
    )
    write_failure_reports(directory, selected, results)
    _emit_results(results, as_json=args.json)
    return _exit_code(results, strict=args.strict)


def cli() -> None:
    raise SystemExit(main())


def _run_clinical_note(path: Path, write_json: Path | None, as_json: bool) -> int:
    try:
        payload = structure_path(path)
    except ClinicalNoteError as exc:
        return _fail(as_json, str(exc), "invalid", 1)
    ok, _reasons = outcome(payload)
    if write_json is not None:
        write_json.parent.mkdir(parents=True, exist_ok=True)
        write_json.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    if as_json:
        _write_json(payload)
    else:
        for line in explain(payload):
            print(line)
        if write_json is not None:
            print(f"wrote {write_json}")
    return 0 if ok else 1


def _exit_code(results: list[CaseResult], *, strict: bool) -> int:
    failed = sum(result.status == "failed" for result in results)
    skipped = sum(result.status == "skipped" for result in results)
    passed = sum(result.status == "passed" for result in results)
    if failed or (strict and skipped):
        return 1
    if passed == 0:
        return 2
    return 0


def _fail(as_json: bool, message: str, code: str, exit_code: int) -> int:
    if as_json:
        _write_json({"error": {"code": code, "message": message}})
    else:
        print(message, file=sys.stderr)
    return exit_code


def _emit_list(cases: list[EvalCase], *, as_json: bool) -> None:
    if as_json:
        _write_json(
            {
                "cases": [
                    {
                        "id": case.id,
                        "mode": case.mode,
                        "tags": case.tags,
                        "description": case.description,
                        "source": case.source,
                    }
                    for case in cases
                ]
            }
        )
        return
    if not cases:
        print("no eval cases")
        return
    width = max(len(case.id) for case in cases)
    for case in cases:
        tags = ",".join(case.tags) if case.tags else "-"
        print(f"{case.id:<{width}}  {case.mode:<6}  {tags:<16}  {case.description}")


def _emit_results(results: list[CaseResult], *, as_json: bool) -> None:
    if as_json:
        _write_json(_summary(results))
        return
    for result in results:
        if result.status == "passed":
            print(f"PASS  {result.id}")
            continue
        if result.status == "skipped":
            print(f"SKIP  {result.id}  {result.skip_reason}")
            continue
        print(f"FAIL  {result.id}")
        if result.error:
            print(f"      {result.error}")
        for assertion in result.assertions:
            if not assertion.ok:
                print(f"      {assertion.name}: {assertion.detail}")
        if result.report_path:
            print(f"      report: {result.report_path}")
    counts = _summary(results)
    print(
        f"{counts['passed']} passed, {counts['failed']} failed, {counts['skipped']} skipped"
    )


def _summary(results: list[CaseResult]) -> dict[str, Any]:
    return {
        "passed": sum(result.status == "passed" for result in results),
        "failed": sum(result.status == "failed" for result in results),
        "skipped": sum(result.status == "skipped" for result in results),
        "results": [result.as_dict() for result in results],
    }


def _write_json(payload: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(payload, indent=2) + "\n")
