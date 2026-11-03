"""Clinical-note structuring. No Postgres; run with pytest --noconftest."""

import json
from pathlib import Path

import pytest

from app.evals.cli import main
from app.evals.clinical import outcome, structure_example

_RULE = (
    "Format subjective histories as bullet points, with each sentence "
    "in its own bullet point."
)


def _example(note: str, transcript: str, prior: str = "") -> dict[str, object]:
    context: list[dict[str, str]] = []
    if prior:
        context.append({"noteContent": prior})
    return {
        "example_id": "tiny",
        "inputs": {
            "transcript_prompt_at_generation": transcript,
            "gathered_patient_context": context,
        },
        "outputs": {"original_base_generation_markdown": note},
        "auxiliary_evidence": {
            "current_relevant_rule_rows": [{"is_active": True, "content": _RULE}]
        },
    }


_NOTE = """## Subjective

- Follow-up for bloodwork.
- Drinks two coffees.

## Objective

- Potassium: 5.6.

## Assessment & Plan

**Hyperkalemia**: Potassium is 5.6.

- Repeat the potassium test.
"""

_TRANSCRIPT = (
    "clinician_0: This is a follow-up for your bloodwork. "
    "Potassium is 5.6. I would like to repeat the potassium test. "
    "patient_1: I drink two coffees."
)


def test_structures_supported_note() -> None:
    payload = structure_example(_example(_NOTE, _TRANSCRIPT))
    assert payload["document_id"] == "tiny"
    assert payload["source_document"]["text"] == _TRANSCRIPT
    subjective = payload["clinical_note"]["subjective"]
    assert subjective["chief_complaint"]["claims"][0]["text"].startswith("Follow-up")
    assert subjective["relevant_history"]["social_history"]["substance_use"]["claims"]
    assert payload["clinical_note"]["objective"]["completed_investigations"] == [
        "Potassium: 5.6."
    ]
    problems = payload["clinical_note"]["assessment_and_plan"]["problems"]
    assert problems[0]["problem"] == "Hyperkalemia"
    assert problems[0]["plan"] == ["Repeat the potassium test."]
    ok, reasons = outcome(payload)
    assert ok, reasons


def test_missing_number_is_fabrication() -> None:
    note = _NOTE.replace("Potassium: 5.6.", "Potassium: 9.9.")
    payload = structure_example(_example(note, _TRANSCRIPT))
    ok, reasons = outcome(payload)
    assert not ok
    assert any("fabrication" in reason for reason in reasons)


def test_prior_context_is_uncertain_not_fabricated() -> None:
    note = """## Subjective

- Uses a patch.

## Objective

## Assessment & Plan
"""
    transcript = "clinician_0: How has the HRT been working?"
    payload = structure_example(
        _example(note, transcript, prior="She uses a 37.5 mcg patch.")
    )
    results = {
        item["field"]: item for item in payload["evaluation"]["field_results"]
    }
    # "patch" is not in the transcript. It should not be scored as supported.
    scored = [
        item
        for item in results.values()
        if item["claim_count"] and item["field"].startswith("subjective.")
    ]
    assert scored
    assert all(item["fabrication"] is False for item in scored)
    assert any(item["correctness"] == "uncertain" for item in scored)


def test_multi_sentence_bullet_fails_preference() -> None:
    note = """## Subjective

- Feels well today. Drinks coffee.

## Objective

## Assessment & Plan
"""
    transcript = "patient_1: I feel well today and I drink coffee."
    payload = structure_example(_example(note, transcript))
    ok, reasons = outcome(payload)
    assert not ok
    assert any("preference" in reason for reason in reasons)


def test_cli_writes_json_and_exits(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = tmp_path / "note.json"
    path.write_text(json.dumps(_example(_NOTE, _TRANSCRIPT)), encoding="utf-8")
    out = tmp_path / "structured.json"
    code = main(["--clinical-note", str(path), "--write-json", str(out), "--json"])
    assert code == 0
    written = json.loads(out.read_text(encoding="utf-8"))
    assert written["document_id"] == "tiny"
    printed = json.loads(capsys.readouterr().out)
    assert printed["document_id"] == "tiny"
