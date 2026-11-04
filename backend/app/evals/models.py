"""Eval case schema.

Cases are YAML or JSON files under the repo `evals/` directory. A file is
either one case or a `cases:` list. See `evals/README.md`.
"""

from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class EvalLoadError(Exception):
    """A case file or the eval config could not be loaded."""


class ScriptTool(BaseModel):
    """One tool call a scripted model turn will request."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    input: dict[str, Any] = Field(default_factory=dict)


class ScriptTurn(BaseModel):
    """One mocked model response, in order."""

    model_config = ConfigDict(extra="forbid")

    stop_reason: Literal["tool_use", "end_turn"] = "end_turn"
    text: str = ""
    tools: list[ScriptTool] = Field(default_factory=list)


class ToolExpect(BaseModel):
    """A tool call the run must contain.

    `input` matches by equality on the keys you set (other keys are ignored).
    `output_includes` is a regular expression searched against the tool output.
    `count` defaults to "at least one".
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    input: dict[str, Any] | None = None
    output_includes: str | None = None
    count: int | None = Field(default=None, ge=0)


class Expect(BaseModel):
    """Gates for one case. Decisions and shape, not a full prose snapshot."""

    model_config = ConfigDict(extra="forbid")

    succeeded: bool = True
    called_tools: list[ToolExpect] = Field(default_factory=list)
    not_called_tools: list[str] = Field(default_factory=list)
    tool_order: list[str] | None = None
    max_tool_calls: int | None = Field(default=None, ge=0)
    reply_includes: str | None = None

    @field_validator("called_tools", mode="before")
    @classmethod
    def _coerce_called_tools(cls, value: Any) -> Any:
        if not isinstance(value, list):
            return value
        coerced: list[Any] = []
        for item in value:
            if isinstance(item, str):
                coerced.append({"name": item})
            else:
                coerced.append(item)
        return coerced


class EvalCase(BaseModel):
    """One eval case, after the file name has been folded into `id`."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    description: str = ""
    tags: list[str] = Field(default_factory=list)
    prompt: str
    system_prompt: str | None = None
    tool_names: list[str] | None = None
    script: list[ScriptTurn] | None = None
    expect: Expect = Field(default_factory=Expect)
    source: str

    @property
    def mode(self) -> Literal["script", "live"]:
        return "live" if self.script is None else "script"

    @field_validator("prompt")
    @classmethod
    def _prompt_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("prompt must not be empty")
        return value

    @model_validator(mode="after")
    def _check_script(self) -> Self:
        if self.script is not None and len(self.script) == 0:
            raise ValueError(
                "script must contain at least one turn; omit script for a live case"
            )
        for index, turn in enumerate(self.script or []):
            if turn.stop_reason == "tool_use" and not turn.tools:
                raise ValueError(f"script turn {index} is tool_use but lists no tools")
            if turn.tools and turn.stop_reason != "tool_use":
                raise ValueError(
                    f"script turn {index} lists tools; set stop_reason: tool_use"
                )
        return self


class EvalConfig(BaseModel):
    """Optional `evals/evals.config.yaml`."""

    model_config = ConfigDict(extra="forbid")

    max_concurrency: int = Field(default=4, ge=1)
