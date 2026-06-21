# Cadence — API & Data Contract (FROZEN)

> This is the agreement. Both people (and both Claude Code sessions) build against this.
> Change a field name only by editing `schema.py` **and** telling the other person.
> Source of truth lives in code: `ingestion/schema.py`, `ingestion/api_models.py`, `agent/tools.py`.

---

## Endpoints

| Method | Path | Role | Request | Response | Owner |
|---|---|---|---|---|---|
| POST | `/api/chat/message` | patient | `ChatRequest` | `ChatResponse` | Adit |
| GET | `/api/chat/history` | patient | `?patient_id&session_id?` | `ChatHistoryResponse` | Adit |
| POST | `/api/ingest` | clinician | multipart file + `patient_id` | `IngestResponse` | Adit |
| GET | `/api/patient/history` | patient | `?patient_id` | `HistoryResponse` | Adit |
| GET | `/api/patient/watchfor` | patient | `?patient_id` | `WatchForResponse` | Adit |
| GET | `/api/patient/summary` | patient | `?patient_id` | `SummaryResponse` | Adit |
| GET | `/api/clinician/panel` | clinician | — | `PanelResponse` | Adit |
| GET | `/api/clinician/patient/{id}` | clinician | path id | `PatientDetailResponse` | Adit |
| GET | `/api/clinician/escalations` | clinician | — | `EscalationsResponse` | Adit |
| WS | `/ws/escalations` | clinician | — | streams `EscalationSummary` | Adit |
| POST | `/api/clinician/action` | clinician | `ActionRequest` | `ActionResponse` | Adit |
| POST | `/api/push/subscribe` | clinician | `PushSubscribeRequest` | `GenericOk` | Adit |

All request/response shapes are defined in `ingestion/api_models.py`.

---

## Data schemas (`ingestion/schema.py`)

| Model | Produced by | Consumed by |
|---|---|---|
| `ProtocolJSON` | plan ingestion (Claude Vision) | orchestrator, risk engine, watchfor view |
| `SymptomLog` | `log_symptom` | history view, patterns, risk, clinician detail |
| `RiskScore` | `assess_risk` | chat response, panel ranking, clinician detail |
| `PatternAlert` | `detect_pattern` | clinician detail |
| `EscalationSummary` | `escalate_to_clinician` | escalation inbox (REST + WebSocket) |
| `VisitSummary` | `generate_visit_summary` | patient summary page, clinician detail |
| `ChatMessage` | chat turns | chat thread |

**Shared literals:** `Severity = "ok" | "monitor" | "escalate" | "escalate_urgent"`,
`Role = "patient" | "clinician"`, `ActionType = "message" | "book" | "flag" | "note"`.

---

## Agent tools (`agent/tools.py`)

`lookup_plan(patient_id, query) -> list[str]` ·
`log_symptom(patient_id, data) -> SymptomLog` ·
`assess_risk(patient_id) -> RiskScore` ·
`detect_pattern(patient_id) -> list[PatternAlert]` ·
`escalate_to_clinician(patient_id) -> EscalationSummary` ·
`generate_visit_summary(patient_id) -> VisitSummary` ·
`schedule_followup(patient_id, when) -> bool`

**Ownership rule:** Luis implements `assess_risk`, `detect_pattern`, `generate_visit_summary`
in his own files (`risk/classifier.py`, `risk/patterns.py`, `summaries/visit_summary.py`).
Adit imports them into the `TOOL_REGISTRY` here. Luis never edits `tools.py`.

---

## Redis key map (all TLS, all patient-scoped)

| Key | Type | Holds |
|---|---|---|
| `plan:{patient_id}` | JSON | `ProtocolJSON` |
| `session:{patient_id}:{session_id}` | list | `ChatMessage[]` |
| `symptoms:{patient_id}` | list | `SymptomLog[]` |
| `risk_timeline:{patient_id}` | list | `RiskScore[]` |
| `vector:{patient_id}` | vector | care-plan RAG embeddings |
| `escalations:{patient_id}` | list | `EscalationSummary[]` |
| `messages:{patient_id}` | list | clinician → patient messages (no Poke) |
| `notes:{patient_id}` | list | clinician flags/notes |
| `push_subscriptions:{clinician_id}` | JSON | browser Web Push subscription |

---

## Ground rules

1. Patient IDs scope **every** key — no cross-patient leakage.
2. All demo data synthetic (e.g. `patient_id="maria-chen"`). No real PHI.
3. JWT in HttpOnly cookie; role enforced server-side on every route.
4. Model: `claude-sonnet-4-6`. Never hardcode older model names.
5. Frontend reads `VITE_API_URL` for the backend base URL.
