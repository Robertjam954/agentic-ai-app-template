---
cursor:
  subagentId: "bc-536bbaf5-1274-574a-a879-52db67fe381d"
---

# Clinical note eval shape

Each clinical note eval is one JSON object. `source_document.text` is the voice transcript. `clinical_note` is the structured note, with one top-level key per major section. `evaluation.field_results` scores each extracted feature. `evaluation.metrics` reports fabrication rate, correctness, completeness, fluency, coherence, and preference adherence.

Fabrication rate, correctness, fluency, coherence, and preference adherence use the claims written in the raw clinical note. Completeness uses the claims in the dictation. The same six rates are also reported for each major section, using only that section's claims. A section with no claims in the relevant set has denominator 0.

Every feature that is filled cites the exact dictated lines that determined it. The citation is the file name and the line numbers in that file.

## Major sections

| Key | What the transcript can open |
| --- | --- |
| `case_description` | Historian, reliability, and the chief concern. The chief concern is one statement, in the patient's words, of the reason for the encounter |
| `hpi` | Location, quality, severity, duration, timing, context, modifying factors, associated signs and symptoms |
| `pmh` | Past medical history, surgical history, hospitalizations, immunizations, allergies, medications |
| `family_history` | Conditions, hereditary disease, relatives |
| `social_history` | Occupation, living situation, tobacco, alcohol, substances, and the other social-history lines |
| `review_of_systems` | The 11 systems below, in this order |
| `physical_exam` | The 7 body areas below, in this order |
| `labs_studies_imaging` | Labs, ECG, imaging, microbiology, and other studies the clinician stated |
| `assessment_and_plan` | One object per problem. Assessment and plan for that problem live together |

A feature counts toward a section only when the transcript states it. Patient speech opens history features. Clinician speech opens exam findings, studies, impressions, and plans. A feature stated only in prior context does not increase the denominator.

## Evidence

A filled feature is a claim. Each claim carries the exact transcript span used to decide it.

```json
{
  "text": "Raised white cells are likely from the recent infection, and the count should be repeated.",
  "evidence": [
    {
      "file": "internal/note-0001-transcript.txt",
      "line_start": 39,
      "line_end": 39,
      "quote": "clinician_38: Yeah. It sounds like you may have picked up a virus and, um, your hematology panel shows a raised white blood cells. Now, white blood cells are involved in fighting infection, so that can be, I think it's- "
    },
    {
      "file": "internal/note-0001-transcript.txt",
      "line_start": 47,
      "line_end": 47,
      "quote": "clinician_46: ... I, I, I think it is likely due to, um, the infection you were having. I would like to repeat it just to make sure though. "
    }
  ]
}
```

`file` is the dictated transcript, one speaker turn per line. `line_start` and `line_end` are 1-based and inclusive. `quote` is those lines copied as they stand, including the speaker label. A claim that draws on two separated turns uses two evidence objects. A claim with no evidence, or a quote that is not on those lines of that file, is not a supported feature.

For note-0001, open `internal/note-0001-transcript.txt` and go to the line number. That file is `inputs.transcript_prompt_at_generation` from `internal/note-0001.json`, split on newlines. Line 39 is the raised white-cell sentence. Line 47 is the repeat-the-count sentence.

An empty feature stays `{ "claims": [] }`. It has no evidence because the transcript did not open it.

## Review of systems

Stored in this order:

1. Cardiovascular
2. Ears, Nose, Mouth, and Throat
3. Eyes
4. Genitourinary (Female)
5. Genitourinary (Male)
6. Hematologic/Lymphatic/Immunologic
7. Musculoskeletal
8. Neurologic
9. Psychiatric
10. Respiratory
11. Skin

Keys: `cardiovascular`, `ears_nose_mouth_throat`, `eyes`, `genitourinary_female`, `genitourinary_male`, `hematologic_lymphatic_immunologic`, `musculoskeletal`, `neurologic`, `psychiatric`, `respiratory`, `skin`.

Each system is `positive`, `negative`, or `not_asked`. `not_asked` does not count as a feature the transcript opened. Extended is 2–9 documented systems. Complete is 10 or more, or a note that all other systems are negative.

## Physical exam

Body areas, stored in this order:

1. Head, including the face
2. Neck
3. Chest, including breasts and axillae
4. Abdomen
5. Genitalia, groin, buttocks
6. Back, including spine
7. Each extremity

Keys: `head`, `neck`, `chest`, `abdomen`, `genitalia_groin_buttocks`, `back`, `extremity`.

The exam denominator is how many of these areas the transcript documents. The 1995 level uses that count: 1 problem focused, 2–5 expanded problem focused, 6–7 detailed, 8 or more comprehensive. These seven areas cannot reach 8 by themselves.

