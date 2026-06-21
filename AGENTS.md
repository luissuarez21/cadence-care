# Cadence — Full Project Guide (AGENTS.md)

> Read this entire file before writing a single line of code. It is the source of truth for
> what we are building, why, who it is for, how it works, and what matters most in the demo.
> Update it as the repo evolves.

---

## ⛔ FROZEN CONTRACT — read before writing any backend code

Two people build this repo in parallel (Adit = backend infra, Luis = AI layer), often with
separate Codex sessions. To keep the two from drifting, the data shapes and API are
**frozen**. Before generating or editing backend code, read:

- **`backend/CONTRACT.md`** — endpoint table, Redis key map, ownership rules
- **`backend/ingestion/schema.py`** — the 7 core data models (the field names ARE the contract)
- **`backend/ingestion/api_models.py`** — request/response shape for every endpoint
- **`backend/agent/tools.py`** — the 7 frozen tool signatures + registry

Rules:
1. **Do not rename a field** in `schema.py` without editing it there AND telling the other person.
   The frontend, endpoints, and tools all key off these exact names.
2. **Luis implements** `assess_risk`, `detect_pattern`, `generate_visit_summary` in his own files
   (`backend/risk/`, `backend/summaries/`) and they get imported into `TOOL_REGISTRY`.
   **Luis never edits `tools.py`** — only Adit owns the registry. This keeps the tool layer collision-free.
3. Every tool returns a Pydantic model from `schema.py` — never an ad-hoc dict.
4. Work in your own clone/branch; sync through GitHub. Don't both point Codex at the same folder.

---

## What We Are Building

**Cadence** is a proactive AI health companion for high-risk pregnant women and the OBs who care for them.

It lives in the gap between prenatal appointments — the silent 7–14 days where dangerous symptoms build
undetected, where patients don't know what's worth calling about, and where clinicians have zero visibility.

**One-liner:**
*Cadence turns any OB care plan into a daily AI companion for the patient and a full-picture briefing tool
for the clinician — catching problems early, never causing panic, and handing the doctor a complete story
before the conversation even starts.*

---

## The Problem (The Pitch Starts Here)

### The United States has the worst maternal mortality rate in the developed world.

- **23.8 maternal deaths per 100,000 live births** — higher than any other high-income country
- **Preeclampsia alone causes ~15% of all maternal deaths in the US** — and is almost entirely preventable
  with early detection
- **2–10% of US pregnancies are classified as high-risk**: gestational diabetes, preeclampsia risk,
  preterm labor history, multiple gestation, advanced maternal age, chronic conditions
- That is **~150,000–750,000 women per year** in the high-risk category in the US alone
- Gestational diabetes increased **36% between 2016 and 2024** — 79 cases per 1,000 births
- Early-onset preeclampsia (before 34 weeks) carries a **10x greater risk of maternal death**
  compared to normal pregnancy
- When preeclampsia and gestational diabetes co-occur: **82.7% C-section rate, 46.7% preterm birth
  rate, 49.3% NICU admission rate**

### The visit schedule leaves massive gaps — and nothing fills them.

**Standard high-risk prenatal schedule:**
- Weeks 4–16: every 4 weeks
- Weeks 16–28: every 2–3 weeks
- Weeks 28–36: every 1–2 weeks
- Weeks 36–birth: weekly

Even in a high-risk pregnancy, a patient is often alone for **10–14 days at a stretch** — especially
in the second trimester when preeclampsia and gestational diabetes are most likely to develop.

### The current system is entirely reactive. The patient has to initiate.

Today, between visits a high-risk pregnant woman has:
- A **patient portal** (MyChart etc.) where she can send a message — read by a nurse during
  business hours, if she sends one at all
- A **nurse hotline** — call, wait on hold, describe symptoms to someone who doesn't know her chart
- **"Go to the ER"** — the actual advice for anything scary at 2am
- **Nothing** — the most common outcome. She notices something, doesn't know if it's serious,
  decides not to "bother" her doctor, and waits for the next appointment.

A JAMA study found pregnant patients sent an average of **13 portal messages in their entire
pregnancy** — mostly administrative (scheduling, prescriptions), not symptom reports.

### The dangerous symptoms are exactly the ones patients dismiss.

| Symptom | What it signals | Why she waits |
|---|---|---|
| Persistent headache | Eclampsia warning | "It's just a pregnancy headache" |
| Face/hand swelling | Preeclampsia | "Swelling is normal in pregnancy" |
| BP ≥140/90 | Hypertensive crisis | Doesn't check — no routine cued |
| Visual changes / flashing lights | Eclampsia | Thinks it's tiredness |
| Reduced fetal movement | Fetal distress | Anxious but unsure when to call |
| Contractions before 37 weeks | Preterm labor | Thinks it's Braxton Hicks |
| Rapid weight gain | Fluid retention / preeclampsia | Doesn't connect it to urgency |

**The root problem is not that women don't care. It's that they don't know what to watch for,
don't have a structured way to report it, and have no one checking on them.**

---

## The Solution: Two Experiences, One Engine

Cadence is two products sharing one AI engine:

### 1. The Patient Companion (what she uses daily)

A **visually warm, non-clinical mobile-first web app** that acts as her daily health check-in partner.
NOT a scary medical dashboard. NOT a list of things that could go wrong. A companion she trusts —
one that knows her plan, remembers what she said yesterday, and helps her feel informed and seen.

**What she experiences:**
- A **daily chat check-in** — conversational, friendly, never alarm-y. Asks about the specific
  things her OB wants tracked (BP, weight, symptoms, fetal movement, medications) in plain language
- A **"Things to watch for" card** — not fear-mongering. Framed as: *"Your OB wants you to let
  Cadence know right away if any of these happen."* Color-coded gently. Backed by her specific plan.
- A **symptom log** she can see — her own history visualized simply: "You've logged 14 check-ins.
  No red flags detected." Gives her agency and confidence.
- A **"Take to your appointment" summary** — auto-generated before each visit: what she reported,
  any patterns, suggested questions to ask her doctor. She walks in prepared instead of trying to
  remember two weeks of symptoms on the spot.
