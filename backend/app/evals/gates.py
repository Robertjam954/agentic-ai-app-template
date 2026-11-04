"""Score an agent run against a case's expect block."""

import re
from dataclasses import dataclass

from app.agents.service import AgentRun, ToolCall
from app.evals.models import Expect, ToolExpect


@dataclass(frozen=True)
class Assertion:
    name: str
    ok: bool
    detail: str


def grade(run: AgentRun, expect: Expect) -> list[Assertion]:
    """Return one assertion per gate. The case passes when every one is ok."""
    succeeded = run.stop_reason != "max_steps"
    if succeeded == expect.succeeded:
        succeeded_detail = f"stop_reason={run.stop_reason}"
    else:
        succeeded_detail = (
            f"expected succeeded={expect.succeeded}, stop_reason={run.stop_reason}"
        )
    assertions = [
        Assertion(
            name="succeeded",
            ok=succeeded == expect.succeeded,
            detail=succeeded_detail,
        )
    ]
    assertions.extend(_called_tools(run, expect))
    assertions.extend(_not_called(run, expect))
    if expect.tool_order is not None:
        actual = [call.name for call in run.tool_calls]
        assertions.append(
            Assertion(
                name="tool_order",
                ok=actual == expect.tool_order,
                detail=f"actual={actual}",
            )
        )
    if expect.max_tool_calls is not None:
        count = len(run.tool_calls)
        assertions.append(
            Assertion(
                name="max_tool_calls",
                ok=count <= expect.max_tool_calls,
                detail=f"{count} tool call(s), max {expect.max_tool_calls}",
            )
        )
    if expect.reply_includes is not None:
        assertions.append(
            _regex_assertion("reply_includes", expect.reply_includes, run.reply)
        )
    return assertions


def _called_tools(run: AgentRun, expect: Expect) -> list[Assertion]:
    assertions: list[Assertion] = []
    for exp in expect.called_tools:
        if exp.output_includes is not None:
            try:
                output_re: re.Pattern[str] | None = re.compile(exp.output_includes)
            except re.error as exc:
                assertions.append(
                    Assertion(
                        name=f"called_tool:{exp.name}",
                        ok=False,
                        detail=f"invalid output_includes regex: {exc}",
                    )
                )
                continue
        else:
            output_re = None
        matches = [
            call for call in run.tool_calls if _call_matches(call, exp, output_re)
        ]
        if exp.count is None:
            ok = len(matches) >= 1
            expected = "at least 1"
        else:
            ok = len(matches) == exp.count
            expected = str(exp.count)
        same_name = [call for call in run.tool_calls if call.name == exp.name]
        detail = (
            f"matched {len(matches)} (expected {expected}); "
            f"calls named {exp.name}: {len(same_name)}"
        )
        if not ok and same_name:
            shown = [
                {"input": call.tool_input, "output": call.output} for call in same_name
            ]
            detail = f"{detail}; actual={shown}"
        assertions.append(
            Assertion(name=f"called_tool:{exp.name}", ok=ok, detail=detail)
        )
    return assertions


def _call_matches(
    call: ToolCall, exp: ToolExpect, output_re: re.Pattern[str] | None
) -> bool:
    if call.name != exp.name:
        return False
    if exp.input is not None:
        for key, value in exp.input.items():
            if call.tool_input.get(key) != value:
                return False
    if output_re is not None and output_re.search(call.output) is None:
        return False
    return True


def _not_called(run: AgentRun, expect: Expect) -> list[Assertion]:
    assertions: list[Assertion] = []
    for name in expect.not_called_tools:
        used = [call for call in run.tool_calls if call.name == name]
        assertions.append(
            Assertion(
                name=f"not_called_tool:{name}",
                ok=not used,
                detail="not called" if not used else f"called {len(used)} time(s)",
            )
        )
    return assertions


def _regex_assertion(name: str, pattern: str, text: str) -> Assertion:
    try:
        found = re.search(pattern, text) is not None
    except re.error as exc:
        return Assertion(name=name, ok=False, detail=f"invalid regex: {exc}")
    if found:
        return Assertion(name=name, ok=True, detail="matched")
    return Assertion(name=name, ok=False, detail=f"{text!r} did not match /{pattern}/")