## Assessment and plan

Assessment and plan are one section, `assessment_and_plan`. Each problem is one object. A second problem is the next object in `problems`, with the next id (`problem_002`).

The object matches this shape. Plan actions sit under that same problem, not in a second list.

```json
{
  "assessment_and_plan": {
    "problems": [
      {
        "id": "problem_001",
        "diagnosis_or_clinical_impression": { "claims": [] },
        "assessment": { "claims": [] },
        "differential_diagnoses": { "claims": [] },
        "plan": {
          "medications": [
            {
              "name": { "claims": [] },
              "dose": { "claims": [] },
              "route": { "claims": [] },
              "frequency": { "claims": [] },
              "duration": { "claims": [] }
            }
          ],
          "other_treatments": { "claims": [] },
          "planned_investigations": { "claims": [] },
          "education_and_counseling": { "claims": [] },
          "referrals": { "claims": [] },
          "follow_up": { "claims": [] }
        }
      }
    ]
  }
}
```

A problem counts a feature only when the clinician stated it. `differential_diagnoses` stays empty when no differential was stated. A medication field stays empty when that part was not stated: a named drug with no dose opens `name` and leaves `dose`, `route`, `frequency`, and `duration` empty. Those empty fields are not in the denominator.

The section's task rule is the Assessment & Plan instruction: state the diagnosis the clinician said, one assessment paragraph, a differential only if stated, and plan bullets only for treatments, doses, investigations, counseling, referrals, and follow-up that were stated.

## Metrics

Six rates. A claim is one assertion. A note claim is supported when the voice transcript states that same fact. It is unsupported when it is not accurate against the transcript. Every claim in the raw clinical note is one or the other, so correctness and fabrication rate share one denominator and add to 1.

| Metric | Ratio | Direction |
| --- | --- | --- |
| `fabrication_rate` | Note claims that are not accurate against the voice transcript, divided by the claims in the raw clinical note | Lower is better |
| `correctness` | Note claims supported by the voice transcript, divided by the claims in the raw clinical note (supported plus unsupported) | Higher is better |
| `completeness` | Dictation claims that are represented in the raw clinical note, divided by the claims in the dictation | Higher is better |
| `fluency` | Note claims whose text is readable clinical prose, divided by the claims in the raw clinical note | Higher is better |
| `coherence` | Note claims that stay in section order, divided by the claims in the raw clinical note | Higher is better |
| `preference_adherence` | Note claims that follow that section's task rule, divided by the claims in the raw clinical note | Higher is better |

`numerator` is the top of that ratio. `denominator` is the bottom. `rate` is numerator divided by denominator. A denominator of 0 leaves `rate` null.

A missing dictation claim lowers completeness. It does not, by itself, change the other five, because those count only claims the note wrote. An unsupported note claim lowers correctness and raises fabrication rate. It does not raise completeness.

Fluency fails when a claim is broken or still contains template instructions. A short clinical fragment is readable. Coherence fails when a claim is out of order: history, then exam and studies, then assessment and plan. A plan written as history fails. A patient-reported fact written as a measurement fails.

Preference adherence uses the section's task rule. On `case_description`, `hpi`, `pmh`, `family_history`, and `social_history`, a bullet with more than one sentence fails when that one-sentence rule is active. Those misses stay in the history section that owns the claim. On `assessment_and_plan`, a claim fails when it breaks the Assessment & Plan instruction above. Exam, review of systems, and labs have no extra task rule, so their written claims pass preference adherence.