- An **alert system she controls** — she can flag anything with one tap: "I want my OB to know
  about this." Low friction, no drama. The agent decides the clinical urgency; she decides to flag.
- **No unsolicited fear**. The app never says "this could be dangerous" without context. It says
  "let's let your OB know about this — I've put it in your summary."

**UI principles:**
- Warm colors. Clean typography. Feels like a wellness app, not an EMR.
- The chat is the center. Everything else is secondary.
- Zero medical jargon in the patient-facing copy.
- Accessibility-first: large text, clear contrast, works on low-end Android.

### 2. The Clinician Dashboard (what her OB sees before the appointment)

A **clean, time-saving briefing tool** — not a firehose of data. The OB sits down for a 15-minute
appointment and already knows what happened in the last two weeks.

**What the clinician sees:**
- **Per-patient timeline** — everything the patient reported, in chronological order. BP readings,
  weight logs, symptom check-ins, any flags she raised. Not raw data — summarized intelligently.
- **Pattern detection** — the AI surfaces trends the patient wouldn't notice. *"BP has been
  trending up over the last 6 days — within range but directionally concerning."* *"Patient
  mentioned headaches on 3 separate days this week."* This is the signal the OB needs.
- **Risk score + rationale** — a plain-English explanation of why the patient is `ok | monitor |
  escalate` today. Not a black box. The OB can see exactly what the AI looked at.
- **Suggested conversation starters** — *"Ask about the headaches. Ask about sodium intake.
  Consider checking BP again before she leaves."* The AI does pre-visit prep. The doctor leads.
- **Real-time escalation alerts** — if a red flag is detected between visits, the clinician gets
  an immediate structured summary: what happened, what was said, what the thresholds were, and
  a suggested action. Not a raw alert — a clean clinical handoff.
- **Panel view** — see all patients ranked by current risk level. 50 patients → the 3 that need
  attention today. The rest can wait until their appointment.
- **Action buttons** — message patient, book sooner, flag for nurse, add a note. One click.

**Clinician UX principles:**
- Information density is appropriate for a clinical context — but not overwhelming
- Every AI inference is explained. The clinician always sees the "why"
- The dashboard respects clinical time: the most important things are at the top, always

---

## The AI Agent: How It Works

### The Core Loop (technical + conceptual)

```
OB uploads care plan
        ↓
Codex (vision) ingests → structured protocol JSON
  { goals[], meds[], tasks[], check_in_cadence, red_flags[], patient_context }
        ↓
Daily: agent initiates chat check-in with patient
        ↓
Patient responds in natural language
        ↓
Agent tools fire:
  - lookup_plan(query)         → RAG over patient's care doc
  - log_symptom(data)          → Redis: structured symptom log
  - assess_risk(context)       → risk score + rationale vs. red_flags[]
  - detect_pattern(patient_id) → compare today vs. history (Redis)
  - escalate_to_clinician()    → structured summary → clinician dashboard + alert
  - generate_visit_summary()   → pre-appointment brief for both patient + OB
        ↓
Every decision traced to Arize → LLM-as-judge eval
  "Did it escalate when it should have?"
  "Did it stay calm when it should have?"
        ↓
Clinician sees full picture. Patient feels supported.
```

### What the Agent Does NOT Do
- **Never diagnoses.** Never says "you may have preeclampsia." Collects, triages, escalates.
- **Never tells the patient something is dangerous without context.** If a red flag is hit,
  the agent says: *"Your BP reading is above the threshold from your care plan. I've sent a
  summary to your OB and added this to your appointment brief."* Calm. Actionable. No panic.
- **Never gives medical advice beyond what is in the care plan.** Agent is RAG-grounded.
  Everything it says is traceable to the patient's specific protocol.
- **Never replaces the clinician.** It is a preparation and monitoring tool. The human decides.

### Memory & Continuity
- Every patient has a **Redis-backed per-session and cross-session memory**
- Agent remembers: *"She mentioned a headache 3 days ago. Ask if it's still there."*
- Symptoms are logged with timestamps and structured metadata — not just free text
- Risk timeline is queryable: *"Show me the last 7 days of BP readings"*
- Vector store (Redis) over the care plan enables RAG — agent answers are grounded in her doc

### The Condition Pack System
The engine is condition-agnostic. What changes per condition is a **config pack**:

```json
{
  "condition": "high_risk_pregnancy_preeclampsia",
  "check_in_cadence_hours": 24,
  "daily_questions": [
    "What was your blood pressure reading this morning?",
    "And your evening reading?",
    "Any headaches today — and if so, how bad on a scale of 1–10?",
    "Any swelling in your face or hands (not just feet)?",
    "Have you noticed any visual changes — flashing lights, blurred vision?",
    "How is baby moving today compared to yesterday?",
    "Did you take your low-dose aspirin today?"
  ],
  "red_flags": [
    { "condition": "bp_systolic >= 140 AND bp_diastolic >= 90 on two readings", "severity": "escalate", "message": "BP above threshold on two readings" },
    { "condition": "severe_headache AND visual_changes", "severity": "escalate_urgent", "message": "Possible eclampsia warning signs" },
    { "condition": "face_swelling AND bp_elevated", "severity": "escalate", "message": "Facial swelling with elevated BP" },
    { "condition": "fetal_movement_decreased", "severity": "escalate", "message": "Decreased fetal movement reported" },
    { "condition": "contractions_regular AND gestational_age < 37w", "severity": "escalate_urgent", "message": "Possible preterm labor" }
  ],
  "patient_tone": "warm, reassuring, never clinical",
  "coaching_topics": ["low-dose aspirin adherence", "BP monitoring routine", "when to call OB immediately"],
  "clinician_view": {
    "key_metrics": ["systolic_bp", "diastolic_bp", "headache_severity", "fetal_movement", "swelling_location"],
    "pattern_alerts": ["bp_trending_up_3_days", "recurring_headaches", "inconsistent_fetal_movement"]
  }
}
```

