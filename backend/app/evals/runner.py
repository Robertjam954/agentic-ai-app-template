"""Execute eval cases against the agent loop."""

import asyncio
import json
import time
import traceback
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from app.agents.client import is_configured
from app.agents.service import execute_agent
from app.evals.gates import Assertion, grade
from app.evals.models import EvalCase
from app.evals.scripted import ScriptedClient

SKIP_NEEDS_LIVE = "no script; pass --live to call the model"
LIVE_KEY_MISSING = (
    "ANTHROPIC_API_KEY is not set. Add it to the repo .env, then rerun with --live."
)


@dataclass
class CaseResult:
    id: str
    status: Literal["passed", "failed", "skipped"]
    description: str
    mode: Literal["script", "live"]
    tags: list[str]
    reply: str | None = None
    stop_reason: str | None = None
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    assertions: list[Assertion] = field(default_factory=list)
    error: str | None = None
    skip_reason: str | None = None
    traceback: str | None = None
    duration_ms: float = 0
    report_path: str | None = None

    def as_dict(self) -> dict[str, Any]:
        """JSON shape for stdout. The on-disk report adds the traceback."""
        return {
            "id": self.id,
            "status": self.status,
            "description": self.description,
            "mode": self.mode,
            "tags": self.tags,
            "reply": self.reply,
            "stop_reason": self.stop_reason,
            "tool_calls": self.tool_calls,
            "assertions": [
                {"name": item.name, "ok": item.ok, "detail": item.detail}
                for item in self.assertions
            ],
            "error": self.error,
            "skip_reason": self.skip_reason,
            "duration_ms": round(self.duration_ms, 1),
            "report_path": self.report_path,
        }


async def run_cases(
    cases: list[EvalCase], *, live: bool, concurrency: int
) -> list[CaseResult]:
    """Run cases concurrently. Result order matches `cases`."""
    semaphore = asyncio.Semaphore(concurrency)

    async def _one(case: EvalCase) -> CaseResult:
        async with semaphore:
            return await run_case(case, live=live)

    return list(await asyncio.gather(*[_one(case) for case in cases]))


async def run_case(case: EvalCase, *, live: bool) -> CaseResult:
    started = time.perf_counter()
    result = CaseResult(
        id=case.id,
        status="failed",
        description=case.description,
        mode=case.mode,
        tags=list(case.tags),
    )
    if case.script is None and not live:
        result.status = "skipped"
        result.skip_reason = SKIP_NEEDS_LIVE
        result.duration_ms = _elapsed_ms(started)
        return result
    if case.script is None and not is_configured():
        result.error = LIVE_KEY_MISSING
        result.duration_ms = _elapsed_ms(started)
        return result

    client = None if case.script is None else ScriptedClient(case.script)
    try:
        run = await execute_agent(
            case.prompt,
            system_prompt=case.system_prompt,
            tool_names=case.tool_names,
            client=client,
        )
    except Exception as exc:  # noqa: BLE001 - a case failure should not abort the suite
        result.error = f"{type(exc).__name__}: {exc}"
        result.traceback = traceback.format_exc()
        result.duration_ms = _elapsed_ms(started)
        return result

    result.reply = run.reply
    result.stop_reason = run.stop_reason
    result.tool_calls = [
        {"name": call.name, "input": call.tool_input, "output": call.output}
        for call in run.tool_calls
    ]
    result.assertions = grade(run, case.expect)
    result.status = "passed" if all(item.ok for item in result.assertions) else "failed"
    result.duration_ms = _elapsed_ms(started)
    return result


def write_failure_reports(
    directory: Path, cases: list[EvalCase], results: list[CaseResult]
) -> None:
    """Write one JSON file per failed case under `<dir>/.results/<stamp>/`."""
    failed = [result for result in results if result.status == "failed"]
    if not failed:
        return
    by_id = {case.id: case for case in cases}
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    report_dir = directory / ".results" / stamp
    report_dir.mkdir(parents=True, exist_ok=True)
    for result in failed:
        case = by_id[result.id]
        path = report_dir / f"{result.id.replace('/', '__')}.json"
        result.report_path = str(path)
        payload = result.as_dict()
        payload["traceback"] = result.traceback
        payload["prompt"] = case.prompt
        payload["script"] = (
            None if case.script is None else [turn.model_dump() for turn in case.script]
        )
        payload["expect"] = case.expect.model_dump()
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        result.report_path = str(path)


def _elapsed_ms(started: float) -> float:
    return (time.perf_counter() - started) * 1000
