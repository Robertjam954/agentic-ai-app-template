"""E&M field layout for clinical-note extraction.

History, exam, and medical decision making follow the 1995 and 1997 E&M
guidelines. History has four elements: chief complaint, the eight-element
history of present illness, review of systems, and past/family/social history.
Instructor validates the chief complaint and the HPI elements.

NOTE: do not change the field names. The runner and the results page share them.
"""

from __future__ import annotations

import re
from typing import Any

import instructor
from pydantic import BaseModel, Field, ValidationError, field_validator

HPI_FIELDS = (
    "location",
    "quality",
    "severity",
    "duration",
    "timing",
    "context",
    "modifying_factors",
    "associated_signs_and_symptoms",
)

ROS_SYSTEMS = (
    "constitutional",
    "eyes",
    "ears_nose_mouth_throat",
    "cardiovascular",
    "respiratory",
    "gastrointestinal",
    "genitourinary",
    "musculoskeletal",
    "integumentary",
    "neurologic",
    "psychiatric",
    "endocrine",
    "hematologic_lymphatic",
    "allergic_immunologic",
)

PFSH_AREAS = ("past_history", "family_history", "social_history")

EXAM_ORGAN_SYSTEMS = (
    "constitutional",
    "eyes",
    "ears_nose_mouth_throat",
    "cardiovascular",
    "respiratory",
    "gastrointestinal",
    "genitourinary",
    "musculoskeletal",
    "skin",
    "neurologic",
    "psychiatric",
    "hematologic_lymphatic_immunologic",
)

EXAM_BODY_AREAS = (
    "head",
    "neck",
    "chest",
    "abdomen",
    "genitalia_groin_buttocks",
    "back",
    "extremity",
)

# (field id, needles). First match wins, except review-of-systems sentences,
# which can document more than one system.
PFSH_CHECKS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "history.pfsh.family_history",
        ("mother", "father", "parent", "sister", "brother", "family"),
    ),
    (
        "history.pfsh.social_history",
        (
            "alcohol",
            "coffee",
            "espresso",
            "smok",
            "cannabis",
            "vape",
            "water",
            "hydrat",
            "exercise",
            "diet",
            "sleep",
            "work from home",
            "work-from-home",
            "occupational",
            "job",
            "moved",
            "moving",
            "homeless",
            "housing",
        ),
    ),
    (
        "history.pfsh.past_history",
        (
            "history of",
            "previously",
            "years ago",
            "early 20",
            "autoimmune",
            "investigat",
        ),
    ),
)

HPI_CHECKS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "history.hpi.associated_signs_and_symptoms",
        ("cough", "hot flash", "pain", "nausea", "fever", "fatigue", "symptom"),
    ),
    (
        "history.hpi.modifying_factors",
        ("relief", "reliev", "better when", "worse when", "exacerbat", "no impact"),
    ),
    (
        "history.hpi.quality",
        ("dry", "itchy", "sharp", "burning", "dull", "throbbing"),
    ),
    ("history.hpi.duration", ("day", "week", "month", "hour", "year", "minute")),
    (
        "history.hpi.timing",
        (
            "occasional",
            "sometimes",
            "daily",
            "per day",
            "at night",
            "in the morning",
            "started",
            "onset",
            "ago",
            "returned",
        ),
    ),
    (
        "history.hpi.severity",
        ("feeling good", "feels well", "feels good", "severe", "mild", "moderate"),
    ),
    ("history.hpi.location", ("left side", "right side", "chest", "abdomen", "site")),
    (
        "history.hpi.context",
        ("while i", "while she", "while he", "during the", "after the"),
    ),
    (
        "history.chief_complaint",
        ("follow-up", "follow up", "presents", "reason for", "here for"),
    ),
)

ROS_CHECKS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "history.ros.constitutional",
        ("fever", "chills", "weight loss", "night sweat", "fatigue"),
    ),
    ("history.ros.eyes", ("vision", "eye", "eyes")),
    (
        "history.ros.ears_nose_mouth_throat",
        ("ear", "hearing", "nose", "sinus", "throat", "mouth"),
    ),
    (
        "history.ros.cardiovascular",
        ("chest pain", "palpitation", "edema"),
    ),
    (
        "history.ros.respiratory",
        ("cough", "wheez", "short of breath", "dyspnea"),
    ),
    (
        "history.ros.gastrointestinal",
        ("nausea", "vomit", "diarrhea", "constipation", "abdominal"),
    ),
    ("history.ros.genitourinary", ("urin", "dysuria", "vaginal")),
    (
        "history.ros.musculoskeletal",
        ("joint", "muscle", "back pain", "stiffness"),
    ),
    ("history.ros.integumentary", ("rash", "skin", "lesion", "breast")),
    ("history.ros.neurologic", ("headache", "dizz", "numb", "seizure")),
    ("history.ros.psychiatric", ("depression", "anxiety", "mood")),
    ("history.ros.endocrine", ("thyroid", "diabetes", "polyuria")),
    ("history.ros.hematologic_lymphatic", ("bleeding", "bruising", "lymph")),
    ("history.ros.allergic_immunologic", ("allerg", "hives", "immune")),
)

EXAM_ORGAN_CHECKS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "exam.organ.constitutional",
        (
            "blood pressure",
            "heart rate",
            "pulse",
            "temperature",
            "spo2",
            "respiratory rate",
            "vital",
        ),
    ),
    ("exam.organ.eyes", ("pupil", "fundus", "conjunctiv")),
    ("exam.organ.ears_nose_mouth_throat", ("tympanic", "oropharynx", "nares")),
    ("exam.organ.cardiovascular", ("murmur", "heart sound", "rhythm")),
    ("exam.organ.respiratory", ("lungs clear", "auscult", "wheeze on exam")),
    ("exam.organ.gastrointestinal", ("abdomen soft", "bowel sound", "tender")),
    ("exam.organ.genitourinary", ("pelvic exam", "genital")),
    ("exam.organ.musculoskeletal", ("range of motion", "joint exam")),
    ("exam.organ.skin", ("rash on exam", "lesion on exam", "skin exam")),
    ("exam.organ.neurologic", ("cranial nerve", "reflex", "oriented")),
    ("exam.organ.psychiatric", ("mental status", "thought process", "thought content")),
    ("exam.organ.hematologic_lymphatic_immunologic", ("lymph node", "lymphaden")),
)

EXAM_AREA_CHECKS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("exam.area.head", ("face", "scalp")),
    ("exam.area.neck", ("neck supple", "thyroid exam")),
    ("exam.area.chest", ("chest wall", "axilla")),
    ("exam.area.abdomen", ("abdomen",)),
    ("exam.area.genitalia_groin_buttocks", ("groin", "buttock")),
    ("exam.area.back", ("spine", "lumbar")),
    ("exam.area.extremity", ("extremity", "arm", "leg")),
)

DATA_CHECKS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "mdm.data_reviewed",
        (
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
        ),
    ),
)

_REVIEW = re.compile(
    r"\b(?:denies|denied|negative|review of systems|ros)\b|\ball other systems\b",
    re.IGNORECASE,
)


class Claim(BaseModel):
    text: str = Field(..., min_length=1)

    @field_validator("text")
    @classmethod
    def validate_text(cls, value: str) -> str:
        cleaned = " ".join(value.split())
        if not re.search(r"[A-Za-z]", cleaned):
            raise ValueError(
                "Claim text must be a statement, not a blank or a bare number"
            )
        return cleaned


class ClaimList(BaseModel):
    claims: list[Claim] = Field(default_factory=list)


def _matching(claims: list[Claim], pattern: str, message: str) -> list[Claim]:
    for claim in claims:
        if re.search(pattern, claim.text, re.IGNORECASE) is None:
            raise ValueError(message)
    return claims


class ChiefComplaint(BaseModel):
    """A statement, in the patient's words, that gives the reason for the encounter."""

    statement: ClaimList = Field(default_factory=ClaimList)


class HistoryOfPresentIllness(BaseModel):
    """Chronological description of the present illness. Eight elements."""

    location: ClaimList = Field(
        default_factory=ClaimList, description="Site of the problem or symptom."
    )
    quality: ClaimList = Field(
        default_factory=ClaimList,
        description="Description or characteristics of the problem or symptom.",
    )
    severity: ClaimList = Field(
        default_factory=ClaimList,
        description="Intensity, degree, or measure of the problem or symptom.",
    )
    duration: ClaimList = Field(
        default_factory=ClaimList,
        description="Length of time the problem or symptom has existed.",
    )
    timing: ClaimList = Field(
        default_factory=ClaimList,
        description="Regularity of occurrence, or when the problem or symptom occurs.",
    )
    context: ClaimList = Field(
        default_factory=ClaimList,
        description="Events surrounding the occurrence of the problem or symptom.",
    )
    modifying_factors: ClaimList = Field(
        default_factory=ClaimList,
        description="Factors that relieve, exacerbate, or do not impact the problem.",
    )
    associated_signs_and_symptoms: ClaimList = Field(
        default_factory=ClaimList,
        description="Other problems or symptoms that accompany the main one.",
    )

    @field_validator("duration")
    @classmethod
    def validate_duration(cls, value: ClaimList) -> ClaimList:
        value.claims = _matching(
            value.claims,
            r"\b(?:day|days|week|weeks|month|months|year|years|hour|hours|minute|minutes)\b",
            "Duration must be a length of time",
        )
        return value

    @field_validator("timing")
    @classmethod
    def validate_timing(cls, value: ClaimList) -> ClaimList:
        value.claims = _matching(
            value.claims,
            r"\b(?:daily|occasional|sometimes|night|morning|started|onset|ago|returned|every|when)\b|per day",
            "Timing must say when it occurs or how regular it is",
        )
        return value

    @field_validator("severity")
    @classmethod
    def validate_severity(cls, value: ClaimList) -> ClaimList:
        value.claims = _matching(
            value.claims,
            r"\b(?:mild|moderate|severe|intensity|degree|feeling good|feels well|feels good)\b|\d+\s*/\s*10",
            "Severity must be an intensity, degree, or measure",
        )
        return value

    @field_validator("modifying_factors")
    @classmethod
    def validate_modifying_factors(cls, value: ClaimList) -> ClaimList:
        value.claims = _matching(
            value.claims,
            r"relief|reliev|better when|worse when|exacerbat|no impact|impact",
            "Modifying factors must relieve, exacerbate, or have no impact",
        )
        return value


