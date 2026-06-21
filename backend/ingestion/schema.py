"""
Cadence — Shared Data Schemas (FROZEN CONTRACT)

This file is the single source of truth for every object that moves between layers.
Field names and types are the contract. Do NOT rename a field without telling the
other person — the frontend, the backend endpoints, and the AI tools all key off
these exact shapes.

Owner of this file: Adit (but changes require both people to agree).
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

# ─────────────────────────────────────────────────────────────────────────────
# Enums / shared literals
# ─────────────────────────────────────────────────────────────────────────────

# Risk severity is used everywhere: risk engine output, patient timeline, panel ranking.
Severity = Literal["ok", "monitor", "escalate", "escalate_urgent"]

# Role claim carried in the JWT.
Role = Literal["patient", "clinician"]

# Who sent a chat message.
Sender = Literal["cadence", "patient"]

# Clinician one-click action types.
ActionType = Literal["message", "book", "flag", "note"]


# ─────────────────────────────────────────────────────────────────────────────
# 1. ProtocolJSON — the parsed care plan (output of plan ingestion)
# ─────────────────────────────────────────────────────────────────────────────

class Medication(BaseModel):
    name: str
    dose: str
    frequency: str
    instructions: str = ""


class Task(BaseModel):
    task: str
    frequency: str
    instructions: str = ""


class RedFlag(BaseModel):
    """One escalation condition from the care plan / condition pack."""
    description: str                       # e.g. "BP >= 140/90 on two readings"
    severity: Severity                     # ok | monitor | escalate | escalate_urgent
    escalation_message: str                # plain-English message shown when hit


class ProtocolJSON(BaseModel):
    """The structured care plan. Stored at Redis key plan:{patient_id}."""
    patient_id: str
    condition: str                         # e.g. "high_risk_pregnancy_preeclampsia"
    gestational_age_weeks: Optional[int] = None
    goals: list[str] = Field(default_factory=list)
    medications: list[Medication] = Field(default_factory=list)
    tasks: list[Task] = Field(default_factory=list)
    check_in_cadence_hours: int = 24
    red_flags: list[RedFlag] = Field(default_factory=list)
    patient_context: str = ""              # free-text from OB for agent context
    created_at: datetime
    last_updated: datetime


# ─────────────────────────────────────────────────────────────────────────────
# 2. SymptomLog — one structured check-in entry
# ─────────────────────────────────────────────────────────────────────────────

class SymptomLog(BaseModel):
    """
    One logged check-in. Appended to Redis list symptoms:{patient_id}.
    All clinical fields optional — a single check-in may only touch a few.
    """
    patient_id: str
    timestamp: datetime
    bp_systolic: Optional[int] = None
    bp_diastolic: Optional[int] = None
    headache_severity: Optional[int] = None        # 0-10 scale
    swelling_location: Optional[str] = None        # e.g. "face", "hands", "feet"
    vision_changes: Optional[bool] = None
    fetal_movement: Optional[str] = None           # e.g. "normal", "decreased"
    medication_taken: Optional[bool] = None
    raw_text: str = ""                             # the patient's original message
    notes: str = ""                                # agent's structured note


# ─────────────────────────────────────────────────────────────────────────────
# 3. RiskScore — output of assess_risk
# ─────────────────────────────────────────────────────────────────────────────

class RiskScore(BaseModel):
    """
    Result of evaluating current state vs. the care plan red flags.
    Written to Redis list risk_timeline:{patient_id}; surfaced in panel + detail.
    """
    patient_id: str
    timestamp: datetime
    severity: Severity                     # ok | monitor | escalate | escalate_urgent
    rationale: str                         # plain-English "why" — NOT a black box
    recommended_action: str                # what the agent suggests next
    triggered_flags: list[str] = Field(default_factory=list)  # red_flag descriptions hit


# ─────────────────────────────────────────────────────────────────────────────
# 4. PatternAlert — output of detect_pattern (trend over time)
# ─────────────────────────────────────────────────────────────────────────────

class PatternAlert(BaseModel):
    """A trend the patient wouldn't notice. Surfaced on the clinician detail view."""
    patient_id: str
    title: str                             # e.g. "BP trending up 4 days"
    detail: str                            # e.g. "128/84 → 142/91 over Oct 21-24"
    metric: str                            # e.g. "bp_systolic"
    severity: Severity = "monitor"


# ─────────────────────────────────────────────────────────────────────────────
# 5. EscalationSummary — the clinical handoff (output of escalate_to_clinician)
# ─────────────────────────────────────────────────────────────────────────────

class EscalationSummary(BaseModel):
    """
    Structured clinical summary. Written to Redis list escalations:{patient_id},
    pushed to clinician inbox via WebSocket, and triggers a (zero-PHI) Web Push.
    """
    escalation_id: str
    patient_id: str
    patient_name: str                      # synthetic only (e.g. "Maria Chen")
    timestamp: datetime
    severity: Severity
    summary: str                           # e.g. "BP 142/91 and 140/90 this evening..."
    triggering_readings: list[str] = Field(default_factory=list)
    pattern_context: list[str] = Field(default_factory=list)  # related PatternAlert titles
    recommended_action: str
    acknowledged: bool = False


# ─────────────────────────────────────────────────────────────────────────────
# 6. VisitSummary — pre-appointment brief (output of generate_visit_summary)
# ─────────────────────────────────────────────────────────────────────────────

class VisitSummary(BaseModel):
    """
    Two variants generated from the same data. Patient sees `patient_facing`,
    clinician sees `clinician_facing` + `conversation_starters`.
    """
    patient_id: str
    generated_at: datetime
    period_start: datetime
    period_end: datetime
    patient_facing: str                    # plain English, what to bring up
    clinician_facing: str                  # clinical summary + patterns
    conversation_starters: list[str] = Field(default_factory=list)
    key_metrics: dict[str, str] = Field(default_factory=dict)  # e.g. {"avg_bp": "131/85"}


# ─────────────────────────────────────────────────────────────────────────────
# 7. Chat — message shapes
# ─────────────────────────────────────────────────────────────────────────────

class ChatMessage(BaseModel):
    """One turn in a conversation. Stored in Redis list session:{patient_id}:{session_id}."""
    sender: Sender                         # cadence | patient
    text: str
    timestamp: datetime
    flagged: bool = False                  # true if this turn produced an escalation