**Pack A — Gestational Diabetes:** daily glucose logs (fasting + post-meal), hypoglycemia symptoms,
fetal kick counts, weight. Red flags: fasting >95 mg/dL consistently, hypoglycemia symptoms, rapid
weight gain, decreased fetal movement.

**Pack B — Preeclampsia Risk (Primary Demo):** as above. The main demo condition.

New condition = new JSON pack. The engine doesn't change. That's the platform story.

---

## Architecture

### Frontend (Paulina owns this)
- **Framework:** Next.js 14 + React + Tailwind CSS
- **Patient app** (`/app/patient`):
  - Chat interface — conversational check-in UI (WhatsApp-style, but warmer)
  - "Things to watch for" card component — pulled from condition pack red flags, written in plain English
  - Symptom history view — timeline of what she's logged, visualized simply
  - "Take to your appointment" page — auto-generated visit summary, shareable/printable
  - Notification banner — when a flag has been sent to her OB, shown gently
- **Clinician dashboard** (`/app/clinician`):
  - Patient panel — sortable by risk level, shows last check-in and current status
  - Patient detail view — full timeline, pattern alerts, risk score + rationale
  - Pre-visit brief — generated summary + conversation starters
  - Escalation inbox — real-time alerts with structured clinical summaries
  - Action buttons — message, book, flag, note

### Backend (Adit owns this)
- **Framework:** FastAPI (Python)
- **Agent orchestrator:** Anthropic Codex API with tool use
  - Model: `Codex-sonnet-4-6` (latest capable model — do NOT hardcode older versions)
  - System prompt: loaded from `prompts/agent_system.txt` — includes patient context, condition pack,
    tone instructions, guardrails
  - Tool definitions: `lookup_plan`, `log_symptom`, `assess_risk`, `detect_pattern`,
    `escalate_to_clinician`, `generate_visit_summary`, `schedule_followup`
- **Plan ingestion pipeline:**
  - Upload endpoint → Codex vision reads PDF/image → structured protocol JSON
  - Schema validated with Pydantic
  - Stored in Redis under `plan:{patient_id}`
- **Memory layer (Redis):**
  - `session:{patient_id}:{session_id}` — conversation turns (last N messages for context window)
  - `symptoms:{patient_id}` — time-series structured log of every check-in response
  - `risk_timeline:{patient_id}` — risk scores + rationale by timestamp
  - `plan:{patient_id}` — parsed protocol JSON from ingestion
  - `vector:{patient_id}` — embeddings of care plan chunks for RAG
  - All keys namespaced by `patient_id` — never mixed across patients
- **RAG:** Redis vector store. Embeddings generated at ingest time. `lookup_plan` tool does
  semantic search over patient's care doc to ground agent answers.
- **Risk engine:** `assess_risk` tool loads the condition pack's `red_flags[]`, evaluates current
  session data against thresholds, calls Codex with a structured rubric → returns
  `{ severity, rationale, recommended_action }`. Every call traced to Arize.
- **Pattern detection:** `detect_pattern` queries `symptoms:{patient_id}` time-series, runs
  trend logic (e.g. BP trending up 3 days, recurring headache mentions), surfaces to both agent
  and clinician dashboard.
- **Escalation:** `escalate_to_clinician` generates a structured clinical summary and writes it
  to `escalations:{patient_id}`. Clinician dashboard receives via websocket in real time.
  Also triggers a **Web Push notification** to the clinician's browser — zero PHI in the
  notification body, just *"A patient needs your attention — tap to review."* Clinician taps
  → lands directly on the escalation in their dashboard. Poke used for secure in-app
  clinician → patient messaging (not for escalation alerts).
- **Visit summary generation:** `generate_visit_summary` queries all symptom logs and risk
  timeline for the period since last appointment → Codex summarizes → two outputs:
  patient-facing (plain English, what to bring up) and clinician-facing (clinical summary,
  patterns, conversation starters).
- **Observability:** Every agent tool call + LLM response traced to Arize Phoenix. LLM-as-judge
  eval runs async: *"Given this patient context and red flags, was escalation appropriate?"*
  Score logged to Arize dashboard. This is our safety proof to judges.
- **Error monitoring:** Sentry — wraps all API routes and agent calls.

### Data flow summary
```
Patient opens app
  → POST /api/chat/message
  → Agent reads: session history + plan (Redis) + condition pack
  → Agent generates response (may call tools)
  → Tools: log_symptom → Redis | assess_risk → risk score | detect_pattern → trends
  → If escalate: generate summary → write escalations:{patient_id} → notify clinician
  → Response streamed back to patient chat
  → All decisions traced to Arize

OB opens dashboard
  → GET /api/clinician/panel → risk-ranked patient list
  → GET /api/clinician/patient/{id} → full timeline + patterns + visit summary
  → GET /api/clinician/escalations → real-time alert inbox
  → POST /api/clinician/action → message | book | flag | note
```

---

## Security, Privacy & Compliance

> This section must be ready to answer every judge question before they ask it.
> Read it. Know it. Reference it in the pitch. Every claim here is architecturally accurate.

### Why this matters
We are handling sensitive health information about pregnant women. Even in a hackathon demo with
synthetic data, we must demonstrate we have thought carefully about how this product operates in
the real world. Judges with healthcare backgrounds will probe this. SkyDeck will probe this.
The answer must be complete and technically correct — not hand-wavy.

---

### Demo: Zero Real PHI, Ever

- All patient data in the demo is **fully synthetic** — fictional names, fictional BP readings,
  fictional care plans. Maria Chen is not a real person.
- State this proactively in the demo. Do not wait to be asked.
- No real OB care plan is ever uploaded. No real clinician name is ever used.
- `seed_data.py` generates all demo data programmatically — nothing typed manually, nothing copied
  from a real patient.

---

### What We Build With Compliance In Mind (Hackathon Implementation)

**Redis — secure connection from day one**
- Connect via `rediss://` (TLS), not `redis://` (plaintext). Even with synthetic data.
- Require authentication: `REDIS_PASSWORD` from `.env`, never hardcoded.
- All keys namespaced by `patient_id` — queries always scoped. Cross-patient leakage is
  architecturally impossible, not just a policy.