```json
{
  "clinical_note": {
    "case_description": {
      "chief_concern": {
        "claims": [
          {
            "text": "Follow-up call regarding the blood test.",
            "evidence": [
              {
                "file": "internal/note-0001-transcript.txt",
                "line_start": 5,
                "line_end": 5,
                "quote": "clinician_4: Perfect. Okay. Um, it was just a follow-up call, um, regarding the blood test that we had done for you. Um- "
              }
            ]
          }
        ]
      }
    },
    "hpi": {
      "location": { "claims": [] },
      "quality": { "claims": [] },
      "severity": { "claims": [] },
      "duration": { "claims": [] },
      "timing": { "claims": [] },
      "context": { "claims": [] },
      "modifying_factors": { "claims": [] },
      "associated_signs_and_symptoms": { "claims": [] }
    },
    "pmh": {},
    "family_history": {},
    "social_history": {},
    "review_of_systems": {
      "cardiovascular": { "claims": [] },
      "ears_nose_mouth_throat": { "claims": [] },
      "eyes": { "claims": [] },
      "genitourinary_female": { "claims": [] },
      "genitourinary_male": { "claims": [] },
      "hematologic_lymphatic_immunologic": { "claims": [] },
      "musculoskeletal": { "claims": [] },
      "neurologic": { "claims": [] },
      "psychiatric": { "claims": [] },
      "respiratory": { "claims": [] },
      "skin": { "claims": [] }
    },
    "physical_exam": {
      "body_areas": {
        "head": { "claims": [] },
        "neck": { "claims": [] },
        "chest": { "claims": [] },
        "abdomen": { "claims": [] },
        "genitalia_groin_buttocks": { "claims": [] },
        "back": { "claims": [] },
        "extremity": { "claims": [] }
      }
    },
    "labs_studies_imaging": { "claims": [] },
    "assessment_and_plan": {
      "problems": [
        {
          "id": "problem_001",
          "diagnosis_or_clinical_impression": {
            "claims": [
              {
                "text": "Raised white blood cells, likely from recent infection.",
                "evidence": [
                  {
                    "file": "internal/note-0001-transcript.txt",
                    "line_start": 39,
                    "line_end": 39,
                    "quote": "clinician_38: Yeah. It sounds like you may have picked up a virus and, um, your hematology panel shows a raised white blood cells. Now, white blood cells are involved in fighting infection, so that can be, I think it's- "
                  },
                  {
                    "file": "internal/note-0001-transcript.txt",
                    "line_start": 47,
                    "line_end": 47,
                    "quote": "clinician_46: ... I, I, I think it is likely due to, um, the infection you were having. I would like to repeat it just to make sure though. "
                  }
                ]
              }
            ]
          },
          "assessment": {
            "claims": [
              {
                "text": "The count is higher than the prior normal result and fits the recent infection, so it should be repeated.",
                "evidence": [
                  {
                    "file": "internal/note-0001-transcript.txt",
                    "line_start": 47,
                    "line_end": 47,
                    "quote": "clinician_46: ... I, I, I think it is likely due to, um, the infection you were having. I would like to repeat it just to make sure though. "
                  }
                ]
              }
            ]
          },
          "differential_diagnoses": { "claims": [] },
          "plan": {
            "medications": [],
            "other_treatments": { "claims": [] },
            "planned_investigations": {
              "claims": [
                {
                  "text": "Repeat the white blood cell count.",
                  "evidence": [
                    {
                      "file": "internal/note-0001-transcript.txt",
                      "line_start": 47,
                      "line_end": 47,
                      "quote": "clinician_46: ... I, I, I think it is likely due to, um, the infection you were having. I would like to repeat it just to make sure though. "
                    }
                  ]
                }
              ]
            },
            "education_and_counseling": { "claims": [] },
            "referrals": { "claims": [] },
            "follow_up": { "claims": [] }
          }
        }
      ]
    }
  },
  "evaluation": {
    "field_results": [],
    "capacity": {
      "sections": {
        "case_description": { "count": 0, "fields": [] },
        "hpi": { "count": 0, "fields": [] },
        "pmh": { "count": 0, "fields": [] },
        "family_history": { "count": 0, "fields": [] },
        "social_history": { "count": 0, "fields": [] },
        "review_of_systems": { "count": 0, "fields": [] },
        "physical_exam": { "count": 0, "fields": [] },
        "labs_studies_imaging": { "count": 0, "fields": [] },
        "assessment_and_plan": { "count": 0, "fields": [] }
      }
    },
    "metrics": [
      {
        "name": "fabrication_rate",
        "numerator": 0,
        "denominator": 0,
        "rate": null,
        "direction": "lower"
      },
      {
        "name": "correctness",
        "numerator": 0,
        "denominator": 0,
        "rate": null,
        "direction": "higher"
      },
      {
        "name": "completeness",
        "numerator": 0,
        "denominator": 0,
        "rate": null,
        "direction": "higher"
      },
      {
        "name": "fluency",
        "numerator": 0,
        "denominator": 0,
        "rate": null,
        "direction": "higher"
      },
      {
        "name": "coherence",
        "numerator": 0,
        "denominator": 0,
        "rate": null,
        "direction": "higher"
      },
      {
        "name": "preference_adherence",
        "numerator": 0,
        "denominator": 0,
        "rate": null,
        "direction": "higher"
      }
    ],
    "metrics_by_section": [
      {
        "section": "assessment_and_plan",
        "name": "completeness",
        "numerator": 0,
        "denominator": 0,
        "rate": null,
        "direction": "higher"
      }
    ]
  }
}
```

`metrics` is the whole note. `metrics_by_section` repeats the same six names once per major section. Fabrication rate, correctness, fluency, coherence, and preference adherence in a section use that section's note claims. Completeness in a section uses that section's dictation claims. To check a claim, open its `evidence.file` and read `line_start` through `line_end`. The quote on the claim is those lines.
