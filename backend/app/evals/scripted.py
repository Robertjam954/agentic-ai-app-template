"""A model client that replays scripted turns. No network."""

from types import SimpleNamespace
from typing import Any

from app.evals.models import ScriptTurn


class ScriptedMessages:
    """`client.messages.create` compatible with the agent loop."""

    def __init__(self, turns: list[ScriptTurn]) -> None:
        self._turns = turns
        self._index = 0

    async def create(self, **_kwargs: Any) -> Any:
        if self._index >= len(self._turns):
            raise RuntimeError(
                "scripted model ran out of turns; add a final end_turn "
                "or the case is calling the model more times than the script"
            )
        turn = self._turns[self._index]
        self._index += 1
        blocks: list[Any] = []
        if turn.text:
            blocks.append(SimpleNamespace(type="text", text=turn.text))
        for tool_index, tool in enumerate(turn.tools):
            blocks.append(
                SimpleNamespace(
                    type="tool_use",
                    name=tool.name,
                    input=dict(tool.input),
                    id=f"toolu_{self._index}_{tool_index}",
                )
            )
        if not blocks:
            blocks.append(SimpleNamespace(type="text", text=""))
        return SimpleNamespace(stop_reason=turn.stop_reason, content=blocks)


class ScriptedClient:
    def __init__(self, turns: list[ScriptTurn]) -> None:
        self.messages = ScriptedMessages(turns)
