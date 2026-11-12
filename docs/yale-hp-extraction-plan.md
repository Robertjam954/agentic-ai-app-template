---
cursor:
  subagentId: "bc-536bbaf5-1274-574a-a879-52db67fe381d"
---

---
title: Yale H&P hierarchical note extraction
version: 0.1
date_created: 2026-11-04
last_updated: 2026-11-04
owner: Robert
framework: FastAPI + Anthropic, Instructor field validation
---

# Implementation Plan: Yale H&P hierarchical note extraction

Each extracted note becomes one hierarchical JSON object. The ten top-level keys follow the Yale History & Physical plus Assessment & Plan template. Identification is renamed `case_description`. Subcomponents are the features to extract and validate. The allowed values are the ones written in that template. A later pass over the 500-case set may add values; this plan does not invent them.

The current extractor in `backend/app/evals/em.py` still uses history, exam, and medical decision making. This plan replaces that shape. No extractor code changes in this step.

Success looks like this: a note that follows the Yale template validates against the hierarchy below; a blank feature fails; a value on the seed list passes; a non-empty value that is not on the list yet is kept and marked as an extension instead of being dropped; review-of-systems screening does not land in the HPI; the plan's problems are the same problems as the assessment.

## Requirements

**Functional**

- Emit one JSON object per note with these top-level keys, in this order: `case_description`, `hpi`, `pmh`, `family_history`, `social_history`, `review_of_systems`, `physical_exam`, `labs_studies_imaging`, `assessment_and_plan`.
- Extract every feature listed under those keys. Validate it with Instructor field validators (Pydantic `Field`, `field_validator`, `model_validator`), the same pattern already used for the chief complaint and HPI.
- Seed allowed values from the Yale template only.
- Keep a value that is not on the seed list when the text is non-empty. Mark it `vocabulary: "extension"`. Do not fail the note for that. The 500-case pass is what grows the lists.
- Treat a blank, a bare number where a statement is required, or a missing required feature as a validation failure.
- Keep ROS out of the HPI. Pertinent positives and negatives in the HPI are targeted. The ROS is the organ-system survey.
- Score ROS type from the systems that are individually documented: problem pertinent (1), extended (2–9), complete (10 or more, or a notation that all other systems are negative). Nine systems without that notation is not complete.
- Organize the physical exam by body area. Record the 1995 level from how many body areas are documented.
- Make `assessment_and_plan` problem-based. Each problem holds its diagnosis, assessment, differential, and plan together. The shape is in `docs/clinical-note-eval-shape.md`.

**Non-functional**

- Offline tests do not call Anthropic or OpenAI.
- Note text and the 500-case files stay out of git. They contain clinical text.
- No new API key. `.env` is not part of this work.
- The first implementation slice is the schema and the validators. A live model fill of a real note is a later task.

## Component coverage matrix

**Every row must be answered.** Decision is one of **Build** / **Reuse** / **N/A**.

| # | Component | Decision | Notes / where it lives / N/A reason |
|---|-----------|----------|--------------------------------------|
| 1 | Infra & databases (DB, migrations, container, config, secrets) | Reuse | The note is a JSON object on the existing eval payload. No new table and no vector store. Postgres, FastAPI, and `.env` stay as they are. |
| 2 | Agents (single vs. supervisor + workers; routing) | Build | One extractor role, not a supervisor. It fills this hierarchy and stops. Host it in the existing backend. The deterministic structurer remains the offline path. |
| 3 | Tools (registry; per-agent subsets; external APIs) | N/A | This slice validates a document. It does not call an external API or register a new tool. |
| 4 | Memory (multi-turn history; long-term / retrieval) | N/A | One note is one document. Nothing is carried across notes. |
| 5 | Prompts (per-role registry; versioning) | Build | One extraction prompt per top-level key, so the HPI prompt cannot ask for a review of systems. Version them in git next to the schema. |
| 6 | Frontend components (chat/agent surface) | Reuse | No new page. `/results` stays on the current field-capacity board until a note has been extracted into this shape. |
| 7 | Tracing / observability / eval | Build | The validator report is the trace: feature path, pass or fail, and whether a value was listed or an extension. Reuse the eval runner for the fixture. No live judge in this slice. |
| — | Auth & secrets | Reuse | No new secret. Do not commit `.env` or note text. |
| — | Deployment / hosting | N/A | The schema ships inside the existing backend image. No new service. |
| — | Testing | Build | One validator test per top-level key, plus the ROS count rule, the body-area exam count, and the rule that plan problems match assessment problems. |
| — | Code review (claude-review.yml) | Reuse | The existing PR review workflow covers the implementation PR. This plan file is not that PR. |

