import { Link } from "@tanstack/react-router"
import { useEffect, useState } from "react"

import "./results-dashboard.css"

type Status = "fail" | "pass" | "skip"
type Tone = "up" | "down" | "mid"

type Step = {
  id: string
  label: string
  detail: string
  value: number
}

type EvidenceCell = {
  cls: "mut" | "pos" | "mid" | "wt"
  text: string
}

type EvidenceRow = {
  id: string
  label: string
  kind: string
  cells: EvidenceCell[]
}

type MetricChip = {
  name: string
  score: string
  cls: EvidenceCell["cls"]
}

type EquationTerm = {
  k: string
  v: string
  tone: Tone | "dim"
  op?: "+" | "−" | "="
}

type DashCase = {
  id: string
  sub: string
  status: Status
  headline: string
  suffix: string
  tier: string
  read: string
  baseline: number
  baselineLabel: string
  finalLabel: string
  steps: Step[]
  equation: EquationTerm[]
  meta: { k: string; v: string }[]
  side: { k: string; v: string }[]
  fallTitle: string
  legend: { label: string; tone: Tone }[]
  evidenceTitle: string
  evidenceSub: string
  evidenceHead: string[]
  evidence: EvidenceRow[]
  chips: MetricChip[]
  share: number
  flag: string
  distNote: string
  showFigures: boolean
}

const STATUS_COLOR: Record<Status, string> = {
  fail: "var(--up)",
  pass: "var(--down)",
  skip: "var(--mid)",
}

const NOTE_FIELDS: EvidenceRow[] = [
  row("chief_complaint", "Chief complaint", "history", "uncertain", "pass"),
  row(
    "hpi.associated_signs_and_symptoms",
    "HPI · associated signs",
    "history",
    "uncertain",
    "fail",
  ),
  row("hpi.duration", "HPI · duration", "history", "missing", "na"),
  row("hpi.quality", "HPI · quality", "history", "missing", "na"),
  row("hpi.timing", "HPI · timing", "history", "missing", "na"),
  row(
    "pfsh.past_history",
    "PFSH · past history",
    "history",
    "uncertain",
    "pass",
  ),
  row(
    "pfsh.social_history",
    "PFSH · social history",
    "history",
    "uncertain",
    "fail",
  ),
  row("data_reviewed", "Data reviewed", "MDM", "uncertain", "na"),
  row("hematology", "Hematology", "MDM", "uncertain", "na"),
  row("kidney", "Kidney", "MDM", "uncertain", "na"),
  row("potassium", "Potassium", "MDM", "uncertain", "na"),
]

const CASES: DashCase[] = [
  {
    id: "note-0001",
    sub: "SOAP note",
    status: "fail",
    headline: "9",
    suffix: "/11",
    tier: "fail · preference adherence",
    read: "Preference adherence is 9 of 11. Two history fields are multi-sentence bullets, so the case fails. Correctness is 8 of 11 (history 4/7, exam 0/0, medical decision making 4/4). History level is problem focused: chief complaint present, 2 HPI elements, no review of systems, and all 3 PFSH areas. The 1995 exam level is none. Medical decision making has 3 diagnoses and 5 data items; risk is not scored, so no type is assigned. Fabrication is 0 of 11. Fluency and coherence are 11 of 11.",
    baseline: 11,
    baselineLabel: "capacity",
    finalLabel: "preference",
    steps: [
      miss(
        "hpi.associated_signs_and_symptoms",
        "HPI · associated signs",
        "history · multi-sentence bullet",
      ),
      miss(
        "pfsh.social_history",
        "PFSH · social history",
        "history · multi-sentence bullet",
      ),
    ],
    equation: [
      { k: "Field capacity", v: "11", tone: "dim" },
      { k: "Preference misses", v: "2", tone: "up", op: "−" },
      { k: "Preference", v: "9", tone: "up", op: "=" },
    ],
    meta: [
      { k: "Case", v: "note-0001" },
      { k: "History level", v: "problem focused" },
      { k: "Exam (1995)", v: "none" },
      { k: "MDM risk", v: "not scored" },
    ],
    side: [
      { k: "Fields", v: "11" },
      { k: "Result", v: "fail" },
    ],
    fallTitle: "Why preference is 9 — field by field",
    legend: [{ label: "miss", tone: "up" }],
    evidenceTitle: "Field evidence",
    evidenceSub:
      "History is the chief complaint, eight HPI elements, 14 review-of-systems, and three PFSH areas. This panel is the 11 fields the transcript opened. Exam capacity is 0. Uncertain still counts as correct. A missing field lowers correctness and does not fail the run. Hover a miss to trace it on the waterfall.",
    evidenceHead: ["Correctness", "Fabrication", "Preference"],
    evidence: NOTE_FIELDS,
    chips: [
      { name: "Correctness", score: "8/11", cls: "pos" },
      { name: "Fabrication", score: "0/11", cls: "pos" },
      { name: "Fluency", score: "11/11", cls: "pos" },
      { name: "Coherence", score: "11/11", cls: "pos" },
      { name: "Preference", score: "9/11", cls: "mut" },
    ],
    share: 9 / 11,
    flag: "this case · 9/11",
    distNote:
      "Headline rate for note-0001 is preference adherence, 9 of 11. Fabrication is 0 of 11, and lower is better.",
    showFigures: true,
  },
  {
    id: "current_time",
    sub: "scripted · smoke",
    status: "pass",
    headline: "5",
    suffix: "/5",
    tier: "pass · scripted gates",
    read: "The scripted runner called current_time, left word_count unused, and the reply mentioned UTC. Every gate held.",
    baseline: 0,
    baselineLabel: "start",
    finalLabel: "gates",
    steps: [
      hold("succeeded", "Succeeded", "loop finished"),
      hold("called", "current_time", "called · output includes T"),
      hold("not_called", "word_count", "not called"),
      hold("reply", "Reply", "includes UTC"),
      hold("order", "Tool order", "current_time"),
    ],
    equation: [
      { k: "Start", v: "0", tone: "dim" },
      { k: "Gates held", v: "5", tone: "down", op: "+" },
      { k: "Result", v: "5", tone: "down", op: "=" },
    ],
    meta: [
      { k: "Case", v: "current_time" },
      { k: "Tags", v: "smoke · tools" },
      { k: "Mode", v: "scripted" },
      { k: "Model", v: "fake" },
    ],
    side: [
      { k: "Gates", v: "5" },
      { k: "Result", v: "pass" },
    ],
    fallTitle: "Why it passed — gate by gate",
    legend: [{ label: "holds", tone: "down" }],
    evidenceTitle: "Gate evidence",
    evidenceSub: "Checks from the scripted current_time case. No model call.",
    evidenceHead: [],
    evidence: [
      gate("succeeded", "Succeeded", "loop", "pass"),
      gate("called", "current_time", "tool", "pass"),
      gate("not_called", "word_count", "not called", "pass"),
      gate("reply", "Reply", "includes UTC", "pass"),
      gate("order", "Tool order", "current_time", "pass"),
    ],
    chips: [],
    share: 1,
    flag: "this case · 5/5",
    distNote:
      "All five gates held. This case does not use transcript field capacity.",
    showFigures: false,
  },
  {
    id: "word_count",
    sub: "scripted · smoke",
    status: "pass",
    headline: "5",
    suffix: "/5",
    tier: "pass · scripted gates",
    read: "The scripted runner counted “hello world” as 2, left current_time unused, and stayed inside the tool-call cap.",
    baseline: 0,
    baselineLabel: "start",
    finalLabel: "gates",
    steps: [
      hold("succeeded", "Succeeded", "loop finished"),
      hold("called", "word_count", "hello world · output 2"),
      hold("not_called", "current_time", "not called"),
      hold("reply", "Reply", "includes 2"),
      hold("max_calls", "Max calls", "at most 2"),
    ],
    equation: [
      { k: "Start", v: "0", tone: "dim" },
      { k: "Gates held", v: "5", tone: "down", op: "+" },
      { k: "Result", v: "5", tone: "down", op: "=" },
    ],
    meta: [
      { k: "Case", v: "word_count" },
      { k: "Tags", v: "smoke · tools" },
      { k: "Mode", v: "scripted" },
      { k: "Model", v: "fake" },
    ],
    side: [
      { k: "Gates", v: "5" },
      { k: "Result", v: "pass" },
    ],
    fallTitle: "Why it passed — gate by gate",
    legend: [{ label: "holds", tone: "down" }],
    evidenceTitle: "Gate evidence",
    evidenceSub: "Checks from the scripted word_count case. No model call.",
    evidenceHead: [],
    evidence: [
      gate("succeeded", "Succeeded", "loop", "pass"),
      gate("called", "word_count", "tool", "pass"),
      gate("not_called", "current_time", "not called", "pass"),
      gate("reply", "Reply", "includes 2", "pass"),
      gate("max_calls", "Max calls", "cap 2", "pass"),
    ],
    chips: [],
    share: 1,
    flag: "this case · 5/5",
    distNote:
      "All five gates held. This case does not use transcript field capacity.",
    showFigures: false,
  },
  {
    id: "live/word_count",
    sub: "live · skipped",
    status: "skip",
    headline: "Skip",
    suffix: "",
    tier: "skipped · needs --live",
    read: "This case has no scripted model turn. The default run skips it. Pass --live to call the model and count four words.",
    baseline: 0,
    baselineLabel: "start",
    finalLabel: "gates",
    steps: [],
    equation: [],
    meta: [
      { k: "Case", v: "live/word_count" },
      { k: "Tags", v: "live · tools" },
      { k: "Mode", v: "not run" },
      { k: "Model", v: "—" },
    ],
    side: [
      { k: "Gates", v: "5" },
      { k: "Result", v: "skipped" },
    ],
    fallTitle: "Not run",
    legend: [],
    evidenceTitle: "Gate evidence",
    evidenceSub: "Gates defined on the case. None of them ran.",
    evidenceHead: [],
    evidence: [
      gate("succeeded", "Succeeded", "loop", "na"),
      gate("called", "word_count", "output 4", "na"),
      gate("not_called", "current_time", "not called", "na"),
      gate("reply", "Reply", "includes 4", "na"),
      gate("max_calls", "Max calls", "cap 3", "na"),
    ],
    chips: [],
    share: 0.08,
    flag: "this case · skipped",
    distNote:
      "Skipped unless the runner is started with --live. That flag was not used.",
    showFigures: false,
  },
]

function miss(id: string, label: string, detail: string): Step {
  return { id, label, detail, value: -1 }
}

function hold(id: string, label: string, detail: string): Step {
  return { id, label, detail, value: 1 }
}

function row(
  id: string,
  label: string,
  section: string,
  correctness: "uncertain" | "missing",
  preference: "pass" | "fail" | "na",
): EvidenceRow {
  const correctnessCell: EvidenceCell =
    correctness === "missing"
      ? { cls: "mut", text: "missing" }
      : { cls: "mid", text: "uncertain" }
  const preferenceCell: EvidenceCell =
    preference === "fail"
      ? { cls: "mut", text: "fail" }
      : preference === "pass"
        ? { cls: "pos", text: "pass" }
        : { cls: "wt", text: "n/a" }
  return {
    id,
    label,
    kind: section,
    cells: [correctnessCell, { cls: "pos", text: "none" }, preferenceCell],
  }
}

function gate(
  id: string,
  label: string,
  kind: string,
  state: "pass" | "na",
): EvidenceRow {
  return {
    id,
    label,
    kind,
    cells: [
      state === "pass"
        ? { cls: "pos", text: "pass" }
        : { cls: "wt", text: "not run" },
    ],
  }
}

function finalOf(item: DashCase) {
  return item.baseline + item.steps.reduce((sum, step) => sum + step.value, 0)
}

function Sparkline({ item }: { item: DashCase }) {
  const w = 60
  const h = 18
  const color = STATUS_COLOR[item.status]
  if (item.steps.length === 0) {
    return (
      <svg
        width={w}
        height={h}
        viewBox={`0 0 ${w} ${h}`}
        fill="none"
        aria-hidden="true"
      >
        <line
          x1="0"
          y1={h / 2}
          x2={w}
          y2={h / 2}
          stroke={color}
          strokeDasharray="2 2"
        />
      </svg>
    )
  }
  let cursor = item.baseline
  const pts = [cursor]
  for (const step of item.steps) {
    cursor += step.value
    pts.push(cursor)
  }
  const lo = Math.min(...pts)
  const hi = Math.max(...pts)
  const span = hi - lo || 1
  const n = pts.length - 1
  const d = pts
    .map((value, index) => {
      const x = (index / n) * w
      const y = h - ((value - lo) / span) * (h - 2) - 1
      return `${index === 0 ? "M" : "L"}${x.toFixed(1)} ${y.toFixed(1)}`
    })
    .join(" ")
  return (
    <svg
      width={w}
      height={h}
      viewBox={`0 0 ${w} ${h}`}
      fill="none"
      aria-hidden="true"
    >
      <path
        d={d}
        stroke={color}
        strokeWidth="1.6"
        strokeLinejoin="round"
        strokeLinecap="round"
      />
    </svg>
  )
}

function toneColor(tone: Tone | "dim") {
  if (tone === "up") return "var(--up)"
  if (tone === "down") return "var(--down)"
  if (tone === "mid") return "var(--mid)"
  return "var(--text-dim)"
}