- Key structure: `session:{patient_id}`, `symptoms:{patient_id}`, `plan:{patient_id}`,
  `vector:{patient_id}`, `escalations:{patient_id}`. No keys without a patient scope.

**JWT authentication — HttpOnly cookies, not localStorage**
- JWTs must be stored in **HttpOnly, Secure, SameSite=Strict cookies** — never in `localStorage`
  or `sessionStorage`.
- `localStorage` is accessible to JavaScript and vulnerable to XSS. For a health app this is
  unacceptable even in a demo — it sets the wrong architectural precedent.
- Implementation: FastAPI sets the cookie on login. Next.js never touches the raw token.
- Role claims: `{ role: "patient" | "clinician", patient_id | clinician_id }`.
- Clinicians can only query their own assigned patients. Enforced server-side on every route.

**Sentry — PII scrubbing required**
- Configure Sentry with `send_default_pii = False` before initializing.
- Add custom scrubbing rules for health fields: `bp_systolic`, `bp_diastolic`, `symptom`,
  `patient_id` values should be masked in breadcrumbs and error payloads.
- Why: a stack trace from a failed Redis write could contain a patient's symptom log. Sentry
  must never receive readable PHI even in error context.
- In `main.py`: initialize Sentry with scrubbing before any routes are registered.

**Escalation notifications — Web Push, not SMS**
- Clinician escalation alerts use the **Web Push API** (browser push notifications via a
  service worker), not SMS.
- Why not SMS: regular SMS travels over carrier networks unencrypted. Sending clinical details
  via SMS violates HIPAA. Even "notification only" SMS still leaks metadata about clinical events.
- Web Push is end-to-end: the push payload is encrypted in transit (Web Push Protocol uses
  VAPID + AES-128-GCM), delivered directly to the clinician's authenticated browser session.
- **The push notification body contains zero PHI.** It says: *"A patient needs your attention
  — tap to review."* That's it.
- Clinician taps the notification → lands directly on the escalation in their Cadence dashboard
  behind their authenticated session → sees the full clinical summary there.
- The clinical data never leaves the app. The notification is just a tap-to-open signal.

**Implementation (Adit):**
- Backend: generate VAPID key pair (`py-vapid` or `pywebpush`). Store the public key in `.env`.
- When a patient enrolls on the clinician dashboard, browser requests push permission →
  subscription object sent to backend → stored in `push_subscriptions:{clinician_id}` in Redis.
- On escalation: `webpush()` call with the minimal notification payload → delivered to clinician.
- Frontend: `public/sw.js` service worker handles `push` events and shows the notification.

**Poke — in-app secure messaging**
- Poke is used for **secure in-app messaging between clinician and patient** (the "Message"
  action button on the clinician dashboard), not for escalation alerts.
- This is a better fit for Poke's product (messaging platform) and keeps the sponsor coverage.
- Message content stays within Poke's secure channel. No PHI on carrier SMS.

**Arize — de-identified traces**
- Arize receives traces of every agent decision. In production these traces could contain PHI.
- De-identify all Arize span metadata: replace `patient_id` with a hashed/anonymized token
  before sending to Arize. Strip raw symptom text from span attributes.
- What Arize should see: `{ patient_token: "hash_abc123", risk_score: "escalate",
  tool_called: "assess_risk", escalation_appropriate: true }` — not symptom text.
- In production, Arize offers HIPAA-compliant plans with BAAs. Flag this for the enterprise story.
- For the demo with synthetic data, this is low-risk — but build the de-identification habit now.

**Anthropic API — correct for demo, Bedrock for production**
- The Anthropic standard API does not include a HIPAA BAA. It is appropriate for our demo
  because all data is synthetic.
- In production: all LLM inference moves to **Amazon Bedrock** (Codex models available on
  Bedrock). AWS signs BAAs for Bedrock. Patient data stays within AWS infrastructure.
- Never send real patient data through the standard Anthropic API. This is the line.

**Deepgram — voice PHI requires a BAA**
- A patient's voice describing her symptoms is PHI.
- If we build the voice path: use synthetic voice for the demo. In production, Deepgram offers
  HIPAA-compliant plans and BAAs — required before handling any real patient voice data.
- For the demo: recorded fallback audio with a fictional patient. Never a real person's voice.

---

### Production HIPAA Architecture (Tell This To Judges Proactively)

A production Cadence deployment includes:

**Legal**
- **Business Associate Agreement (BAA)** with every covered entity (hospital, OB practice) before
  any real data flows — required under HIPAA for any vendor handling PHI on behalf of a provider
- BAAs also required with: AWS (for infrastructure), Bedrock (for LLM inference), Arize
  (for observability), and any other third party that processes real patient data
- **Patient consent flow** — when a patient enrolls, she sees and accepts: what data is collected,
  who it's shared with (her OB, care team only), that an AI monitors her check-ins and may alert
  her care team, and her right to withdraw. This is not optional. It is a HIPAA authorization.

**Infrastructure**
- AWS HIPAA-eligible services: EC2, ElastiCache (Redis with encryption at rest + in-transit TLS),
  S3 (server-side encryption), RDS if needed — all with HIPAA-eligible configurations explicitly enabled
- Redis: `requirepass` + TLS + encryption at rest + private subnet (never public internet)
- All API traffic over HTTPS/TLS 1.2+. No plaintext data on the wire anywhere.
- VPC with private subnets for all data stores. Backend not publicly accessible.

**Access control**
- RBAC: patients see only their own data. Clinicians see only their assigned patients. No admin
  "see all records" role. Minimum necessary standard enforced at the API layer.
- Every request authenticated. JWT in HttpOnly cookie. Token rotation on suspicious activity.
- Multi-factor authentication for clinician accounts.

**Audit and monitoring**
- Every access to a patient record logged: user ID, timestamp, action, IP. Required by HIPAA
  §164.312(b). Logs stored separately from application logs, immutable, retained per policy.
- Sentry with full PII scrubbing. Health field values masked before leaving the server.
- Arize with de-identified traces and, in production, a signed BAA.

