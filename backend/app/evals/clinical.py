"""Turn one saved clinical-note example into the eval JSON shape.

`source_document.text` is the visit transcript. `clinical_note` is the saved
generation, split into the subjective, objective, and assessment fields.
`evaluation.field_results` scores each field against that transcript.

Facts that appear only in gathered prior context are uncertain, not treated as
supported by today's visit. A number or distinctive fact in neither place is a
fabrication.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z])")
_NUMBER = re.compile(r"\d+(?:\.\d+)?")
_YEAR = re.compile(r"^(19|20)\d{2}$")
_RESIDUE = re.compile(
    r"\[[^\]]+\]|only include if|do not infer|do not include",
    re.IGNORECASE,
)
_HEADER = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)
_PROBLEM = re.compile(r"^\*\*(.+?)\*\*:\s*(.*)$")
_SPEAKER = re.compile(r"\b(?:clinician|patient)_\d+:", re.IGNORECASE)

_NUMBER_WORDS = {
    "0": "zero",
    "1": "one",
    "2": "two",
    "3": "three",
    "4": "four",
    "5": "five",
    "6": "six",
    "7": "seven",
    "8": "eight",
    "9": "nine",
    "10": "ten",
}

_STOP = {
    "about",
    "after",
    "again",
    "also",
    "and",
    "another",
    "any",
    "are",
    "because",
    "been",
    "before",
    "being",
    "but",
    "during",
    "for",
    "from",
    "had",
    "has",
    "have",
    "her",
    "here",
    "his",
    "into",
    "its",
    "just",
    "more",
    "most",
    "not",
    "only",
    "other",
    "our",
    "over",
    "she",
    "some",
    "such",
    "than",
    "that",
    "the",
    "their",
    "them",
    "then",
    "there",
    "they",
    "this",
    "was",
    "were",
    "when",
    "which",
    "while",
    "with",
    "within",
    "without",
    "you",
    "your",
}

_SHORT_OK = {"cbc", "egfr", "hrt", "wbc"}

# A note word counts as present when the transcript uses one of these phrases.
_SYNONYMS: dict[str, tuple[str, ...]] = {
    "abnormal": ("abnormal",),
    "additional": ("longer", "while"),
    "avoid": ("away", "stay away"),
    "avocados": ("avocado", "avocados"),
    "bananas": ("banana", "bananas"),
    "cbc": ("blood", "white"),
    "childbirth": ("daughter",),
    "clarify": ("ask", "finding out"),
    "clinically": ("healthy", "sick"),
    "contact": ("contact",),
    "continue": ("longer",),
    "decreased": ("dropped", "drop"),
    "dehydration": ("water", "dehydrated"),
    "denies": ("not sick", "healthy"),
    "elevated": ("raised", "high"),
    "espresso": ("espresso",),
    "fatigue": ("tired",),
    "fluid": ("water", "drink"),
    "hematology": ("blood",),
    "hydration": ("water", "drink"),
    "hyperkalemia": ("potassium",),
    "illness": ("bug", "infection", "sick"),
    "inherited": ("inherited",),
    "intake": ("drink", "drinking"),
    "intermittent": ("sometimes",),
    "leukocytosis": ("white", "blood"),
    "liters": ("liter", "litre"),
    "menopausal": ("hrt",),
    "mild": ("bit",),
    "mother": ("mom", "mum"),
    "children": ("kids", "kid"),
    "child": ("kid", "daughter", "son"),
    "returned": ("come back", "came back"),
    "respiratory": ("cough",),
    "rare": ("hardly",),
    "occasional": ("sometimes",),
    "palpitations": ("palpitation", "palpitations"),
    "pods": ("pod", "pods"),
    "reassuring": ("okay", "good"),
    "relocation": ("moved", "moving"),
    "renal": ("kidney",),
    "repeat": ("repeat",),
    "requisition": ("requisition", "email"),
    "residual": ("sometimes",),
    "stable": ("stable",),
    "transdermal": ("patch",),
    "ultrasound": ("ultrasound",),
    "vasomotor": ("hot flash", "hot flashes"),
    "viral": ("virus", "bug"),
    "weekend": ("weekend", "saturday"),
    "well": ("well", "good", "healthy"),
}

_HPI_FIELDS = (
    "onset",
    "duration",
    "frequency",
    "severity",
    "location",
    "quality",
    "progression",
    "context",
    "relieving_factors",
    "exacerbating_factors",
    "self_treatment",
    "impact_on_daily_activities",
    "associated_symptoms",
)

_SUBJECTIVE_FIELDS = (
    "chief_complaint",
    *_HPI_FIELDS,
    "past_medical_history",
    "lifestyle",
    "social_determinants",
    "occupational_exposures",
    "substance_use",
    "family_history",
)

_OBJECTIVE_FIELDS = (
    "vital_signs",
    "physical_examination",
    "mental_status_examination",
    "completed_investigations",
    "other_objective_findings",
)


class ClinicalNoteError(Exception):
    """The example file is missing the transcript or the generated note."""


@dataclass
class _Placed:
    field: str
    text: str
    preference_ok: bool


@dataclass
class _Support:
    kind: str
    fabrication: bool
    uncertainty: str | None


def structure_path(path: Path) -> dict[str, Any]:
    """Read an example file and return the eval JSON object."""
    if not path.is_file():
        raise ClinicalNoteError(f"clinical note not found: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ClinicalNoteError(f"{path}: invalid JSON ({exc})") from exc
    if not isinstance(data, dict):
        raise ClinicalNoteError(f"{path}: expected a JSON object")
    return structure_example(data)


def structure_example(data: dict[str, Any]) -> dict[str, Any]:
    """Build source text, the clinical note, and per-field scores."""
    transcript = _transcript(data)
    prior = _prior_context(data)
    note = _generated_note(data)
    if not transcript.strip():
        raise ClinicalNoteError("example has no visit transcript")
    if not note.strip():
        raise ClinicalNoteError("example has no generated clinical note")

    preference_rule = _preference_rule(data)
    placed = _place_note(note, preference_rule=preference_rule)
    transcript_norm = _normalize(transcript)
    prior_norm = _normalize(prior)
    sections_in_order = _sections_in_order(note)

    clinical = _empty_note()
    clinical["assessment_and_plan"]["problems"] = _problems(
        _split_sections(note).get("assessment", "")
    )
    buckets: dict[str, list[_Placed]] = {}
    for item in placed:
        buckets.setdefault(item.field, []).append(item)
        if not item.field.startswith("assessment_and_plan.problems:"):
            _store_claim(clinical, item)

    field_results = [
        _score_field(
            field,
            buckets.get(field, []),
            transcript_norm=transcript_norm,
            prior_norm=prior_norm,
            transcript_raw=transcript,
            prior_raw=prior,
            preference_rule=preference_rule,
            sections_in_order=sections_in_order,
        )
        for field in _field_names(clinical)
    ]
    example_id = data.get("example_id")
    document_id = example_id if isinstance(example_id, str) and example_id else None
    return {
        "document_id": document_id,
        "source_document": {"id": document_id, "text": transcript},
        "clinical_note": clinical,
        "evaluation": {"field_results": field_results},
    }


def outcome(payload: dict[str, Any]) -> tuple[bool, list[str]]:
    """Pass when no scored field is fabricated, ungrounded, or off-preference."""
    reasons: list[str] = []
    results = payload.get("evaluation", {}).get("field_results", [])
    if not isinstance(results, list):
        return False, ["evaluation.field_results is missing"]
    for item in results:
        if not isinstance(item, dict) or item.get("claim_count", 0) == 0:
            continue
        field = str(item.get("field", ""))
        if item.get("fabrication") is True:
            reasons.append(f"{field}: fabrication")
        elif item.get("correctness") == "unsupported":
            reasons.append(f"{field}: correctness unsupported")
        if item.get("fluency") == "fail":
            reasons.append(f"{field}: fluency")
        if item.get("coherence") == "fail":
            reasons.append(f"{field}: coherence")
        if item.get("preference_adherence") == "fail":
            reasons.append(f"{field}: preference adherence")
    return (not reasons, reasons)


def explain(payload: dict[str, Any]) -> list[str]:
    """Short text report. Empty fields are counted, not listed."""
    document_id = payload.get("document_id") or "clinical-note"
    results = payload["evaluation"]["field_results"]
    ok, reasons = outcome(payload)
    lines = [f"{'PASS' if ok else 'FAIL'}  {document_id}"]
    shown = 0
    empty = 0
    for item in results:
        if item["claim_count"] == 0:
            empty += 1
            continue
        shown += 1
        uncertainty = item["uncertainty"]
        extra = f"  uncertainty: {uncertainty}" if uncertainty else ""
        lines.append(
            f"  {item['field']}: correctness={item['correctness']}"
            f" fabrication={str(item['fabrication']).lower()}"
            f" fluency={item['fluency']}"
            f" coherence={item['coherence']}"
            f" preference={item['preference_adherence']}"
            f" claims={item['claim_count']}{extra}"
        )
    lines.append(f"{shown} fields scored, {empty} empty")
    lines.extend(f"  fail: {reason}" for reason in reasons)
    return lines


def _transcript(data: dict[str, Any]) -> str:
    inputs = _dict(data.get("inputs"))
    text = inputs.get("transcript_prompt_at_generation")
    if isinstance(text, str) and text.strip():
        return text
    saved = _dict(inputs.get("saved_base_input"))
    saved_text = saved.get("transcriptPrompt")
    return saved_text if isinstance(saved_text, str) else ""


def _prior_context(data: dict[str, Any]) -> str:
    inputs = _dict(data.get("inputs"))
    chunks: list[str] = []
    for item in _list(inputs.get("gathered_patient_context")):
        note = _dict(item).get("noteContent")
        if isinstance(note, str) and note.strip():
            chunks.append(note)
    return "\n".join(chunks)


def _generated_note(data: dict[str, Any]) -> str:
    outputs = _dict(data.get("outputs"))
    markdown = outputs.get("original_base_generation_markdown")
    if isinstance(markdown, str) and markdown.strip():
        return markdown
    html = outputs.get("current_note_html_at_export")
    if isinstance(html, str) and html.strip():
        return _html_to_text(html)
    return ""


def _preference_rule(data: dict[str, Any]) -> str | None:
    evidence = _dict(data.get("auxiliary_evidence"))
    for row in _list(evidence.get("current_relevant_rule_rows")):
        item = _dict(row)
        if item.get("is_active") is not True:
            continue
        content = item.get("content")
        if not isinstance(content, str):
            continue
        lowered = content.lower()
        if "bullet" in lowered and "sentence" in lowered:
            return content.strip()
    return None


def _place_note(note: str, *, preference_rule: str | None) -> list[_Placed]:
    sections = _split_sections(note)
    placed: list[_Placed] = []
    for bullet in _bullets(sections.get("subjective", "")):
        sentences = _sentences(bullet)
        preference_ok = preference_rule is None or len(sentences) == 1
        for sentence in sentences:
            placed.append(
                _Placed(
                    field=_classify_subjective(sentence),
                    text=sentence,
                    preference_ok=preference_ok,
                )
            )
    for bullet in _bullets(sections.get("objective", "")):
        for sentence in _sentences(bullet):
            placed.append(
                _Placed(
                    field=_classify_objective(sentence),
                    text=sentence,
                    preference_ok=True,
                )
            )
    for problem in _problems(sections.get("assessment", "")):
        texts = [problem["assessment"], *problem["plan"]]
        for text in texts:
            if text:
                placed.append(
                    _Placed(
                        field=f"assessment_and_plan.problems:{problem['problem']}",
                        text=text,
                        preference_ok=True,
                    )
                )
    return placed


def _score_field(
    field: str,
    claims: list[_Placed],
    *,
    transcript_norm: str,
    prior_norm: str,
    transcript_raw: str,
    prior_raw: str,
    preference_rule: str | None,
    sections_in_order: bool,
) -> dict[str, Any]:
    if not claims:
        return {
            "field": _public_field(field),
            "correctness": "empty",
            "fabrication": False,
            "fluency": "not_applicable",
            "coherence": "not_applicable",
            "preference_adherence": "not_applicable",
            "uncertainty": "No explicit statement in the note.",
            "claim_count": 0,
        }
    supports = [
        _support(claim.text, transcript_norm, prior_norm, transcript_raw, prior_raw)
        for claim in claims
    ]
    kinds = {item.kind for item in supports}
    if "unsupported" in kinds:
        correctness = "unsupported"
    elif "uncertain" in kinds:
        correctness = "uncertain"
    else:
        correctness = "supported"
    uncertainties = list(
        dict.fromkeys(item.uncertainty for item in supports if item.uncertainty)
    )
    fluency_fail = any(_fluency_fail(claim.text) for claim in claims)
    subjective = field in _SUBJECTIVE_FIELDS or field.startswith("subjective.")
    if preference_rule is None or not subjective:
        preference = "not_applicable"
    elif all(claim.preference_ok for claim in claims):
        preference = "pass"
    else:
        preference = "fail"
    return {
        "field": _public_field(field),
        "correctness": correctness,
        "fabrication": any(item.fabrication for item in supports),
        "fluency": "fail" if fluency_fail else "pass",
        "coherence": "pass" if sections_in_order else "fail",
        "preference_adherence": preference,
        "uncertainty": " ".join(uncertainties) or None,
        "claim_count": len(claims),
    }


def _support(
    text: str,
    transcript_norm: str,
    prior_norm: str,
    transcript_raw: str,
    prior_raw: str,
) -> _Support:
    tokens = _tokens(text)
    transcript_hits = 0
    prior_hits = 0
    misses: list[str] = []
    for token in tokens:
        if _token_in(token, transcript_norm):
            transcript_hits += 1
        elif prior_norm and _token_in(token, prior_norm):
            prior_hits += 1
        else:
            misses.append(token)
    missing_numbers = [
        number
        for number in _NUMBER.findall(text)
        if not _number_in(number, transcript_raw) and not _number_in(number, prior_raw)
    ]
    year_gaps = [number for number in missing_numbers if _YEAR.match(number)]
    hard_numbers = [number for number in missing_numbers if number not in year_gaps]
    uncertainties: list[str] = []
    if year_gaps:
        uncertainties.append(
            "Calendar year "
            + ", ".join(year_gaps)
            + " is not in the source; the note infers it."
        )
    if prior_hits and not hard_numbers:
        uncertainties.append(
            "Some wording is only in gathered prior context, not this visit transcript."
        )
    if misses:
        unique_misses = list(dict.fromkeys(misses))
        uncertainties.append(
            "Wording not in the source: " + ", ".join(unique_misses[:6]) + "."
        )
    if hard_numbers:
        listed = ", ".join(hard_numbers)
        return _Support(
            kind="unsupported",
            fabrication=True,
            uncertainty=f"Number {listed} is not in the source. "
            + " ".join(uncertainties),
        )
    total = len(tokens) or 1
    grounded = transcript_hits + prior_hits
    if not tokens and not hard_numbers:
        return _Support("supported", False, None)
    if not misses and prior_hits == 0:
        return _Support("supported", False, " ".join(uncertainties) or None)
    if grounded / total >= 0.5:
        return _Support("uncertain", False, " ".join(uncertainties) or None)
    return _Support(
        kind="unsupported",
        fabrication=True,
        uncertainty="Not supported by the source. " + " ".join(uncertainties),
    )


def _public_field(field: str) -> str:
    if field.startswith("assessment_and_plan.problems:"):
        name = field.split(":", 1)[1]
        return f"assessment_and_plan.problems[{name}]"
    mapping = {
        "chief_complaint": "subjective.chief_complaint",
        "past_medical_history": "subjective.relevant_history.past_medical_history",
        "family_history": "subjective.relevant_history.family_history",
        "lifestyle": "subjective.relevant_history.social_history.lifestyle",
        "social_determinants": (
            "subjective.relevant_history.social_history.social_determinants"
        ),
        "occupational_exposures": (
            "subjective.relevant_history.social_history.occupational_exposures"
        ),
        "substance_use": "subjective.relevant_history.social_history.substance_use",
        "vital_signs": "objective.vital_signs",
        "physical_examination": "objective.physical_examination",
        "mental_status_examination": "objective.mental_status_examination",
        "completed_investigations": "objective.completed_investigations",
        "other_objective_findings": "objective.other_objective_findings",
    }
    if field in mapping:
        return mapping[field]
    if field in _HPI_FIELDS:
        return f"subjective.history_of_present_illness.{field}"
    return field


def _field_names(clinical: dict[str, Any]) -> list[str]:
    names = list(_SUBJECTIVE_FIELDS)
    names.extend(_OBJECTIVE_FIELDS)
    problems = clinical["assessment_and_plan"]["problems"]
    if isinstance(problems, list) and problems:
        for problem in problems:
            if isinstance(problem, dict):
                names.append(
                    "assessment_and_plan.problems:" + str(problem.get("problem", ""))
                )
    else:
        names.append("assessment_and_plan.problems")
    return names


def _store_claim(clinical: dict[str, Any], item: _Placed) -> None:
    if item.field in _HPI_FIELDS:
        clinical["subjective"]["history_of_present_illness"][item.field][
            "claims"
        ].append({"text": item.text})
        return
    if item.field == "chief_complaint":
        clinical["subjective"]["chief_complaint"]["claims"].append({"text": item.text})
        return
    if item.field == "past_medical_history":
        clinical["subjective"]["relevant_history"]["past_medical_history"][
            "claims"
        ].append({"text": item.text})
        return
    if item.field == "family_history":
        clinical["subjective"]["relevant_history"]["family_history"]["claims"].append(
            {"text": item.text}
        )
        return
    if item.field in {
        "lifestyle",
        "social_determinants",
        "occupational_exposures",
        "substance_use",
    }:
        clinical["subjective"]["relevant_history"]["social_history"][item.field][
            "claims"
        ].append({"text": item.text})
        return
    if item.field in {"vital_signs", "mental_status_examination", "other_objective_findings"}:
        clinical["objective"][item.field]["claims"].append({"text": item.text})
        return
    if item.field in {"physical_examination", "completed_investigations"}:
        clinical["objective"][item.field].append(item.text)


def _empty_note() -> dict[str, Any]:
    hpi: dict[str, dict[str, list[dict[str, str]]]] = {
        name: {"claims": []} for name in _HPI_FIELDS
    }
    return {
        "subjective": {
            "chief_complaint": {"claims": []},
            "history_of_present_illness": hpi,
            "relevant_history": {
                "past_medical_history": {"claims": []},
                "social_history": {
                    "lifestyle": {"claims": []},
                    "social_determinants": {"claims": []},
                    "occupational_exposures": {"claims": []},
                    "substance_use": {"claims": []},
                },
                "family_history": {"claims": []},
            },
        },
        "objective": {
            "vital_signs": {"claims": []},
            "physical_examination": [],
            "mental_status_examination": {"claims": []},
            "completed_investigations": [],
            "other_objective_findings": {"claims": []},
        },
        "assessment_and_plan": {"problems": []},
    }


def _split_sections(note: str) -> dict[str, str]:
    matches = list(_HEADER.finditer(note))
    sections = {"subjective": "", "objective": "", "assessment": ""}
    if not matches:
        sections["subjective"] = note
        return sections
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(note)
        body = note[start:end].strip()
        title = match.group(1).lower()
        if "subjective" in title:
            sections["subjective"] = body
        elif "objective" in title:
            sections["objective"] = body
        elif "assessment" in title or "plan" in title:
            sections["assessment"] = body
    return sections


def _sections_in_order(note: str) -> bool:
    titles = [match.group(1).lower() for match in _HEADER.finditer(note)]
    order = [
        next((title for title in titles if key in title), None)
        for key in ("subjective", "objective", "assessment")
    ]
    # "plan" may be the assessment header.
    if order[2] is None:
        order[2] = next((title for title in titles if "plan" in title), None)
    present = [title for title in order if title is not None]
    if len(present) < 2:
        return True
    positions = [titles.index(title) for title in present]
    return positions == sorted(positions)


def _bullets(section: str) -> list[str]:
    bullets: list[str] = []
    for raw in section.splitlines():
        line = raw.strip()
        if line.startswith("- "):
            bullets.append(line[2:].strip())
    return bullets


def _problems(section: str) -> list[dict[str, Any]]:
    problems: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for raw in section.splitlines():
        line = raw.strip()
        if not line:
            continue
        match = _PROBLEM.match(line)
        if match:
            current = {
                "problem": match.group(1).strip(),
                "assessment": match.group(2).strip(),
                "plan": [],
            }
            problems.append(current)
            continue
        if current is None:
            continue
        if line.startswith("- "):
            current["plan"].append(line[2:].strip())
        else:
            extra = line[2:].strip() if line.startswith("- ") else line
            current["assessment"] = (current["assessment"] + " " + extra).strip()
    # Problems are created before claims are stored, so the note shell needs them
    # even when scoring has not run. The caller stores plan text separately.
    return problems


def _sentences(text: str) -> list[str]:
    parts = [part.strip() for part in _SENTENCE_SPLIT.split(text.strip()) if part.strip()]
    return parts or [text.strip()]


def _classify_subjective(text: str) -> str:
    lowered = text.lower()
    checks: tuple[tuple[str, tuple[str, ...]], ...] = (
        ("family_history", ("mother", "father", "parent", "sister", "brother", "family")),
        ("substance_use", ("alcohol", "coffee", "espresso", "smok", "cannabis", "vape")),
        ("occupational_exposures", ("work from home", "work-from-home", "occupational", "job")),
        ("social_determinants", ("moved", "moving", "homeless", "housing")),
        ("lifestyle", ("water", "hydrat", "exercise", "diet", "sleep")),
        (
            "past_medical_history",
            ("history of", "previously", "years ago", "early 20", "autoimmune", "investigat"),
        ),
        ("chief_complaint", ("follow-up", "follow up", "presents", "reason for")),
        ("associated_symptoms", ("cough", "hot flash", "pain", "nausea", "fever", "fatigue")),
        ("quality", ("dry", "itchy", "sharp", "burning", "dull")),
        ("onset", ("on the", "started", "onset", "returned", "ago")),
        ("duration", ("week", "month", "days")),
        ("frequency", ("occasional", "sometimes", "daily", "per day")),
        ("severity", ("feeling good", "feels well", "feels good", "severe", "mild")),
        ("progression", ("stabil", "worsen", "improv", "another week", "recur")),
        ("relieving_factors", ("relief", "reliev", "better when")),
        ("exacerbating_factors", ("worse when", "exacerbat")),
        ("self_treatment", ("tried", "ibuprofen", "acetaminophen")),
        ("impact_on_daily_activities", ("daily activities", "unable to", "work")),
    )
    for field, needles in checks:
        if any(needle in lowered for needle in needles):
            return field
    return "context"


def _classify_objective(text: str) -> str:
    lowered = text.lower()
    if any(
        needle in lowered
        for needle in (
            "blood pressure",
            "heart rate",
            "pulse",
            "temperature",
            "spo2",
            "respiratory rate",
            "vital",
        )
    ):
        return "vital_signs"
    if any(needle in lowered for needle in ("mental status", "affect", "oriented", "mood")):
        return "mental_status_examination"
    if any(
        needle in lowered
        for needle in ("examination", "tender", "auscult", "palpat", "lungs clear")
    ):
        return "physical_examination"
    if any(
        needle in lowered
        for needle in (
            "potassium",
            "egfr",
            "white blood",
            "cholesterol",
            "liver",
            "hematology",
            "hemoglobin",
            "creatinine",
            "panel",
            "bloodwork",
            "lab",
        )
    ):
        return "completed_investigations"
    return "other_objective_findings"


def _tokens(text: str) -> list[str]:
    words = re.findall(r"[a-z][a-z0-9]+", text.lower())
    tokens: list[str] = []
    for word in words:
        if word in _STOP:
            continue
        if len(word) < 4 and word not in _SHORT_OK:
            continue
        tokens.append(word)
    return tokens


def _token_in(token: str, normalized: str) -> bool:
    if re.search(rf"\b{re.escape(token)}\b", normalized):
        return True
    for phrase in _SYNONYMS.get(token, ()):
        if phrase in normalized:
            return True
    stem = _stem(token)
    if len(stem) < 4:
        return False
    for word in normalized.split():
        if _stem(word.strip(".")) == stem:
            return True
    return False


def _stem(word: str) -> str:
    for suffix in ("ing", "ed", "ly", "es", "s"):
        if word.endswith(suffix) and len(word) - len(suffix) >= 4:
            return word[: -len(suffix)]
    return word


def _number_in(number: str, raw: str) -> bool:
    if number in raw:
        return True
    word = _NUMBER_WORDS.get(number)
    if word is None:
        return False
    return re.search(rf"\b{word}\b", raw, re.IGNORECASE) is not None


def _normalize(text: str) -> str:
    lowered = _SPEAKER.sub(" ", text.lower())
    lowered = re.sub(r"[^a-z0-9.]+", " ", lowered)
    return re.sub(r"\s+", " ", lowered).strip()


def _fluency_fail(text: str) -> bool:
    if _RESIDUE.search(text):
        return True
    return re.search(r"[A-Za-z]", text) is None


def _html_to_text(html: str) -> str:
    text = re.sub(r"<br\s*/?>", "\n", html, flags=re.IGNORECASE)
    text = re.sub(r"</(p|h2|li|div|ul)>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    return text.replace("&amp;", "&").replace("&nbsp;", " ")


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []
