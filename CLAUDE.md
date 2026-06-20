# Cadence — Project Guide (CLAUDE.md)

> This file orients any Claude Code session working in this repo. Read it first.
> **Cadence** is a hackathon project for the **CalHacks AI Hackathon** (UC Berkeley AI Hackathon 2026),
> targeting the **Anthropic health track** (must use Claude Code) + a grand-prize / SkyDeck Pad-13 track.

## What we're building (one-liner)
**Cadence turns any care plan into a proactive AI companion for the patient and a triage copilot for the
clinician — catching problems early and escalating to a human with a clean handoff.**

It generalizes the "agentic care" model (an AI does the *between-visit* work; licensed humans handle the clinical
moments). The wedge is **post-discharge cardiopulmonary monitoring (Heart Failure + COPD)**; the platform is
"any longitudinal condition via condition packs."

## Why it exists (the problem)
Patients are dangerous and expensive *between* visits. The harm (readmission, ER trips, missed deterioration)
happens in the gap that nobody owns. Cadence owns that gap: it proactively checks in, detects red-flags, and
escalates to the care team before a small problem becomes an ER visit. Hospitals pay to avoid CMS readmission
penalties (up to 3% of Medicare reimbursement); value-based care orgs pay because between-visit engagement drives
retention and outcomes.

---

## The core loop (the whole product in 5 steps)
1. **Ingest** — upload any care plan / discharge summary (PDF, photo, text). Claude (vision) extracts a structured
   protocol: `{ goals, meds[], tasks[], check_in_cadence, red_flags[] }`.
2. **Engage** — the agent *proactively* reaches out on that cadence (SMS now, voice as a bonus). Logs symptoms /
   adherence in natural language; answers questions grounded in the patient's own plan (RAG).
3. **Triage** — every interaction is scored by a risk classifier → `ok | monitor | escalate` with a rationale.
4. **Escalate** — on a red-flag, generate a structured clinical summary and route it to the care team.
5. **Clinician copilot** — a dashboard ranks the whole panel by risk; AI summaries + one-click action
   (message / book sooner). The agent triages **50 patients → the 3 that matter.**

> Design principle: every demo beat ends the same way — *the agent catches something and hands a human a clean
> handoff.* Cadence **triages and escalates; it never diagnoses.** Human-in-the-loop is always visible.

---

## Architecture
- **Frontend** (Next.js + React + Tailwind):
  - `Patient chat` — SMS-style web thread + a "call me" button for the voice demo.
  - `Clinician dashboard` — panel ranked by risk, AI summaries, one-click actions.
- **Backend** (FastAPI, Python — or Node if the team prefers): a **Claude orchestrator with tool use**.
  - Agent tools: `lookup_plan` (RAG), `log_symptom`, `assess_risk`, `escalate_to_clinician`, `schedule_followup`.
- **Ingestion**: upload → Claude vision → protocol JSON (validated against the schema above).
- **Memory**: Redis — per-patient conversation history, structured symptom logs, risk timeline.
- **RAG**: small vector store (Redis) over the patient's plan + a tiny per-condition knowledge base.
- **Risk classifier**: Claude + a rubric + the protocol's explicit `red_flags[]` → severity + rationale. Traced to Arize.
- **Voice** (bonus): Deepgram voice agent for one check-in call (real-world action = it places the call and
  escalates on a red-flag). Always keep a **recorded fallback**.
- **Escalation**: Poke (or an SMS mock) pings the clinician.
- **Observability**: Arize tracing on every agent decision + an LLM-as-judge eval ("did it escalate appropriately?"
  = the safety story). Sentry for error polish.

### Condition packs (how "deep niche + general engine" is true)
The engine is condition-agnostic. Each **condition pack** is a small config — *what to ask, how often, red-flag
thresholds, escalation pathway, tone, clinician view* — for one condition. Depth = one excellent pack. Breadth =
"a new condition is just a new pack." Packs live in `packs/<condition>.json` (or similar).

**Pack A — Heart Failure (CHF):** daily check-in; track weight, swelling, breathlessness, orthopnea, fatigue, meds,
sodium. 🚩 weight gain ≥3 lb/24h or ≥5 lb/week, new/worse dyspnea, waking up breathless → escalate (adjust diuretic
before an ER trip). Coaching: low-sodium diet, daily weigh-in, med adherence.

**Pack B — COPD:** daily check-in; track dyspnea, sputum color/volume, cough, rescue-inhaler use, fever, O2 sat. 🚩
purulent/colored sputum + increased breathlessness (Anthonisen), fever, spiking inhaler use → escalate (rescue
action plan). Coaching: inhaler technique, smoking cessation, breathing exercises.

(Alternative niches if we pivot: Oncology = chemo+radiation symptom monitoring; Post-surgical = joint+cardiac.)

---

## Build plan & priorities
**Scope discipline (most important rule):** the **text channel** is the must-have. Voice + the second condition pack
+ the live PDF-ingest breadth beat are **bonuses cut from the back** if time runs short.

Build order:
1. Shared engine + text loop: ingest → proactive check-in → log → risk → escalate → dashboard.
2. Two condition packs (HF + COPD) with real red-flag rubrics.
3. Deepgram voice path (+ recorded fallback).
4. Arize traces + safety eval; Sentry.
5. Demo hardening: golden path, fallbacks, rehearse the 90-second script.

### Demo (90s, bulletproof — pre-cache everything)
1. Drop in the HF plan → protocol built live; drop in the COPD plan → different protocol. "Same engine, any plan."
2. Agent proactively texts the patient; she replies symptoms; agent answers grounded in her plan.
3. She reports a red-flag (e.g. a weight spike) → agent detects, escalates, writes a clinical summary.
4. Cut to the clinician dashboard: she jumps to the top with a summary + suggested action; one-click book. Panel: 50 → 3.
5. Flash the Arize trace: every decision inspectable + the eval that it escalated correctly.

---

## Team & ownership
- **Luis** (growth/ops + health domain): product narrative, clinical rubric / red-flags / knowledge base,
  real-user validation (text a real RD for one quote), pitch + demo script. *Owns "is this real."*
- **Adit** (eng): backend agent engine, ingestion, Redis, integrations. *Owns the core loop.*
- **Paulina** (UI / demo owner): both frontends, dashboard polish, demo rehearsal. *One person owns the demo.*

## Sponsors / prizes we're stacking
Anthropic Claude Code (health track) · Deepgram (voice + real action) · Redis (memory + RAG) · Arize (eval +
observability + safety) · Poke (escalation) · Sentry (polish). Optional: BrowserBase (pull a plan from a portal).
**SkyDeck pitch:** agentic care infrastructure for value-based care orgs.

## Guardrails & conventions
- **Not medical advice / no diagnosis.** Cadence triages and escalates to a licensed human. Keep this framing in
  UI copy, prompts, and the pitch. Show the human-in-the-loop.
- **No real PHI.** Use synthetic patients and synthetic care plans only. Never commit real patient data or API keys
  — keep secrets in `.env` (gitignored).
- **Keep the demo deterministic.** Always have a hardcoded golden path + recorded fallback; never rely on live AI
  succeeding on stage.
- Prefer the latest Claude models for any LLM calls.
- Keep new code consistent with whatever stack we scaffold (this file documents intent; update it as the repo grows).

## Status
Greenfield. This CLAUDE.md was written during planning. Next: scaffold the repo (frontend + backend), define the
protocol JSON schema, and stub the agent tools.

## References (in Notion, under "AI Hackathon")
- 🩺 Healthcare Ideas — Cadence (Plan + POC) — full plan, condition packs, niche analysis.
- 🚀 Idea Catalog & Winning Strategy — broader idea set + the winning rubric.
- 🏢 Sponsor Research & Strategy · 🏆 Past Winners Research & 2026 Playbook.
