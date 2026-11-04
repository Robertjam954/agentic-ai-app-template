"""Chief complaint schema for the clinical-note eval.

The history of present illness is the chief complaint: a statement, in the
patient's words, that gives the reason for the encounter. Each complaint has
the properties below. Instructor validates that shape with Pydantic field
validators, the same pattern as
https://python.useinstructor.com/learning/patterns/field_validation/

NOTE: do not change this export format. The runner and the results page share
these field names.
"""

from __future__ import annotations

import re
from typing import Any

import instructor
from pydantic import BaseModel, Field, ValidationError, field_validator

# Stable names. Order is the order the results page lists them.
COMPLAINT_FIELDS = (
    "statement",
    "location",
    "quality",
    "severity",
    "duration",
    "timing",
    "context",
    "modifying_factors",
    "associated_signs_and_symptoms",
)

FIELD_LABELS = {
    "statement": "Statement",
    "location": "Location",
    "quality": "Quality",
    "severity": "Severity",
    "duration": "Duration",
    "timing": "Timing",
    "context": "Context",
    "modifying_factors": "Modifying factors",
    "associated_signs_and_symptoms": "Associated signs and symptoms",
}


class Claim(BaseModel):
    """One sentence placed under a chief-complaint property."""

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
    """One chief complaint and the properties that describe it."""

    statement: ClaimList = Field(
        default_factory=ClaimList,
        description="A statement, in the patient's words, that gives the reason for the encounter.",
    )
    location: ClaimList = Field(
        default_factory=ClaimList,
        description="Site of the complaint.",
    )
    quality: ClaimList = Field(
        default_factory=ClaimList,
        description="Description or characteristics of the complaint.",
    )
    severity: ClaimList = Field(
        default_factory=ClaimList,
        description="Intensity, degree, or measure of the complaint.",
    )
    duration: ClaimList = Field(
        default_factory=ClaimList,
        description="Length of time the complaint has been present.",
    )
    timing: ClaimList = Field(
        default_factory=ClaimList,
        description="Regularity, or when the complaint occurs.",
    )
    context: ClaimList = Field(
        default_factory=ClaimList,
        description="Events surrounding the complaint.",
    )
    modifying_factors: ClaimList = Field(
        default_factory=ClaimList,
        description="What relieves the complaint, exacerbates it, or has no impact.",
    )
    associated_signs_and_symptoms: ClaimList = Field(
        default_factory=ClaimList,
        description="Other problems that accompany the complaint.",
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


# Instructor response model. Field validators above are what it retries on.
ChiefComplaintResponse = instructor.response_schema(ChiefComplaint)


def complaint_schema() -> dict[str, Any]:
    """JSON schema Instructor sends for one chief complaint."""
    schema = ChiefComplaintResponse.model_json_schema()
    if not isinstance(schema, dict):
        raise TypeError("chief_complaint: Instructor schema was not an object")
    return schema


def validate_chief_complaints(raw: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Validate complaints and return the JSON shape.

    Errors are prefixed with the field path, in the same way a failed read
    names the file before the parser message. Instructor uses these validators
    when it retries a provider response.
    """
    validated: list[dict[str, Any]] = []
    for index, item in enumerate(raw):
        path = f"chief_complaints[{index}]"
        try:
            complaint = ChiefComplaintResponse.model_validate(item)
        except ValidationError as exc:
            raise ValueError(f"{path}: {exc}") from exc
        validated.append(complaint.model_dump())
    return validated
