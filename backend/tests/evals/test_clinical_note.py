"""Clinical-note structuring. No Postgres; run with pytest --noconftest."""

import json
import math
from pathlib import Path

import pytest

from app.evals.cli import main
from app.evals.clinical import (
    merge_field_results,
    normalize_geval_score,
    outcome,
    structure_example,
)
from app.evals.em import (
    HPI_FIELDS,
    complaint_schema,
    exam_level_1995,
    history_fields,
    history_level,
    hpi_schema,
    validate_history,
)

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


def _history(**overrides: object) -> dict[str, object]:
    history: dict[str, object] = {
        "chief_complaint": {"claims": []},
        "history_of_present_illness": {name: {"claims": []} for name in HPI_FIELDS},
        "review_of_systems": {},
        "pfsh": {},
    }
    history.update(overrides)
    return history


def test_hpi_is_separate_from_the_chief_complaint() -> None:
    assert tuple(complaint_schema()["properties"]) == ("statement",)
    assert tuple(hpi_schema()["properties"]) == HPI_FIELDS
    illness = {name: {"claims": []} for name in HPI_FIELDS}
    illness["duration"] = {"claims": [{"text": "It has lasted two weeks."}]}
    illness["timing"] = {"claims": [{"text": "It started daily."}]}
    illness["severity"] = {"claims": [{"text": "The pain is mild."}]}
    illness["modifying_factors"] = {"claims": [{"text": "Rest gives relief."}]}
    cleaned = validate_history(
        _history(
            chief_complaint={"claims": [{"text": "  Follow-up for bloodwork.  "}]},
            history_of_present_illness=illness,
        )
    )
    assert cleaned["chief_complaint"]["claims"][0]["text"] == "Follow-up for bloodwork."
    bad = {name: {"claims": []} for name in HPI_FIELDS}
    bad["duration"] = {"claims": [{"text": "The pain is sharp."}]}
    with pytest.raises(ValueError, match="Duration must be a length of time"):
        validate_history(_history(history_of_present_illness=bad))


def test_review_of_systems_can_document_several_systems() -> None:
    fields = history_fields("Denies fever, cough, and chest pain.")
    assert fields == [
        "history.ros.constitutional",
        "history.ros.cardiovascular",
        "history.ros.respiratory",
    ]
    assert history_fields("She has a cough.") == [
        "history.hpi.associated_signs_and_symptoms"
    ]


def test_history_and_exam_levels_follow_the_guideline_tables() -> None:
    assert (
        history_level(cc=True, hpi=2, ros=0, pfsh=0, established=True)
        == "problem_focused"
    )
    assert (
        history_level(cc=True, hpi=2, ros=1, pfsh=0, established=True)
        == "expanded_problem_focused"
    )
    assert history_level(cc=True, hpi=4, ros=3, pfsh=1, established=True) == "detailed"
    assert (
        history_level(cc=True, hpi=4, ros=10, pfsh=2, established=True)
        == "comprehensive"
    )
    # Established complete PFSH is 2 of 3. A new visit still needs 3 of 3.
    assert (
        history_level(cc=True, hpi=4, ros=10, pfsh=2, established=False) == "detailed"
    )
    assert history_level(cc=False, hpi=4, ros=10, pfsh=3, established=False) == "none"
    assert history_level(cc=True, hpi=0, ros=10, pfsh=3, established=True) == "none"
    assert exam_level_1995(0) == "none"
    assert exam_level_1995(1) == "problem_focused"
    assert exam_level_1995(5) == "expanded_problem_focused"
    assert exam_level_1995(7) == "detailed"
    assert exam_level_1995(8) == "comprehensive"


