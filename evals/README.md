# Local eval runner

Run the agent loop against fixed cases from the command line. Scripted cases
use the real tools and a fake model, so they do not need `ANTHROPIC_API_KEY`,
Postgres, or Docker. Cases with no `script` call Claude only when you pass
`--live`.

The chat UI stays the chat UI. The Results page at `/results` draws the
shipped case scores. It does not need a login. Start the frontend, then open
<http://localhost:5173/results>.

## Install

From the repo root, with [uv](https://docs.astral.sh/uv/) installed. uv downloads
the Python version in `backend/pyproject.toml` (3.14). The repo already ships a
`.env`, which the app settings load when the command runs from `backend/`.

```bash
uv sync --directory backend
```

## Run

```bash
uv run --directory backend agent-eval --list
uv run --directory backend agent-eval
uv run --directory backend agent-eval --tag smoke
uv run --directory backend agent-eval word_count
uv run --directory backend agent-eval --json
```

The same commands work as `python -m app.evals` after `cd backend`. From the
repo root, `bun run eval` and `bun run eval:list` call the same runner.

| Exit | Meaning |
| --- | --- |
| 0 | At least one case ran, and every case that ran passed |
| 1 | A case failed, a case file failed to load, or `--strict` and something was skipped |
| 2 | No case matched, the eval directory is missing, or every selected case was skipped |

A failed case writes `evals/.results/<timestamp>/<case-id>.json` (prompt, tool
input/output, assertions). That directory is gitignored.

## Define a case

Put `*.eval.yaml`, `*.eval.yml`, or `*.eval.json` under `evals/`. The case id
is the path under `evals/` with the `.eval.*` suffix removed:

| File | `id` in the file | Case id |
| --- | --- | --- |
| `evals/word_count.eval.yaml` | omitted | `word_count` |
| `evals/word_count.eval.yaml` | `short` | `word_count/short` |
| `evals/live/word_count.eval.yaml` | omitted | `live/word_count` |
| `evals/tools.eval.yaml` with a `cases:` list and no ids | | `tools/0000`, `tools/0001`, … |

A file is one case, or a list of cases, or a mapping with `tags`, `description`,
and `cases`. Gates check the tool trajectory and the shape of the reply.

```yaml
description: Count words with the word_count tool.
tags: [smoke, tools]
prompt: |
  How many words are in the text below? Use the word_count tool.
  hello world
script:
  - tools:
      - name: word_count
        input:
          text: "hello world"
  - text: "There are 2 words."
expect:
  succeeded: true
  called_tools:
    - name: word_count
      input:
        text: "hello world"
      output_includes: "^2$"
  not_called_tools: [current_time]
  reply_includes: "2"
  max_tool_calls: 2
```

- `script` is the fake model, one turn per `messages.create` call. A turn with
  `tools` is a tool-use turn. The last turn should be text. Tool handlers are
  the real ones in `backend/app/agents/tools.py`.
- `called_tools` can be a name (`word_count`) or a mapping. `input` matches by
  equality on the keys you list. `output_includes` and `reply_includes` are
  regular expressions (`re.search`). `count` sets an exact number of matching
  calls; omit it to mean "at least one".
- `tool_order` is the exact list of tool names. `succeeded: true` fails when
  the loop hits the step cap.
- Optional `system_prompt` and `tool_names` are passed into the agent loop.
- `evals/evals.config.yaml` sets `max_concurrency` (default 4).

`word_count` matches `word_count` and `word_count/short`. It does not match
`word_count_extra`. Repeat `--tag` to keep cases that have any of those tags.
When both ids and tags are set, a case must match both.

## Point at another directory

`--dir` defaults to this repo's `evals/` folder, from the file path, not from
the shell's current directory.

```bash
uv run --directory backend agent-eval --dir /path/to/cases
```

## Clinical note

`--clinical-note` reads one saved note example (transcript plus generated SOAP note) and prints field scores. It does not call a model. The structured object is `source_document.text`, `clinical_note`, and `evaluation.field_results`.

Exit 0 when no written field is fabricated, unsupported, disfluent, incoherent, or off an active one-sentence-per-bullet preference. Exit 1 otherwise. `--write-json` saves the object. Each metric is a count out of the fields the transcript supports. That capacity is counted separately for the subjective, objective, and assessment sections. Higher is better, except fabrication, where lower is better. The history of present illness is the chief complaint: a patient statement plus location, quality, severity, duration, timing, context, modifying factors, and associated signs and symptoms. Instructor field validators check that shape. Those counts for the cases in this repo are on the Results page (`/results`).

```bash
uv run --directory backend agent-eval --clinical-note /path/to/note-0001.json
uv run --directory backend agent-eval --clinical-note /path/to/note-0001.json --write-json /path/to/note-0001-structured.json
```

## Live cases

Omit `script` to call the configured model. Those cases are skipped unless you
pass `--live`. They need `ANTHROPIC_API_KEY` in `.env`. `evals/live/word_count.eval.yaml`
is one example.

```bash
uv run --directory backend agent-eval --live --tag live
```

Gate the tool you meant to call, the tool you did not, and a shape check on the
reply. Do not pin the whole sentence.
