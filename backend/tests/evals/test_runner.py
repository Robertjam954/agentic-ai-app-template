"""Local eval runner. Does not need Postgres; run with pytest --noconftest."""

import asyncio
import json
from pathlib import Path

import pytest

from app.agents.service import MAX_STEPS, AgentRun, ToolCall, run_agent
from app.evals.cli import main
from app.evals.gates import grade
from app.evals.loader import load_cases, select_cases
from app.evals.models import EvalCase, EvalLoadError, Expect, ScriptTool, ScriptTurn
from app.evals.runner import run_case, run_cases
from app.evals.scripted import ScriptedClient

REPO = Path(__file__).resolve().parents[3]
EVALS = REPO / "evals"


def test_shipped_cases_list_and_pass() -> None:
    cases = load_cases(EVALS)
    ids = [case.id for case in cases]
    assert ids == ["current_time", "live/word_count", "word_count"]

    smoke = select_cases(cases, [], ["smoke"])
    assert [case.id for case in smoke] == ["current_time", "word_count"]
    assert [case.id for case in select_cases(cases, ["live"], [])] == [
        "live/word_count"
    ]
    assert select_cases(cases, ["word"], []) == []

    results = asyncio.run(run_cases(cases, live=False, concurrency=2))
    by_id = {result.id: result for result in results}
    assert by_id["word_count"].status == "passed"
    assert by_id["word_count"].tool_calls == [
        {"name": "word_count", "input": {"text": "hello world"}, "output": "2"}
    ]
    assert by_id["current_time"].status == "passed"
    output = by_id["current_time"].tool_calls[0]["output"]
    assert isinstance(output, str)
    assert "T" in output
    assert by_id["live/word_count"].status == "skipped"


def test_scripted_run_does_not_build_provider_client(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    def boom() -> None:
        raise AssertionError("provider client should not be built")

    monkeypatch.setattr("app.agents.service.get_client", boom)
    cases = select_cases(load_cases(EVALS), ["word_count"], [])
    results = asyncio.run(run_cases(cases, live=False, concurrency=1))
    assert results[0].status == "passed"


def test_run_agent_returns_text() -> None:
    client = ScriptedClient([ScriptTurn(text="hi there")])
    reply = asyncio.run(run_agent("hello", client=client))
    assert reply == "hi there"


def test_script_that_runs_out_of_turns_fails_the_case() -> None:
    case = EvalCase(
        id="short",
        prompt="count",
        source="short.eval.yaml",
        script=[
            ScriptTurn(
                stop_reason="tool_use",
                tools=[ScriptTool(name="word_count", input={"text": "a"})],
            )
        ],
    )
    result = asyncio.run(run_case(case, live=False))
    assert result.status == "failed"
    assert result.error is not None
    assert "ran out of turns" in result.error


def test_step_cap_fails_succeeded_gate() -> None:
    turns = [
        ScriptTurn(
            stop_reason="tool_use",
            tools=[ScriptTool(name="word_count", input={"text": "a"})],
        )
        for _ in range(MAX_STEPS)
    ]
    case = EvalCase(id="capped", prompt="loop", source="capped.eval.yaml", script=turns)
    result = asyncio.run(run_case(case, live=False))
    assert result.status == "failed"
    assert result.stop_reason == "max_steps"
    assert any(item.name == "succeeded" and not item.ok for item in result.assertions)


def test_grade_tool_order_and_regex() -> None:
    run = AgentRun(
        reply="nope",
        stop_reason="end_turn",
        tool_calls=(
            ToolCall(name="word_count", tool_input={"text": "ab"}, output="1"),
        ),
    )
    expect = Expect.model_validate(
        {
            "called_tools": [{"name": "current_time"}],
            "tool_order": ["current_time"],
            "reply_includes": "(",
        }
    )
    assertions = {item.name: item for item in grade(run, expect)}
    assert assertions["called_tool:current_time"].ok is False
    assert assertions["tool_order"].ok is False
    assert assertions["reply_includes"].ok is False
    assert "invalid regex" in assertions["reply_includes"].detail


def test_case_ids_and_json(tmp_path: Path) -> None:
    (tmp_path / "solo.eval.json").write_text(
        json.dumps(
            {
                "description": "json case",
                "tags": ["json"],
                "prompt": "hi",
                "script": [{"text": "ok"}],
                "expect": {"reply_includes": "ok"},
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "group.eval.yaml").write_text(
        "tags: [group]\n"
        "cases:\n"
        "  - id: named\n"
        "    prompt: one\n"
        "    script:\n"
        "      - text: one\n"
        "  - prompt: two\n"
        "    script:\n"
        "      - text: two\n",
        encoding="utf-8",
    )
    cases = load_cases(tmp_path)
    assert [case.id for case in cases] == ["group/0001", "group/named", "solo"]
    assert cases[0].tags == ["group"]
    results = asyncio.run(run_cases(cases, live=False, concurrency=3))
    assert all(result.status == "passed" for result in results)


def test_duplicate_id_and_bad_field(tmp_path: Path) -> None:
    body = json.dumps({"prompt": "hi", "script": [{"text": "hi"}]})
    (tmp_path / "same.eval.yaml").write_text(
        "prompt: hi\nscript:\n  - text: hi\n", encoding="utf-8"
    )
    (tmp_path / "same.eval.json").write_text(body, encoding="utf-8")
    with pytest.raises(EvalLoadError, match="duplicate eval id"):
        load_cases(tmp_path)

    broken = tmp_path / "only"
    broken.mkdir()
    (broken / "bad.eval.yaml").write_text(
        "prompt: hi\nnot_a_field: 1\n", encoding="utf-8"
    )
    with pytest.raises(EvalLoadError, match="not_a_field"):
        load_cases(broken)


def test_cli_shipped_suite_and_filters(capsys) -> None:  # type: ignore[no-untyped-def]
    assert main(["--tag", "smoke"]) == 0
    out = capsys.readouterr().out
    assert "PASS  word_count" in out
    assert "PASS  current_time" in out
    assert "SKIP" not in out
    assert "2 passed, 0 failed, 0 skipped" in out

    assert main(["--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["passed"] == 2
    assert payload["skipped"] == 1
    assert payload["failed"] == 0

    assert main(["missing-case"]) == 2
    assert "no eval cases matched" in capsys.readouterr().err

    assert main(["--strict", "live/word_count"]) == 1
    assert main(["--live", "live/word_count"]) == 1
    live_out = capsys.readouterr().out
    assert "ANTHROPIC_API_KEY" in live_out


def test_cli_failure_report(tmp_path: Path, capsys) -> None:  # type: ignore[no-untyped-def]
    (tmp_path / "bad.eval.yaml").write_text(
        "description: expects the wrong tool\n"
        "prompt: hello\n"
        "script:\n"
        "  - text: hello\n"
        "expect:\n"
        "  called_tools: [word_count]\n",
        encoding="utf-8",
    )
    code = main(["--dir", str(tmp_path), "--json"])
    assert code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["failed"] == 1
    report = Path(payload["results"][0]["report_path"])
    assert report.is_file()
    assert tmp_path in report.parents
    saved = json.loads(report.read_text(encoding="utf-8"))
    assert saved["prompt"] == "hello"
    called = next(
        item for item in saved["assertions"] if item["name"] == "called_tool:word_count"
    )
    assert called["ok"] is False