ChiefComplaintResponse = instructor.response_schema(ChiefComplaint)
HpiResponse = instructor.response_schema(HistoryOfPresentIllness)


def complaint_schema() -> dict[str, Any]:
    schema = ChiefComplaintResponse.model_json_schema()
    if not isinstance(schema, dict):
        raise TypeError("chief_complaint: Instructor schema was not an object")
    return schema


def hpi_schema() -> dict[str, Any]:
    schema = HpiResponse.model_json_schema()
    if not isinstance(schema, dict):
        raise TypeError("hpi: Instructor schema was not an object")
    return schema


def _clean_lists(raw: dict[str, Any], path: str) -> dict[str, Any]:
    cleaned: dict[str, Any] = {}
    for name, value in raw.items():
        if not isinstance(value, dict):
            raise ValueError(f"{path}.{name}: expected a claims object")
        try:
            cleaned[name] = ClaimList.model_validate(value).model_dump()
        except ValidationError as exc:
            raise ValueError(f"{path}.{name}: {exc}") from exc
    return cleaned


def validate_history(history: dict[str, Any]) -> dict[str, Any]:
    """Validate chief complaint and HPI. Prefix errors with the field path."""
    try:
        complaint = ChiefComplaintResponse.model_validate(
            {"statement": history.get("chief_complaint", {"claims": []})}
        )
        hpi = HpiResponse.model_validate(history.get("history_of_present_illness", {}))
    except ValidationError as exc:
        raise ValueError(f"history: {exc}") from exc
    history["chief_complaint"] = complaint.statement.model_dump()
    history["history_of_present_illness"] = hpi.model_dump()
    history["review_of_systems"] = _clean_lists(
        history.get("review_of_systems", {}), "history.review_of_systems"
    )
    history["pfsh"] = _clean_lists(history.get("pfsh", {}), "history.pfsh")
    return history


def is_system_review(text: str) -> bool:
    return _REVIEW.search(text) is not None


def history_fields(text: str, *, explicit: bool = False) -> list[str]:
    """Place one subjective sentence into the history element it documents.

    ``explicit`` skips the chief-complaint default. Capacity uses that so an
    unmatched sentence is not treated as a field the transcript opened.
    """
    lowered = text.lower()
    for field, needles in PFSH_CHECKS:
        if any(_hit(needle, lowered) for needle in needles):
            return [field]
    if is_system_review(lowered):
        systems = [
            field
            for field, needles in ROS_CHECKS
            if any(_hit(needle, lowered) for needle in needles)
        ]
        if systems:
            return systems
    for field, needles in HPI_CHECKS:
        if any(_hit(needle, lowered) for needle in needles):
            return [field]
    if explicit:
        return []
    return ["history.chief_complaint"]


_EXAM_CUE = re.compile(
    r"\b(?:exam|examination|auscult|lungs|murmur|pupil|reflex|oriented)\b",
    re.IGNORECASE,
)


def capacity_fields(text: str) -> list[str]:
    """Fields this transcript sentence actually opens. No chief-complaint default."""
    found = history_fields(text, explicit=True)
    lowered = text.lower()
    for field, needles in DATA_CHECKS:
        if any(_hit(needle, lowered) for needle in needles):
            found.append(field)
    for field, needles in EXAM_ORGAN_CHECKS:
        if any(_hit(needle, lowered) for needle in needles):
            found.append(field)
    if _EXAM_CUE.search(lowered):
        for field, needles in EXAM_AREA_CHECKS:
            if any(_hit(needle, lowered) for needle in needles):
                found.append(field)
    return list(dict.fromkeys(found))