**Data governance**
- PHI retained only as long as clinically necessary. Patients can request full deletion
  (HIPAA Right of Access / Right to Deletion).
- Data minimization: the agent collects only what is in the patient's care plan. No ancillary
  personal data collected.
- Vector embeddings of care plan content are stored in encrypted Redis — treated as PHI, not
  just configuration.

**Breach response**
- HIPAA requires notifying affected individuals and HHS within 60 days of discovering a breach.
- In production: documented incident response plan, defined breach detection via audit log alerts,
  legal counsel on retainer for breach notification.

---

### AI-Specific Safety Guardrails

- **RAG-grounded answers** — agent answers are always traceable to the patient's specific care
  plan. It cannot give general medical advice it hallucinated.
- **No diagnosis, hard-blocked in system prompt** — the system prompt uses explicit constitutional
  rules: "You are not a doctor. You collect symptoms and report them. You never diagnose a condition
  or recommend treatment. If you are about to do either, stop and ask the patient to contact their OB."
- **LLM-as-judge safety eval** — after every escalation, a second Codex call independently
  evaluates: "Was this escalation appropriate given the symptoms and the red flags in the care plan?"
  Score and rationale logged to Arize. This is the auditable safety layer.
- **Human in the loop always visible** — every escalation goes to a licensed clinician who makes
  the actual clinical decision. The dashboard makes this explicit: "Cadence has flagged this for
  your review." The AI suggests. The clinician decides.
- **Jailbreak resistance** — constitutional AI principles in the system prompt + Arize monitoring
  for diagnostic language drift. If the agent ever produces diagnostic language, Arize catches it.

---

### Summary for the Pitch (Say This Verbatim)

> *"We've designed Cadence with compliance as a first-class constraint, not an afterthought. In our
> demo, all data is 100% synthetic — no real patients, no real care plans. Architecturally: escalation
> alerts use Web Push notifications with zero PHI in the payload — no SMS, no carrier network. JWTs
> are stored in HttpOnly cookies. Redis runs with TLS and authentication. Sentry is configured with
> PII scrubbing. Arize traces are de-identified before leaving our infrastructure. In production,
> Cadence runs on HIPAA-eligible AWS with Amazon Bedrock for private LLM inference, requires BAAs
> with every covered entity and third-party processor, enforces minimum necessary access at the API
> layer, and includes patient consent on enrollment. We know exactly where the PHI flows and we've
> closed every gap."*

---

## The Business We Are Building

### Who pays and why

**Buyer 1: OB Practices and MFM Specialists**
- ~3,500 Maternal-Fetal Medicine specialists in the US — concentrated, influential, the "prescribers"
- ~37,000 OBs total
- Pain: managing 50+ high-risk patients with no between-visit visibility. Flying blind until the
  appointment. Legal exposure if something goes wrong in the gap.
- Pays because: malpractice liability reduction, better outcomes, patient satisfaction scores,
  competitive differentiation ("we monitor you between visits")
- Model: per-patient-per-month SaaS subscription (~$50–100/patient/month)

**Buyer 2: Hospital Systems**
- Enterprise contracts with maternal health departments
- Pain: maternal mortality statistics are public. CMS scrutiny. Lawsuits.
- Pays because: one prevented maternal death saves $1–3M in litigation. Cadence's annual cost
  is a rounding error against that number.
- Model: enterprise license + per-patient fee

**Buyer 3: Medicaid**
- Covers **42% of all US births** — the single largest payer for maternity care
- New York State Medicaid already reimburses pregnancy RPM via CPT codes 99453, 99454, 99457
  with HD modifier (effective 2022, expanded 2025). Other states following.
- The billing pathway **already exists**. Babyscripts ($39.8M raised) proves this.
- Pays because: bad maternal outcomes are enormous claims costs. Preterm NICU stays cost
  $50,000–$200,000+. Preventing one pays for years of Cadence.
- Model: per-patient reimbursement via RPM CPT codes

**Buyer 4: Private Insurers**
- Same ROI math as Medicaid — catastrophic maternal outcomes are catastrophic claims
- Increasingly offering maternity management programs; Cadence fits as the AI layer

### The market
- **TAM:** Global maternal health market — 14.6% CAGR, growing to hundreds of billions by 2035
- **SAM:** US high-risk pregnancy monitoring — ~750,000 high-risk pregnancies/year × $600–1,200/year
  per patient = **$450M–$900M/year in the US alone**
- **SOM (Year 1 target):** 10 OB practices × 50 high-risk patients each × $75/patient/month =
  **$450K ARR** — achievable without institutional contracts

### Competitive landscape

| Company | What they do | What they miss | Funding |
|---|---|---|---|
| **Babyscripts** | BP cuff + weight scale, passive logging, clinician alerts | No conversational agent. Patient logs numbers; nobody asks how she feels. | $39.8M |
| **Oula Health** | Reimagined care model, midwife-led, virtual visits | Better visits — doesn't fill the between-visit gap | $50.3M |
| **Diana Health** | In-person redesigned clinics | Not a monitoring product | $45M |
| **Ovia / The Bump** | Consumer pregnancy tracker apps | No clinical connection, no escalation, not personalized to care plan | — |

**The gap Cadence owns:** A proactive, conversational AI companion that is grounded in the patient's
specific OB-issued care plan, tracks subjective symptoms (not just hardware-measured vitals),
detects patterns over time, and generates a full clinical picture for the clinician before the visit.
Nobody does this. Babyscripts is the closest and they're a passive dashboard from a pre-LLM world.

### Why now
- LLMs now capable of clinical-quality language understanding and generation
- CPT codes for pregnancy RPM already established — billing pathway exists
- Maternal mortality is a national policy priority — funding follows
- Babyscripts proved hospital willingness to pay; they built for 2015, we're building for 2026

### The platform story (SkyDeck pitch)
Cadence wins with high-risk pregnancy (concentrated buyer, proven reimbursement, emotional resonance).
Then the condition pack architecture means:
- **Postpartum** — same patient, new protocol. 40% of maternal deaths happen postpartum.
- **Mental health post-discharge** — same proactive check-in model, safety plan as the protocol
- **Addiction recovery** — same engine, recovery plan as the protocol
- **Hospice / palliative** — caregiver-facing, comfort protocol, Medicare per-diem buyer