## Architecture and design

The hierarchy is the product. Feature objects share one shape so a later vocabulary pass can walk every leaf the same way.

```json
{
  "value": null,
  "status": "not_documented",
  "vocabulary": "listed"
}
```

`status` is `present`, `absent`, or `not_documented`. `vocabulary` is `listed` when `value` is on the seed list, and `extension` when it is not. Multi-value features use `findings` instead of a single `value`. Allowed lists live on the model, not copied onto every note.

`case_description.chief_concern` is a feature of the case, not an eleventh key. The Yale chief concern is the full sentence (name, age, the word man or woman, relevant background, presenting problem). Past history stays in `pmh`.

The last key is `assessment_and_plan`. Each problem is one object: diagnosis, assessment paragraph, differential only when stated, and the plan for that same problem. There is no second problem list.

### 1. `case_description`

Renamed from identification.

| Feature | Seed values | Validation |
| --- | --- | --- |
| `date_time` | free text | Non-empty when present |
| `setting` | `ed`, `inpatient_admit`, `consult`, `clinic`, `observation` | One of the list, or an extension |
| `age` | years | Number when present |
| `gender_word` | `man`, `woman` | Yale wording. Extension allowed for later cases |
| `location_bed` | free text | |
| `code_status` | free text | |
| `historian` | `patient`, `family`, `records`, `other` | Required feature. Family and other may name the person in `historian_detail` |
| `historian_detail` | free text | Required when historian is `family` or `other` |
| `reliability` | `reliable`, `limited` | Required feature |
| `reliability_reason` | free text | Required when reliability is `limited` |
| `records_reviewed` | `epic_media`, `care_everywhere`, `prior_notes`, `pfts_imaging` | Any of these |
| `records_detail` | free text | Used when imaging or other records are named |
| `chief_concern` | full sentence | Must contain letters. Must not be a bare symptom label |

### 2. `hpi`

Chronological. The eight elements are required features. Pertinent positives and negatives stay here and are targeted. ED course and prior hospital course are present only when the note has them.

| Feature | Seed values | Validation |
| --- | --- | --- |
| `usual_state_until` | free text | The timeline anchor |
| `location.site` | free text | Where the problem is |
| `location.radiation` | free text | |
| `quality` | `sharp`, `dull`, `crampy`, `burning` | The template's "etc." is why other words are extensions, not failures |
| `severity.score` | `0` through `10` | Integer on that scale when a score is written |
| `severity.functional_impact` | free text | |
| `duration` | length of time | Must name a length of time (minute, hour, day, week, month, year) |
| `timing.onset` | free text | |
| `timing.frequency` | free text | |
| `timing.pattern` | `persistent`, `intermittent` | |
| `timing.when` | free text | |
| `context` | events, exposures, triggers | Free text |
| `modifying_factors.effect` | `relieves`, `worsens`, `no_effect` | At least one when the feature is present |
| `modifying_factors.factor` | `meds`, `rest`, `position`, `food` | Extension allowed |
| `associated_signs_and_symptoms` | free-text findings | |
| `pertinent_positives` | free-text findings | Targeted. Not a system survey |
| `pertinent_negatives` | free-text findings | Targeted. Not a system survey |
| `ed_course.fever_vitals` | free text | |
| `ed_course.studies` | free text | CXR or labs named in the ED course |
| `ed_course.treatment` | `antibiotics`, `fluids` | Extension allowed |
| `ed_course.response` | free text | |
| `prior_hospital_course.ventilator_days` | free text | |
| `prior_hospital_course.antibiotics` | free text | |
| `prior_hospital_course.procedures` | free text | |
| `prior_hospital_course.extubated` | free text | |
| `prior_hospital_course.transferred` | free text | |

### 3. `pmh`