def objective_field(text: str) -> str:
    """Place one objective sentence into exam or into data reviewed."""
    lowered = text.lower()
    for field, needles in DATA_CHECKS:
        if any(_hit(needle, lowered) for needle in needles):
            return field
    for field, needles in EXAM_ORGAN_CHECKS:
        if any(_hit(needle, lowered) for needle in needles):
            return field
    for field, needles in EXAM_AREA_CHECKS:
        if any(_hit(needle, lowered) for needle in needles):
            return field
    return "exam.other"


_STEMS = {
    "allerg",
    "dizz",
    "exacerbat",
    "hydrat",
    "investigat",
    "reliev",
    "smok",
    "urin",
    "vomit",
    "wheez",
}


def _hit(needle: str, lowered: str) -> bool:
    if " " in needle:
        return needle in lowered
    pattern = rf"\b{re.escape(needle)}"
    if needle not in _STEMS:
        pattern += r"(?:es|s)?\b"
    return re.search(pattern, lowered) is not None


def history_level(
    *,
    cc: bool,
    hpi: int,
    ros: int,
    pfsh: int,
    established: bool,
) -> str:
    """Highest history type whose CC, HPI, ROS, and PFSH requirements are met.

    Extended HPI is 4 or more elements and still satisfies a brief (1-3) requirement.
    Complete PFSH is 2 of 3 areas for an established visit and 3 of 3 otherwise.
    """
    if not cc:
        return "none"
    complete_pfsh = 2 if established else 3
    if hpi >= 4 and ros >= 10 and pfsh >= complete_pfsh:
        return "comprehensive"
    if hpi >= 4 and ros >= 2 and pfsh >= 1:
        return "detailed"
    if hpi >= 1 and ros >= 1:
        return "expanded_problem_focused"
    if hpi >= 1:
        return "problem_focused"
    return "none"


def exam_level_1995(documented: int) -> str:
    """1995 exam level from the count of documented organ systems or body areas.

    Expanded problem focused is 2-5 and detailed is 6-7 in the table used here.
    The 2-7 band is ambiguous across carriers, so this split is stated, not hidden.
    """
    if documented >= 8:
        return "comprehensive"
    if documented >= 6:
        return "detailed"
    if documented >= 2:
        return "expanded_problem_focused"
    if documented >= 1:
        return "problem_focused"
    return "none"


def em_summary(
    note: dict[str, Any], *, established: bool, ros_complete_notation: bool
) -> dict[str, Any]:
    """Counts and levels from the extracted note. Risk is not scored."""
    history = note["history"]
    cc = bool(history["chief_complaint"]["claims"])
    hpi_present = [
        name
        for name in HPI_FIELDS
        if history["history_of_present_illness"][name]["claims"]
    ]
    ros_present = [
        name for name in ROS_SYSTEMS if history["review_of_systems"][name]["claims"]
    ]
    pfsh_present = [name for name in PFSH_AREAS if history["pfsh"][name]["claims"]]
    ros_for_level = len(ros_present)
    if ros_complete_notation:
        ros_for_level = max(ros_for_level, 10)
    exam = note["exam"]
    organs = [
        name for name in EXAM_ORGAN_SYSTEMS if exam["organ_systems"][name]["claims"]
    ]
    areas = [name for name in EXAM_BODY_AREAS if exam["body_areas"][name]["claims"]]
    documented = len(organs) + len(areas)
    problems = note["medical_decision_making"]["diagnoses_or_management_options"]
    data = note["medical_decision_making"]["data_reviewed"]["claims"]
    return {
        "history": {
            "chief_complaint": cc,
            "hpi_elements": hpi_present,
            "hpi_count": len(hpi_present),
            "ros_systems": ros_present,
            "ros_count": len(ros_present),
            "ros_count_for_level": ros_for_level,
            "pfsh_areas": pfsh_present,
            "pfsh_count": len(pfsh_present),
            "established_visit": established,
            "level": history_level(
                cc=cc,
                hpi=len(hpi_present),
                ros=ros_for_level,
                pfsh=len(pfsh_present),
                established=established,
            ),
        },
        "exam": {
            "guideline_scored": "1995",
            "organ_systems": organs,
            "body_areas": areas,
            "documented": documented,
            "level": exam_level_1995(documented),
            "level_1997": None,
        },
        "medical_decision_making": {
            "diagnoses": len(problems) if isinstance(problems, list) else 0,
            "data_items": len(data),
            "risk": None,
            "type": None,
        },
    }