One engine. Swappable condition packs. **Cadence is the agentic care layer for any care plan.**

---

## The Demo (90 Seconds, Bulletproof)

> Pre-cache everything. Golden path hardcoded. Recorded fallback for every live AI call.
> One person owns the demo end-to-end (Paulina). Rehearse ×5 before presenting.

### Setup (pre-loaded before demo starts)
- Synthetic patient: "Maria Chen", 29 weeks pregnant, preeclampsia risk, on low-dose aspirin,
  has a care plan doc from her OB already ingested and parsed
- Maria has 9 days of prior check-in history already in Redis (shows pattern detection works)
- Clinician: "Dr. Sarah Reyes", MFM specialist, Maria is one of 8 patients in the panel

### The 90-second run

**[0:00–0:15] The problem (spoken, no UI)**
> *"Every year in the US, hundreds of women die from pregnancy complications that were preventable.
> The warning signs were there — elevated blood pressure, recurring headaches, sudden swelling —
> but nobody was watching. Not because the OB wasn't good. Because the OB only sees the patient
> every two weeks, and nothing exists in between. That's the gap we built Cadence for."*

**[0:15–0:35] Patient view — the companion**
- Open Maria's app on mobile (or mobile-sized browser). Show the warm, clean UI.
- Tonight's check-in message from Cadence: *"Hi Maria! Evening check-in time. How are you feeling?
  Let's start with your blood pressure — what did you get tonight?"*
- Maria replies: "142/91"
- Cadence: *"Thanks. Can you take a second reading in about 5 minutes and share it with me?"*
- Maria: "140/90"
- Cadence: *"Got it. Both readings are above the threshold from your care plan. I've flagged this
  for Dr. Reyes and added it to your appointment summary — she'll be in touch. How's your head
  feeling tonight?"*
- Show: the "Things to watch for" card updated. The symptom log added tonight's entry.
  The app is calm. No panic. Maria sees "Sent to Dr. Reyes" and feels held, not scared.

**[0:35–0:50] Clinician view — the briefing**
- Cut to Dr. Reyes's dashboard. Maria is at the top of the panel — status: ESCALATE.
- Click into Maria's profile. Show the escalation summary:
  *"Maria Chen — BP 142/91 and 140/90 this evening. She also reported headaches on Day 3, 6, and 9
  of this monitoring period — frequency increasing. No visual changes reported tonight. Recommended
  action: contact patient, consider advancing appointment."*
- Show the pattern alert: *"BP has been trending upward over 4 days. Headache mentions: 3 of last
  9 days, increasing frequency."*
- Show suggested conversation starters for the upcoming appointment:
  *"Ask about headache location and severity. Ask about sodium intake this week. Re-check BP in
  office before she leaves. Consider 24-hour urine protein if BP remains elevated."*
- One click: "Book earlier." Appointment moved.

**[0:50–1:05] The trust layer**
- Flash the Arize trace: show a single escalation decision — every tool call logged, every
  input/output visible, the LLM-as-judge eval score: *"Escalation appropriate: YES (confidence 0.97)"*
- Say: *"Every decision Cadence makes is logged, explainable, and evaluated. This isn't a black box
  making medical decisions — it's an auditable AI that hands a clean, traceable handoff to a human."*

**[0:65–1:30] The close (spoken)**
> *"Maria didn't know her blood pressure was dangerous. She thought the headaches were from stress.
> Without Cadence, she waits 12 days for her next appointment. With Cadence, Dr. Reyes knows
> tonight — with full context, a pattern history, and a suggested next step. That's the gap we close.
> We're targeting 3,500 MFM specialists in the US first. Medicaid already reimburses pregnancy RPM
> via established CPT codes — the billing pathway exists today. We are Cadence."*

---

## Build Plan & Priorities

### The one rule: text channel is the must-have. Everything else is a bonus.

A working end-to-end loop — plan ingestion → daily text check-in → risk triage → escalation →
clinician dashboard — is the demo. If that works and looks beautiful, we win. Do not sacrifice it
for features.

**Cut from the back if running out of time (in order):**
1. Voice check-in (Deepgram) — recorded fallback covers it
2. Second condition pack (gestational diabetes) — the "same engine, new pack" beat
3. Live plan ingest in demo — can use pre-ingested plan
4. Arize LLM-as-judge — still trace everything, skip the judge eval if tight

### Hour-by-hour build order (24h, 3 people)

**H0–2: Alignment & contracts**
- Lock scope. No feature creep after this.
- Define all data schemas: `ProtocolJSON`, `SymptomLog`, `RiskScore`, `EscalationSummary`, `VisitSummary`
- Define all REST endpoints + websocket events
- Set up repo, `.env`, all API keys loaded
- Adit: FastAPI scaffold + Redis connection confirmed
- Paulina: Next.js scaffold + Tailwind + route structure
- Luis: Write condition pack JSON for preeclampsia. Write agent system prompt. Write red-flag rubric.

**H2–6: Core engine (parallel)**
- **Adit:** Agent loop (Codex tool use), plan ingestion (vision → JSON), Redis memory,
  `log_symptom` + `assess_risk` tools working end-to-end
- **Paulina:** Patient chat UI (send/receive messages), clinician dashboard shell with mock data
- **Luis:** Clinical rubric finalized. Risk rationale language written.
  All patient-facing copy written (the chat messages, the "things to watch for" card, the tone guide).
  Visit summary template written.

**H6–10: Integration**
- Wire frontend to backend. Patient chat → agent → Redis → risk score → back to chat.
- Escalation flow: red flag detected → summary generated → appears on clinician dashboard.
- End-to-end test with Maria's golden path. Should work without any live AI calls (cached).

**H10–14: Polish & second features**
- Paulina: UI polish — patient companion warmth, clinician dashboard density + clarity.
  "Things to watch for" card. Symptom timeline. Visit summary page.
- Adit: Pattern detection (`detect_pattern` tool). Visit summary generation endpoint.
  Arize tracing on all agent calls.