function Waterfall({
  item,
  lit,
  onLit,
}: {
  item: DashCase
  lit: string | null
  onLit: (id: string | null) => void
}) {
  if (item.steps.length === 0) {
    return (
      <p className="fall__empty">
        No score was produced. The runner skipped this case.
      </p>
    )
  }
  const base = item.baseline
  const fin = finalOf(item)
  let lo = Math.min(base, fin)
  let hi = Math.max(base, fin)
  item.steps.reduce((cursor, step) => {
    const next = cursor + step.value
    lo = Math.min(lo, cursor, next)
    hi = Math.max(hi, cursor, next)
    return next
  }, base)
  const pad = Math.max(0.55, (hi - lo) * 0.08)
  lo -= pad
  hi += pad
  const span = hi - lo || 1
  const xOf = (value: number) => ((value - lo) / span) * 100
  const line = item.steps.length * 40 + 6
  let cursor = base
  return (
    <div className="fall__plot">
      <div className="fall__axis">
        <div className="axtick is-marker" style={{ left: `${xOf(base)}%` }}>
          <div className="axtick__lab">
            {item.baselineLabel} {base}
          </div>
          <div className="axtick__line" style={{ height: line }} />
        </div>
        <div className="axtick is-marker" style={{ left: `${xOf(fin)}%` }}>
          <div className="axtick__lab">
            {item.finalLabel} {fin}
          </div>
          <div className="axtick__line" style={{ height: line }} />
        </div>
      </div>
      {item.steps.map((step, index) => {
        const start = cursor
        const end = cursor + step.value
        cursor = end
        const left = Math.min(start, end)
        const dir = step.value >= 0 ? "down" : "up"
        const origin = step.value >= 0 ? "left" : "right"
        return (
          <button
            type="button"
            className={lit === step.id ? "frow is-lit" : "frow"}
            key={step.id}
            onMouseEnter={() => onLit(step.id)}
            onMouseLeave={() => onLit(null)}
            onFocus={() => onLit(step.id)}
            onBlur={() => onLit(null)}
          >
            <div className="frow__label">
              <div className="frow__gene">{step.label}</div>
              <div className="frow__detail">{step.detail}</div>
            </div>
            <div className="frow__track">
              {index > 0 ? (
                <div
                  className="frow__conn"
                  style={{ left: `${xOf(start)}%` }}
                />
              ) : null}
              <div
                className={`frow__bar ${dir}`}
                style={{
                  left: `${xOf(left)}%`,
                  width: `${(Math.abs(step.value) / span) * 100}%`,
                  ["--origin" as string]: origin,
                }}
              />
            </div>
            <div className={`frow__val ${dir}`}>
              {step.value > 0 ? `+${step.value}` : step.value}
            </div>
          </button>
        )
      })}
    </div>
  )
}

function emphasized(text: string) {
  const parts = text.split(/(\d+ of \d+|\d+\/\d+)/g)
  return parts.map((part, index) =>
    /\d/.test(part) && (part.includes(" of ") || part.includes("/")) ? (
      <b key={`${part}-${index}`}>{part}</b>
    ) : (
      <span key={`${part}-${index}`}>{part}</span>
    ),
  )
}

