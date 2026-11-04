"""The AI Safety Agent prompt is the reviewed draft, loaded from disk."""

from app.agents.orchestrator import WORKERS
from app.agents.prompts import get_prompt


def test_ai_safety_prompt_keeps_the_draft() -> None:
    prompt = get_prompt("ai_safety")
    assert "You are an expert AI Safety Agent." in prompt
    for phrase in (
        "Race, ethnicity, or nationality",
        "social security number",
        "Override system rules",
        "Conceal failures or modify evaluation results",
        "Correctness:",
        "Fabrication:",
        "Fluency:",
        "Coherence:",
        "Preference adherence",
        "state the uncertainty rather than inferring",
    ):
        assert phrase in prompt
    assert "3. Flag suspected or confirmed prompts" in prompt
    assert "4. Measure the following metrics" in prompt


def test_ai_safety_worker_has_no_demo_tools() -> None:
    assert WORKERS["ai_safety"]["prompt"] == "ai_safety"
    assert WORKERS["ai_safety"]["tools"] == []