- Luis: Validate red-flag rubric against real clinical criteria. Write pitch. Begin demo script.

**H14–18: Bonus features (only if core is solid)**
- Second condition pack (gestational diabetes)
- Deepgram voice path (or finalize recorded fallback)
- Arize LLM-as-judge eval

**H18–22: Demo hardening**
- Golden path: pre-cache every AI response in the demo sequence
- Recorded fallback for every live call
- Test the 90-second run ×3. Time it.
- Fix every rough edge in the UI.

**H22–24: Final prep**
- Rehearse the full pitch + demo ×3 as a team
- Prepare SkyDeck pitch answers: "Who pays?", "What's the business model?", "What about HIPAA?",
  "How is this different from Babyscripts?", "How do you get OBs to use this?"
- All team members can answer all questions. Not just Luis.

---

## Team & Ownership

**Luis** — Product, clinical accuracy, pitch
- Write the condition pack JSON content (what questions to ask, what the red flags are, in what language)
- Write all patient-facing copy (chat messages, card text, visit summary templates)
- Write the agent system prompt and guardrail instructions
- Validate clinical accuracy — text a real OB or Nabi RD for one quote on the between-visit gap
- Own the pitch narrative and demo script
- Be able to answer every business/clinical question a judge asks

**Adit** — Backend, agent engine, all integrations
- FastAPI backend
- Codex orchestrator with tool use (all 6 tools implemented)
- Plan ingestion pipeline (Codex vision → Pydantic-validated JSON)
- Redis: all key structures, session memory, symptom logs, risk timeline, vector store
- Risk engine: assess_risk tool + pattern detection
- Escalation flow end-to-end
- Arize tracing on every agent call
- Web Push notification on escalation: VAPID key pair, `webpush()` call, `public/sw.js` service worker
- Poke integration for secure clinician → patient in-app messaging (the "Message" action button)
- Sentry error monitoring

**Paulina** — Frontend, UI, demo ownership
- Next.js + Tailwind setup
- Patient companion app: chat UI, "things to watch for" card, symptom timeline, visit summary page
- Clinician dashboard: panel view, patient detail, escalation inbox, action buttons
- Demo run: she owns the 90-second execution. She drives the keyboard during the demo. She
  knows every click, every fallback, every recovery if something breaks.
- UI must feel warm and trustworthy for the patient view, clinical and clean for the OB view

---

## Sponsors & Prize Coverage

| Sponsor | How we use it | Prize eligibility |
|---|---|---|
| **Anthropic Codex** | Core LLM orchestrator + vision for plan ingestion + tool use | Anthropic health track ✅ |
| **Redis** | Per-patient memory, symptom logs, risk timeline, RAG vector store | Redis prize ✅ |
| **Arize** | Every agent decision traced + LLM-as-judge safety eval | Arize prize ✅ |
| **Deepgram** | Voice check-in agent (if time) + recorded fallback | Deepgram prize (need ≥1 real external call) |
| **Web Push API** | Escalation notification to clinician browser (zero PHI in payload) | — |
| **Poke** | Secure in-app clinician → patient messaging ("Message" action button) | Poke prize ✅ |
| **Sentry** | Error monitoring on all API routes + agent calls | Sentry prize ✅ |
| **BrowserBase** | Optional: pull care plan from patient portal (if no PDF upload) | — |

**SkyDeck Pad-13 pitch angle:** Cadence is agentic care infrastructure for the maternal health
crisis. The go-to-market is OB practices and MFM specialists (concentrated, high-value buyer).
The moat is condition pack depth + the trust the agent builds with patients over months.
The platform is any care plan for any chronic condition.

---

## Guardrails & Non-Negotiables

1. **No diagnosis, ever.** The agent collects, triages, and escalates. It never says "you may have
   preeclampsia" or "this sounds like eclampsia." It says "your BP is above the threshold in your
   care plan — I've sent a summary to your OB." Period.

2. **No real PHI in the demo.** Synthetic patients only. State this proactively to judges.

3. **No hallucinated medical advice.** The agent's answers must be grounded in the patient's
   care plan via RAG. If it doesn't know, it says "I'm not sure — let's flag this for your OB."

4. **No API keys in the repo.** All secrets in `.env`. `.env` is gitignored. If you accidentally
   commit a key, rotate it immediately.

5. **The demo must not fail live.** Every AI call in the demo has a hardcoded fallback. The golden
   path is pre-cached. Test the fallback works before stepping on stage.

6. **Human in the loop is always visible.** Every escalation goes to the clinician. Every
   suggestion is labeled "suggested" not "required." The agent never takes autonomous clinical action.

7. **Use the latest Codex model.** `Codex-sonnet-4-6` for all LLM calls unless a specific reason
   to use another. Do not hardcode old model names.

8. **Keep scope locked after H2.** No new features after the first two hours. If you think of
   something great, write it in `FUTURE_SCOPE.md`. Build what's in this doc.

---

## Protocol JSON Schema

Every ingested care plan is parsed into this structure. Validate with Pydantic.

```python
class ProtocolJSON(BaseModel):
    patient_id: str
    condition: str                    # e.g. "high_risk_pregnancy_preeclampsia"
    gestational_age_weeks: int | None
    goals: list[str]
    medications: list[dict]           # { name, dose, frequency, instructions }
    tasks: list[dict]                 # { task, frequency, instructions }
    check_in_cadence_hours: int       # how often agent initiates check-in
    red_flags: list[dict]             # { description, severity, escalation_message }
    patient_context: str              # free-text from OB for agent context
    created_at: datetime
    last_updated: datetime
```

---

## File Structure (scaffold to this)