Past history from the template's PMH section and the short "Past History Details" block live here. They are one history, not two keys.

| Feature | Seed values | Validation |
| --- | --- | --- |
| `medical` | free-text conditions | |
| `surgical` | free-text procedures | |
| `hospitalizations` | free text | |
| `past_history` | illnesses, injuries, treatments | The Yale PFSH past-history line |
| `immunizations.status` | `up_to_date` | |
| `immunizations.products` | `flu`, `covid`, `pneumococcal`, `other` | |
| `allergies.agent` | free text | |
| `allergies.reaction` | free text | Required when an agent is present |
| `medications` | reconciled list | Each item is a non-empty string |
| `baseline_comparisons` | analyte, today, prior | For a new abnormal test. Example shape: creatinine today versus yesterday. The numbers must be in the note |

### 4. `family_history`

| Feature | Seed values | Validation |
| --- | --- | --- |
| `conditions` | free text | |
| `hereditary` | free text | Present when the hereditary box is used |
| `relatives` | `parent`, `sibling` | Each relative may carry `age_or_cause_of_death` |

### 5. `social_history`

| Feature | Seed values | Validation |
| --- | --- | --- |
| `occupation` | free text | |
| `living_situation` | free text | |
| `humanizing_detail` | free text | One human detail when the note includes one |
| `tobacco` | free text | |
| `alcohol` | free text | |
| `substances` | free text | |
| `diet` | free text | |
| `exercise` | free text | |
| `sexual_history` | free text | Only when the note marks it relevant |
| `safety` | free text | |
| `adls` | free text | |
| `support` | free text | |
| `travel` | free text | |
| `exposures` | free text | |
| `pets` | free text | |

### 6. `review_of_systems`

Organ-system survey. Extended is 2–9 systems. Complete is 10 or more systems individually documented, or fewer systems plus a notation that all other systems are negative. Problem pertinent (1 system) stays in the type list because the template includes it.

Each system:

```json
{
  "status": "positive",
  "findings": ["fever"]
}
```

`status` is `positive`, `negative`, or `not_asked`. A finding must be on that system's seed list or marked as an extension. `not_asked` does not count toward the type.

| System | Seed findings |
| --- | --- |
| `constitutional` | `fever`, `chills`, `weight_loss`, `weight_gain`, `fatigue` |
| `eyes` | `vision_change`, `pain`, `discharge` |
| `ears_nose_mouth_throat` | `hearing`, `congestion`, `sore_throat`, `dental` |
| `cardiovascular` | `chest_pain`, `palpitations`, `edema`, `claudication` |
| `respiratory` | `cough`, `shortness_of_breath`, `wheeze`, `sputum` |
| `gastrointestinal` | `nausea`, `vomiting`, `diarrhea`, `constipation`, `blood`, `abdominal_pain` |
| `genitourinary` | `dysuria`, `frequency`, `hematuria`, `discharge`, `incontinence` |
| `musculoskeletal` | `joint_pain`, `swelling`, `muscle_pain`, `stiffness` |
| `integumentary_breast` | `rash`, `lesion`, `breast_lump`, `breast_pain` |
| `neurologic` | `headache`, `dizziness`, `weakness`, `numbness`, `seizure`, `syncope` |
| `psychiatric` | `depression`, `anxiety`, `sleep`, `memory`, `suicidal_ideation`, `homicidal_ideation` |
| `endocrine` | `polyuria`, `polydipsia`, `heat_intolerance`, `cold_intolerance`, `thyroid` |
| `hematologic_lymphatic` | `bruising`, `bleeding`, `lymphadenopathy` |
| `allergic_immunologic` | `allergies`, `recurrent_infections` |

Also:

| Feature | Seed values | Validation |
| --- | --- | --- |
| `type` | `problem_pertinent`, `extended`, `complete` | Derived from the documented systems. A stored type that disagrees with the count fails |
| `all_other_systems_negative` | `true`, `false` | When true, the type may be `complete` even if fewer than 10 systems are written out |
| `physician_confirmation` | free text | Required when a staff member or a patient form recorded the ROS |

### 7. `physical_exam`

