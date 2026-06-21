"""
Cadence — API Request/Response Models (FROZEN CONTRACT)

The exact shapes that cross the network between frontend and backend.
The frontend builds against these; the backend implements them. Match them exactly.

See CONTRACT.md for the endpoint table that maps these to routes.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from .schema import (
    ActionType,
    ChatMessage,
    EscalationSummary,
    PatternAlert,
    RedFlag,
    RiskScore,
    Severity,
    SymptomLog,
    VisitSummary,
)


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/chat/message  (patient)
# ─────────────────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    patient_id: str
    message: str
    session_id: Optional[str] = None       # omit to continue today's session


class ChatResponse(BaseModel):
    reply: str                             # agent's response text
    flagged: bool = False                  # true if this turn escalated
    risk: Optional[RiskScore] = None       # present if assess_risk ran this turn


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/ingest  (clinician — upload care plan)
# ─────────────────────────────────────────────────────────────────────────────

class IngestResponse(BaseModel):
    patient_id: str
    ok: bool
    red_flags: list[RedFlag] = Field(default_factory=list)
    message: str = ""


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/clinician/panel  (clinician)
# ─────────────────────────────────────────────────────────────────────────────

class PanelRow(BaseModel):
    patient_id: str
    patient_name: str
    severity: Severity                     # drives the RiskBadge color
    last_check_in: Optional[datetime] = None
    headline: str = ""                     # one-line status, e.g. "BP elevated x2"


class PanelResponse(BaseModel):
    patients: list[PanelRow]               # pre-sorted: highest risk first (50 -> 3)


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/clinician/patient/{id}  (clinician)
# ─────────────────────────────────────────────────────────────────────────────

class PatientDetailResponse(BaseModel):
    patient_id: str
    patient_name: str
    current_risk: Optional[RiskScore] = None
    timeline: list[SymptomLog] = Field(default_factory=list)        # chronological
    patterns: list[PatternAlert] = Field(default_factory=list)
    visit_summary: Optional[VisitSummary] = None


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/clinician/escalations  (clinician) + WebSocket /ws/escalations
# ─────────────────────────────────────────────────────────────────────────────

class EscalationsResponse(BaseModel):
    escalations: list[EscalationSummary]   # newest first


# WebSocket /ws/escalations pushes a single EscalationSummary (JSON) on each new flag.


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/clinician/action  (clinician)
# ─────────────────────────────────────────────────────────────────────────────

class ActionRequest(BaseModel):
    patient_id: str
    action: ActionType                     # message | book | flag | note
    content: str = ""                      # message body / note text / booking detail


class ActionResponse(BaseModel):
    ok: bool
    message: str = ""


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/patient/history  +  /api/patient/watchfor  +  /api/patient/summary
# (patient — read-only views backing the existing Lovable routes)
# ─────────────────────────────────────────────────────────────────────────────

class HistoryResponse(BaseModel):
    patient_id: str
    entries: list[SymptomLog]              # chronological, newest first
    check_in_count: int
    flags_count: int


class WatchForResponse(BaseModel):
    patient_id: str
    red_flags: list[RedFlag]               # from the patient's care plan


class SummaryResponse(BaseModel):
    patient_id: str
    visit_summary: VisitSummary


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/push/subscribe  (clinician — register browser for Web Push)
# ─────────────────────────────────────────────────────────────────────────────

class PushSubscribeRequest(BaseModel):
    clinician_id: str
    subscription: dict                     # the browser PushSubscription JSON


class GenericOk(BaseModel):
    ok: bool = True


# ─────────────────────────────────────────────────────────────────────────────
# Chat history (patient — backs the chat thread on load)
# ─────────────────────────────────────────────────────────────────────────────

class ChatHistoryResponse(BaseModel):
    patient_id: str
    session_id: str
    messages: list[ChatMessage]