```
cadence-care/
├── AGENTS.md                        ← this file
├── FUTURE_SCOPE.md                  ← features we didn't build
├── .env                             ← secrets (gitignored)
├── .env.example                     ← template, committed
│
├── packs/                           ← condition packs (Luis owns)
│   ├── preeclampsia_risk.json       ← primary demo condition
│   └── gestational_diabetes.json   ← second pack (H14+ only)
│
├── frontend/                        ← Next.js 14 + Tailwind (Paulina owns)
│   ├── public/
│   │   └── sw.js                   ← service worker for Web Push notifications
│   ├── app/
│   │   ├── layout.tsx              ← root layout, push permission request on mount
│   │   ├── patient/                ← patient companion app
│   │   │   ├── chat/
│   │   │   │   └── page.tsx        ← daily check-in chat UI
│   │   │   ├── watchfor/
│   │   │   │   └── page.tsx        ← "Things to Watch For" card
│   │   │   ├── history/
│   │   │   │   └── page.tsx        ← symptom timeline (last 14 days)
│   │   │   └── summary/
│   │   │       └── page.tsx        ← "Take to Your Appointment" brief
│   │   └── clinician/              ← clinician dashboard
│   │       ├── panel/
│   │       │   └── page.tsx        ← all patients, risk-ranked
│   │       ├── patient/
│   │       │   └── [id]/
│   │       │       └── page.tsx    ← patient detail + timeline + visit brief
│   │       └── escalations/
│   │           └── page.tsx        ← real-time escalation inbox
│   └── components/
│       ├── ChatBubble.tsx          ← patient vs. agent message styling
│       ├── RiskBadge.tsx           ← ok (green) / monitor (amber) / escalate (red)
│       ├── WatchForCard.tsx        ← "Things to Watch For" card
│       ├── SymptomTimeline.tsx     ← chronological symptom log
│       ├── VisitSummaryCard.tsx    ← pre-appointment brief (patient + clinician variants)
│       ├── PatientPanel.tsx        ← risk-ranked patient list row
│       ├── ConversationStarters.tsx← OB suggested questions
│       └── AlertBanner.tsx         ← gentle "OB has been notified" banner
│
├── backend/                         ← FastAPI (Adit owns infrastructure; Luis owns AI layer)
│   ├── main.py                     ← FastAPI app, routes, CORS, Sentry init
│   ├── routes/
│   │   ├── chat.py                 ← POST /api/chat/message
│   │   ├── clinician.py            ← GET /api/clinician/panel|patient/{id}|escalations
│   │   │                              POST /api/clinician/action
│   │   └── ingest.py               ← POST /api/ingest
│   ├── agent/
│   │   ├── orchestrator.py         ← Codex tool-use loop (Adit)
│   │   ├── tools.py                ← tool registry + dispatch (Adit wires; Luis implements)
│   │   └── prompts/                ← all prompt templates (Luis owns)
│   │       ├── system.txt          ← agent system prompt + guardrails
│   │       ├── visit_summary_patient.txt
│   │       ├── visit_summary_clinician.txt
│   │       ├── lmj_eval.txt        ← LLM-as-judge evaluation prompt
│   │       └── rubrics/
│   │           └── preeclampsia.txt← ok | monitor | escalate criteria + rationale language
│   ├── ingestion/
│   │   ├── pipeline.py             ← upload → Codex vision → ProtocolJSON (Adit)
│   │   └── schema.py               ← Pydantic models: ProtocolJSON, SymptomLog, etc. (Adit)
│   ├── memory/
│   │   ├── redis_client.py         ← Redis TLS connection + all key helpers (Adit)
│   │   └── rag.py                  ← embeddings + lookup_plan semantic search (Adit)
│   ├── risk/
│   │   ├── classifier.py           ← assess_risk tool implementation (Luis)
│   │   └── patterns.py             ← detect_pattern trend logic (Luis)
│   ├── escalation/
│   │   └── handler.py              ← generate summary → Redis → Web Push → Poke (Adit)
│   ├── summaries/
│   │   └── visit_summary.py        ← generate_visit_summary implementation (Luis)
│   ├── notifications/
│   │   └── push.py                 ← Web Push via pywebpush, VAPID keys, subscription mgmt (Adit)
│   ├── eval/
│   │   └── arize_judge.py          ← async LLM-as-judge eval, logs to Arize (Luis)
│   └── demo/
│       ├── seed_data.py            ← seeds Maria Chen's 9-day history into Redis (Luis)
│       └── golden_path.py          ← pre-cached AI responses + fallback handler (Luis)
```

---

## Key Stats for the Pitch (Luis memorizes these)

- US maternal mortality: **23.8 per 100,000 live births** — worst in the developed world
- Preeclampsia: causes **~15% of US maternal deaths**, almost entirely preventable with early detection
- High-risk pregnancies: **2–10% of all US pregnancies** = ~150K–750K women/year
- Gestational diabetes: **up 36% since 2016** — 79 per 1,000 births in 2024
- Early-onset preeclampsia: **10x greater risk of maternal death** vs. normal pregnancy
- Between-visit gap: high-risk patients often alone for **10–14 days** in the second trimester
- Current system: patients send an average of **13 portal messages in their entire pregnancy**,
  mostly administrative — almost no symptom reporting
- Babyscripts (closest competitor): **$39.8M raised** — passive BP/weight logging, no conversational agent
- Medicaid CPT codes for pregnancy RPM: **already exist** (99453, 99454, 99457 with HD modifier)
- Medicaid covers **42% of all US births**
- MFM specialists in US: **~3,500** — a concentrated, reachable first buyer
- One prevented maternal death saves a hospital: **$1–3M in litigation**

---

## What We Are NOT Building (scope protection)

- No phone calls or voice check-ins in the MVP — the chatbot is the interaction model
- No EHR integration (Epic, Cerner) — we ingest the care plan as a doc upload; OB workflow is the dashboard
- No wearable hardware integration — software-only; patient enters readings manually
- No medication dispensing or prescription functionality
- No diagnosis, ever
- No real patient data in the demo

---

## Status

Greenfield as of June 2026. AGENTS.md reflects the full product vision after advisor review
(Dylan Vu, CalHacks) and deep niche research. Next session: scaffold the repo to the file
structure above, define the Pydantic schemas, stub all agent tools, build the first chat route.

Start with: `backend/ingestion/schema.py` → `backend/memory/redis_client.py` →
`backend/agent/tools.py` (stubs) → `backend/main.py` (first route: `POST /api/chat/message`).