def test_structures_supported_note() -> None:
    payload = structure_example(_example(_NOTE, _TRANSCRIPT))
    assert payload["document_id"] == "tiny"
    assert payload["source_document"]["text"] == _TRANSCRIPT
    history = payload["clinical_note"]["history"]
    statement = history["chief_complaint"]["claims"]
    assert statement[0]["text"].startswith("Follow-up")
    assert history["pfsh"]["social_history"]["claims"]
    data = payload["clinical_note"]["medical_decision_making"]["data_reviewed"][
        "claims"
    ]
    assert data[0]["text"] == "Potassium: 5.6."
    problems = payload["clinical_note"]["medical_decision_making"][
        "diagnoses_or_management_options"
    ]
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
    results = {item["field"]: item for item in payload["evaluation"]["field_results"]}
    # "patch" is not in the transcript. It should not be scored as supported.
    scored = [
        item
        for item in results.values()
        if item["claim_count"] and item["field"].startswith("history.")
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


def test_merge_keeps_claims_and_uses_model_scores() -> None:
    payload = structure_example(_example(_NOTE, _TRANSCRIPT))
    field = payload["evaluation"]["field_results"][0]["field"]
    merged = merge_field_results(
        payload,
        [
            {
                "field": field,
                "correctness": "unsupported",
                "fabrication": True,
                "fluency": "pass",
                "coherence": "pass",
                "preference_adherence": "not_applicable",
                "uncertainty": "not in the source",
            }
        ],
    )
    updated = merged["evaluation"]["field_results"][0]
    assert updated["correctness"] == "unsupported"
    assert updated["fabrication"] is True
    assert (
        updated["claim_count"]
        == payload["evaluation"]["field_results"][0]["claim_count"]
    )
    assert merged["evaluation"]["scorer"] == "openai"


def test_geval_score_stays_on_a_ten_point_scale() -> None:
    logprobs = [
        {
            "token": "8",
            "logprob": -0.1,
            "top_logprobs": [
                {"token": "8", "logprob": math.log(0.7)},
                {"token": "7", "logprob": math.log(0.2)},
                {"token": "9", "logprob": math.log(0.1)},
            ],
        }
    ]
    # 8*0.7 + 7*0.2 + 9*0.1 = 7.9
    assert normalize_geval_score(8, logprobs) == 7.9
    assert normalize_geval_score(8, None) == 8.0


def test_metrics_are_counts_out_of_transcript_capacity() -> None:
    payload = structure_example(_example(_NOTE, _TRANSCRIPT))
    capacity = payload["evaluation"]["capacity"]
    assert "chief_complaint" in capacity["history"]["fields"]
    assert "pfsh.social_history" in capacity["history"]["fields"]
    assert "data_reviewed" in capacity["medical_decision_making"]["fields"]
    assert capacity["max_fields"] == (
        capacity["history"]["count"]
        + capacity["exam"]["count"]
        + capacity["medical_decision_making"]["count"]
    )
    metrics = {item["name"]: item for item in payload["evaluation"]["metrics"]}
    assert metrics["correctness"]["max_fields"] == capacity["max_fields"]
    assert metrics["correctness"]["capacity"]["history"] == capacity["history"]["count"]
    em = payload["evaluation"]["em"]
    assert em["history"]["chief_complaint"] is True
    assert em["exam"]["level_1997"] is None
    assert em["medical_decision_making"]["risk"] is None
    assert em["medical_decision_making"]["type"] is None
    assert metrics["fabrication"]["direction"] == "lower"
    assert metrics["fabrication"]["score"] == 0
    assert metrics["fabrication"]["success"] is True
    ok, reasons = outcome(payload)
    assert ok, reasons


def test_metric_rates_use_a_ten_point_threshold() -> None:
    payload = structure_example(_example(_NOTE, _TRANSCRIPT))
    payload["evaluation"]["metrics"] = [
        {"name": "correctness", "score": 7.9, "threshold": 5},
        {"name": "fluency", "score": 4.5, "threshold": 5},
    ]
    ok, reasons = outcome(payload)
    assert not ok
    assert reasons == ["fluency: 4.50 is below 5.00"]


def test_fabrication_rate_is_lower_is_better() -> None:
    payload = structure_example(_example(_NOTE, _TRANSCRIPT))
    payload["evaluation"]["metrics"] = [
        {
            "name": "fabrication",
            "score": 6.2,
            "threshold": 5,
            "direction": "lower",
        }
    ]
    ok, reasons = outcome(payload)
    assert not ok
    assert reasons == ["fabrication: 6.20 is above 5.00"]

    payload["evaluation"]["metrics"][0]["score"] = 5.0
    ok, reasons = outcome(payload)
    assert ok, reasons


def test_cli_writes_json_and_exits(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "note.json"
    path.write_text(json.dumps(_example(_NOTE, _TRANSCRIPT)), encoding="utf-8")
    out = tmp_path / "structured.json"
    code = main(["--clinical-note", str(path), "--write-json", str(out), "--json"])
    assert code == 0
    written = json.loads(out.read_text(encoding="utf-8"))
    assert written["document_id"] == "tiny"
    printed = json.loads(capsys.readouterr().out)
    assert printed["document_id"] == "tiny"