Body-based. The seven areas are the 1995 body areas. Findings the template asks to elaborate sit under the area they belong to. Vitals and general appearance sit beside the areas because they are not a body area. Neurologic and psychiatric sit beside the areas for the same reason: the template asks for them, and mood does not belong to one area. Cranial-nerve findings go under `head`. Limb strength goes under `extremities`.

1995 level from the count of documented body areas: 1 problem focused, 2–5 expanded problem focused, 6–7 detailed, 8 or more comprehensive. There are seven areas, so comprehensive also covers a complete single-organ exam, which is the 1995 comprehensive alternative. The 2–7 band is the ambiguous carrier range; the split above is the one the template prints. 1997 is left null. The template names 1997 thresholds and does not list the bullets.

| Feature | What is extracted |
| --- | --- |
| `vitals` | `temperature`, `heart_rate`, `blood_pressure`, `respiratory_rate`, `spo2`, `pain`, `weight`, `height`, `bmi` |
| `general.appearance` | `nad`, `ill_appearing` |
| `general.humanizing_observation` | free text |
| `body_areas.head` | `face`; `eyes`; `ears`; `nose`; `mouth`; `throat`; `cranial_nerves` |
| `body_areas.neck` | `lymph_nodes` with `site`, `count`, `mobility` (`mobile`, `fixed`), `size`, `tenderness`, `consistency` (`firm`, `rubbery`, `hard`, `matted`) |
| `body_areas.chest` | `breasts`, `axillae`, `lungs` (`wheeze`, `crackles`, `work_of_breathing`), `cardiovascular` (`murmur`, `jvp`, `edema`, `pulses`) |
| `body_areas.abdomen` | `tenderness`, `guarding`, `masses`, `bowel_sounds` |
| `body_areas.genitalia_groin_buttocks` | free text, as indicated |
| `body_areas.back` | `spine` |
| `body_areas.extremities` | each limb: `edema`, `pulses`, `strength` |
| `neurologic` | `alert`, `oriented`, `motor`, `sensory` |
| `psychiatric` | `mood`, `affect`, `thought` |
| `level_1995` | `problem_focused`, `expanded_problem_focused`, `detailed`, `comprehensive` |
| `level_1997` | null in this slice |
| `chaperone` | free text for a sensitive exam |

### 8. `labs_studies_imaging`

Every study that has a result also has a comparison slot. The comparison is `new`, `unchanged`, or `changed`, plus the prior value when the note gives one.

| Feature | Seed studies |
| --- | --- |
| `labs` | `cbc`, `bmp`, `lfts`, `troponin`, `bnp`, `abg`, `ua`, `cultures` |
| `ecg` | free text, with comparison |
| `imaging` | `cxr`, `ct`, `ultrasound`, `echo`, each with comparison |
| `microbiology` | `blood`, `sputum`, `urine` |
| `other` | `pfts`, plus studies found in media or Care Everywhere |

A lab leaf is `{ "name", "value", "comparison": { "relation": "new|unchanged|changed", "prior": null } }`.

### 9. `assessment_and_plan`

One object per problem. The plan is nested on that problem. A second problem is the next object, `problem_002`.

| Feature | What is extracted |
| --- | --- |
| `problems[].id` | `problem_001`, then `problem_002` |
| `problems[].diagnosis_or_clinical_impression` | The diagnosis or impression the clinician stated |
| `problems[].assessment` | One paragraph of that assessment |
| `problems[].differential_diagnoses` | Only when a differential was stated |
| `problems[].plan.medications[]` | `name`, `dose`, `route`, `frequency`, `duration`, each only when stated |
| `problems[].plan.other_treatments` | Treatments that are not medications |
| `problems[].plan.planned_investigations` | Investigations the clinician said to do |
| `problems[].plan.education_and_counseling` | Counseling the clinician discussed |
| `problems[].plan.referrals` | Referrals the clinician stated |
| `problems[].plan.follow_up` | Follow-up the clinician stated |

Each filled claim cites the transcript file and line numbers. The field list and the citation shape are in `docs/clinical-note-eval-shape.md`.

### Skeleton