export function ResultsDashboard() {
  const [selected, setSelected] = useState(0)
  const [lit, setLit] = useState<string | null>(null)
  const item = CASES[selected] ?? CASES[0]

  useEffect(() => {
    const caseId = CASES[selected]?.id
    const root = document.querySelector(".eval-dash")
    if (!root || !caseId) return
    const bars = root.querySelectorAll<HTMLElement>(".frow__bar")
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches
    if (reduce) return
    for (const bar of bars) bar.style.setProperty("--grow", "0")
    const timers: number[] = []
    const frame = requestAnimationFrame(() => {
      bars.forEach((bar, index) => {
        timers.push(
          window.setTimeout(
            () => bar.style.setProperty("--grow", "1"),
            40 * index,
          ),
        )
      })
    })
    return () => {
      cancelAnimationFrame(frame)
      for (const timer of timers) window.clearTimeout(timer)
    }
  }, [selected])

  return (
    <div className="eval-dash">
      <h1 className="sr-only">Clinical note eval results</h1>
      <div className="shell">
        <aside className="rail">
          <div className="brand">
            <span className="brand__mark">
              fie<b>l</b>d
            </span>
            <span className="brand__ver">v1 · field-capacity</span>
          </div>
          <p className="rail__caption">
            Clinical-note eval.
            <br />
            Rates out of the fields
            <br />
            the transcript supports.
          </p>
          <Link to="/" className="rail__back">
            App
          </Link>
          <div className="rail__label">
            <p className="eyebrow">Cases</p>
            <span className="rail__count">n={CASES.length}</span>
          </div>
          <ul className="plist" aria-label="Eval cases">
            {CASES.map((entry, index) => (
              <li key={entry.id}>
                <button
                  type="button"
                  className={index === selected ? "pcard is-active" : "pcard"}
                  aria-current={index === selected ? "true" : undefined}
                  onClick={() => {
                    setLit(null)
                    setSelected(index)
                  }}
                >
                  <span className="pcard__id">{entry.id}</span>
                  <span className="pcard__sub">{entry.sub}</span>
                  <span
                    className="pcard__risk"
                    style={{ color: STATUS_COLOR[entry.status] }}
                  >
                    {entry.headline}
                    {entry.suffix ? (
                      <span
                        style={{
                          fontSize: ".55em",
                          color: "var(--text-faint)",
                        }}
                      >
                        {entry.suffix}
                      </span>
                    ) : null}
                  </span>
                  <span className="pcard__spark">
                    <Sparkline item={entry} />
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </aside>

        <main className="main">
          <header className="topbar">
            <div>
              <p className="eyebrow" style={{ marginBottom: 8 }}>
                Field capacity · 4 Nov 2026
              </p>
              <div className="topbar__meta">
                {item.meta.map((meta) => (
                  <div key={meta.k}>
                    <div className="meta__k">{meta.k}</div>
                    <div className="meta__v">{meta.v}</div>
                  </div>
                ))}
              </div>
            </div>
            <div className="topbar__meta">
              {item.side.map((meta) => (
                <div key={meta.k}>
                  <div className="meta__k">{meta.k}</div>
                  <div
                    className="meta__v"
                    style={{
                      color: toneColor(
                        meta.v === "fail"
                          ? "up"
                          : meta.v === "pass"
                            ? "down"
                            : "dim",
                      ),
                    }}
                  >
                    {meta.v}
                  </div>
                </div>
              ))}
            </div>
          </header>

          <section className="hero">
            <div className="verdict">
              <div className="verdict__score" aria-live="polite">
                <span style={{ color: STATUS_COLOR[item.status] }}>
                  {item.headline}
                </span>
                {item.suffix ? (
                  <span className="verdict__pct">{item.suffix}</span>
                ) : null}
              </div>
              <p
                className="verdict__tier"
                style={{ color: STATUS_COLOR[item.status] }}
              >
                <span
                  className="tier-dot"
                  style={{ background: STATUS_COLOR[item.status] }}
                />
                {item.tier}
              </p>
              <p className="verdict__read">{emphasized(item.read)}</p>
              {item.equation.length > 0 ? (
                <div className="baseline-row">
                  {item.equation.map((term) => (
                    <span key={term.k} style={{ display: "contents" }}>
                      {term.op ? <div className="bl__op">{term.op}</div> : null}
                      <div className="bl">
                        <div className="bl__k">{term.k}</div>
                        <div
                          className="bl__v"
                          style={{ color: toneColor(term.tone) }}
                        >
                          {term.v}
                        </div>
                      </div>
                    </span>
                  ))}
                </div>
              ) : null}
            </div>

            <div className="fall">
              <div className="fall__head">
                <p className="fall__title">{item.fallTitle}</p>
                <div className="fall__legend">
                  {item.legend.map((entry) => (
                    <span className="lg" key={entry.label}>
                      <span
                        className="lg__sw"
                        style={{ background: toneColor(entry.tone) }}
                      />
                      {entry.label}
                    </span>
                  ))}
                </div>
              </div>
              <Waterfall item={item} lit={lit} onLit={setLit} />
            </div>
          </section>

          <section className="grid2">
            <div className="panel">
              <div className="panel__head">
                <p className="panel__title">{item.evidenceTitle}</p>
              </div>
              <p className="panel__sub">{item.evidenceSub}</p>
              {item.chips.length > 0 ? (
                <div className="mchips">
                  {item.chips.map((chip) => (
                    <div className="mchip" key={chip.name}>
                      <span className="mchip__k">{chip.name}</span>
                      <span className={`cell ${chip.cls}`}>{chip.score}</span>
                    </div>
                  ))}
                </div>
              ) : null}
              <div className="onco">
                {item.evidenceHead.length > 0 ? (
                  <div className="orow orow--head" aria-hidden="true">
                    <div />
                    <div className="orow__cells">
                      {item.evidenceHead.map((label) => (
                        <span key={label}>{label}</span>
                      ))}
                    </div>
                  </div>
                ) : null}
                {item.evidence.map((evidence) => (
                  <button
                    type="button"
                    className={lit === evidence.id ? "orow is-lit" : "orow"}
                    key={evidence.id}
                    onMouseEnter={() => setLit(evidence.id)}
                    onMouseLeave={() => setLit(null)}
                    onFocus={() => setLit(evidence.id)}
                    onBlur={() => setLit(null)}
                  >
                    <div className="orow__gene">
                      {evidence.label}
                      <small>{evidence.kind}</small>
                    </div>
                    <div className="orow__cells">
                      {evidence.cells.map((cell) => (
                        <span
                          className={`cell ${cell.cls}`}
                          key={`${evidence.id}-${cell.text}`}
                        >
                          {cell.text}
                        </span>
                      ))}
                    </div>
                  </button>
                ))}
              </div>
            </div>

            <div className="panel">
              <div className="panel__head">
                <p className="panel__title">Run position</p>
              </div>
              <p className="panel__sub">
                Headline rate across the four cases in this run. No extra cases
                were simulated.
              </p>
              <div className="dist">
                <div className="dist__bars">
                  {CASES.map((entry, index) => {
                    const here = index === selected
                    const height = 16 + entry.share * 96
                    const end = index === CASES.length - 1
                    return (
                      <button
                        type="button"
                        className={here ? "dbar is-here" : "dbar"}
                        key={entry.id}
                        style={{
                          height,
                          background: STATUS_COLOR[entry.status],
                          opacity: here ? 1 : 0.5,
                          border: 0,
                          padding: 0,
                          cursor: "pointer",
                        }}
                        aria-label={`${entry.id}, ${entry.flag}`}
                        onClick={() => {
                          setLit(null)
                          setSelected(index)
                        }}
                      >
                        {here ? (
                          <span
                            className={end ? "dbar__flag is-end" : "dbar__flag"}
                          >
                            {entry.flag}
                          </span>
                        ) : null}
                      </button>
                    )
                  })}
                </div>
                <div className="dist__axis">
                  <span>0</span>
                  <span>half</span>
                  <span>full</span>
                </div>
                <p className="dist__note">
                  <b>{item.id}.</b> {item.distNote}
                </p>
              </div>
            </div>
          </section>

          {item.showFigures ? (
            <section className="panel figures">
              <div className="panel__head">
                <p className="panel__title">Publication figures</p>
              </div>
              <p className="panel__sub">
                Same counts as this page. Vector PDF and 600 DPI PNG. One note,
                so no error bars.
              </p>
              <div className="figgrid">
                <figure className="figcard">
                  <img
                    src="/results/fig1-note-0001-metric-rates.png"
                    alt="Panel A shows transcript capacity: history 7, exam 0, medical decision making 4. Panel B shows correctness 8/11, fabrication 0/11, fluency 11/11, coherence 11/11, and preference adherence 9/11."
                    width={1800}
                    height={780}
                  />
                  <figcaption>
                    Figure 1. Capacity by E&M component and each metric out of
                    11 fields. Fabrication is lower-is-better.{" "}
                    <a href="/results/fig1-note-0001-metric-rates.pdf">PDF</a>
                  </figcaption>
                </figure>
                <figure className="figcard">
                  <img
                    src="/results/fig2-note-0001-correctness-by-section.png"
                    alt="Correctness by component: history 4 of 7, medical decision making 4 of 4. Exam capacity is 0, so it is omitted."
                    width={900}
                    height={780}
                  />
                  <figcaption>
                    Figure 2. Correctness by component: history 4/7, medical
                    decision making 4/4. Exam capacity is 0.{" "}
                    <a href="/results/fig2-note-0001-correctness-by-section.pdf">
                      PDF
                    </a>
                  </figcaption>
                </figure>
              </div>
            </section>
          ) : null}

          <p className="footnote">
            note-0001 rates from the 4 Nov 2026 run. Fabrication is
            lower-is-better; the other four metrics are higher-is-better.
            Scripted cases are gates, not field counts. No note text is shown on
            this page.
            <br />
            Positive bars on a scripted case are gates that held. Coral bars on
            note-0001 are preference misses, one field each, stepping from
            capacity 11 down to 9.
          </p>
        </main>
      </div>
    </div>
  )
}