```json
{
  "case_description": {
    "date_time": { "value": null, "status": "not_documented", "vocabulary": "listed" },
    "setting": { "value": null, "status": "not_documented", "vocabulary": "listed" },
    "age": { "value": null, "status": "not_documented", "vocabulary": "listed" },
    "gender_word": { "value": null, "status": "not_documented", "vocabulary": "listed" },
    "location_bed": { "value": null, "status": "not_documented", "vocabulary": "listed" },
    "code_status": { "value": null, "status": "not_documented", "vocabulary": "listed" },
    "historian": { "value": null, "status": "not_documented", "vocabulary": "listed" },
    "historian_detail": { "value": null, "status": "not_documented", "vocabulary": "listed" },
    "reliability": { "value": null, "status": "not_documented", "vocabulary": "listed" },
    "reliability_reason": { "value": null, "status": "not_documented", "vocabulary": "listed" },
    "records_reviewed": [],
    "chief_concern": { "value": null, "status": "not_documented", "vocabulary": "listed" }
  },
  "hpi": {
    "usual_state_until": { "value": null, "status": "not_documented", "vocabulary": "listed" },
    "location": {
      "site": { "value": null, "status": "not_documented", "vocabulary": "listed" },
      "radiation": { "value": null, "status": "not_documented", "vocabulary": "listed" }
    },
    "quality": { "value": null, "status": "not_documented", "vocabulary": "listed" },
    "severity": {
      "score": { "value": null, "status": "not_documented", "vocabulary": "listed" },
      "functional_impact": { "value": null, "status": "not_documented", "vocabulary": "listed" }
    },
    "duration": { "value": null, "status": "not_documented", "vocabulary": "listed" },
    "timing": {
      "onset": { "value": null, "status": "not_documented", "vocabulary": "listed" },
      "frequency": { "value": null, "status": "not_documented", "vocabulary": "listed" },
      "pattern": { "value": null, "status": "not_documented", "vocabulary": "listed" },
      "when": { "value": null, "status": "not_documented", "vocabulary": "listed" }
    },
    "context": { "value": null, "status": "not_documented", "vocabulary": "listed" },
    "modifying_factors": {
      "effect": { "value": null, "status": "not_documented", "vocabulary": "listed" },
      "factor": { "value": null, "status": "not_documented", "vocabulary": "listed" }
    },
    "associated_signs_and_symptoms": [],
    "pertinent_positives": [],
    "pertinent_negatives": [],
    "ed_course": null,
    "prior_hospital_course": null
  },
  "pmh": {
    "medical": [],
    "surgical": [],
    "hospitalizations": [],
    "past_history": [],
    "immunizations": { "status": null, "products": [] },
    "allergies": [],
    "medications": [],
    "baseline_comparisons": []
  },
  "family_history": { "conditions": [], "hereditary": [], "relatives": [] },
  "social_history": {
    "occupation": { "value": null, "status": "not_documented", "vocabulary": "listed" },
    "living_situation": { "value": null, "status": "not_documented", "vocabulary": "listed" },
    "humanizing_detail": { "value": null, "status": "not_documented", "vocabulary": "listed" },
    "tobacco": { "value": null, "status": "not_documented", "vocabulary": "listed" },
    "alcohol": { "value": null, "status": "not_documented", "vocabulary": "listed" },
    "substances": { "value": null, "status": "not_documented", "vocabulary": "listed" },
    "diet": { "value": null, "status": "not_documented", "vocabulary": "listed" },
    "exercise": { "value": null, "status": "not_documented", "vocabulary": "listed" },
    "sexual_history": { "value": null, "status": "not_documented", "vocabulary": "listed" },
    "safety": { "value": null, "status": "not_documented", "vocabulary": "listed" },
    "adls": { "value": null, "status": "not_documented", "vocabulary": "listed" },
    "support": { "value": null, "status": "not_documented", "vocabulary": "listed" },
    "travel": { "value": null, "status": "not_documented", "vocabulary": "listed" },
    "exposures": { "value": null, "status": "not_documented", "vocabulary": "listed" },
    "pets": { "value": null, "status": "not_documented", "vocabulary": "listed" }
  },
  "review_of_systems": {
    "type": null,
    "all_other_systems_negative": false,
    "physician_confirmation": null,
    "systems": {}
  },
  "physical_exam": {
    "vitals": {},
    "general": {},
    "body_areas": {
      "head": {},
      "neck": {},
      "chest": {},
      "abdomen": {},
      "genitalia_groin_buttocks": {},
      "back": {},
      "extremities": {}
    },
    "neurologic": {},
    "psychiatric": {},
    "level_1995": null,
    "level_1997": null,
    "chaperone": null
  },
  "labs_studies_imaging": {
    "labs": [],
    "ecg": null,
    "imaging": [],
    "microbiology": [],
    "other": []
  },
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

`review_of_systems.systems` is filled with the 14 system keys from the table above. Empty `{}` in the skeleton means "the key is required; the note has not filled it."

### Where this sits in the current app

- New module later: `backend/app/evals/yale_hp.py` for the models, the seed lists, and `validate_note`. `em.py` stays until a note is actually cut over, so the current `/results` rates do not move in this step.
- Prompts later: `backend/app/evals/yale_hp_prompts.py`, one prompt per key.
- Vocabulary file later: a JSON list per feature path, seeded from this plan, appended only when a 500-case value is accepted.
- Rejected: folding family history and social history back into one PFSH object. The template, and this request, make them their own keys. Rejected: scoring the exam by organ system. The request asks for body areas. Rejected: failing the note when a real finding is not on the seed list. That would freeze the vocabulary before the 500 cases are read.

## Tasks

- [ ] Add `yale_hp.py` with the ten top-level models and the shared feature object — acceptance: `model_json_schema()` key order is the ten keys above
- [ ] Seed allowed values from the tables in this plan, and nowhere else
- [ ] Validate `case_description`: historian and reliability are required; `limited` requires a reason; `family` and `other` require `historian_detail`; chief concern is a full sentence
- [ ] Validate `hpi`: the eight elements, duration as a length of time, severity score only on 0–10, modifying factor is relieves, worsens, or no effect
- [ ] Validate `pmh`, `family_history`, and `social_history` against their tables, including allergy reaction when an agent is present
- [ ] Validate `review_of_systems`: 14 systems, status positive / negative / not asked, type derived from the count, nine systems without "all other systems negative" is not complete
- [ ] Validate `physical_exam`: seven body areas, 1995 level from the count, 1997 left null, lymph-node consistency on the seed list
- [ ] Validate `labs_studies_imaging`: named studies on the seed list, each result can carry a comparison
- [ ] Validate `assessment` and `plan` together: same problem ids, workup before treatment, problem status is active, chronic, or new
- [ ] Mark out-of-list non-empty values as `vocabulary: "extension"` and collect them. Do not drop them and do not fail the note
- [ ] Tests with a tiny fixture note. No live model call. No real note text in the test file
- [ ] Leave `em.py` and `/results` on the current rates until a cutover task says otherwise

## Test plan

- Local: import the models and validate a fixture object that fills one feature on every key. Expect success.
- Per section: one test that a listed value passes, one that a blank fails, one that an unknown non-empty value is kept as an extension.
- ROS: 3 documented systems validates as `extended`. 10 validates as `complete`. 9 without the all-other-systems notation fails a stored type of `complete`.
- Exam: one documented body area is problem focused. Five is expanded. The 1997 field is null.
- Assessment and plan: a plan id missing from the assessment fails. Workup entries are ordered before treatment entries.
- Edge cases: chief concern that is only "abdominal pain" fails the full-sentence check. HPI duration of "the pain is sharp" fails. Reliability `limited` with no reason fails. No API key is required for any of these tests.

## Open questions

1. The 500-case files are not in this workspace. Who accepts a new value onto the seed list, and is that a reviewed file or an automatic union?
2. Should the first implementation stay a validator over JSON the caller supplies, or should it also call the model to fill the ten sections?
3. Neurologic and psychiatric exam lines are not body areas. This plan keeps them beside the seven areas. Say if they should be forced under `head` and dropped as their own features.

## Out of scope

- A new database table, vector store, or service (matrix rows 1, 3, 4, and deployment).
- Reworking `/results` or rescoring note-0001 (frontend reuse). The current board stays on history 7, exam 0, medical decision making 4.
- Inventing 1997 exam bullets or a table-of-risk level. `level_1997` stays null.
- Loading the 500-case dataset. The seed lists stay the template lists until that dataset is available.
- Multi-turn agent memory.
