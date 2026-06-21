"""
Synthetic mock data for the Cadence demo (Story 1).

Every endpoint returns these shapes until the real Redis/agent wiring lands in
later stories. All data is 100% synthetic — patient_id="maria-chen". No real PHI.
Every object here is a Pydantic model from schema.py / api_models.py so the shapes
are guaranteed to match the frozen contract.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from ..ingestion.schema import (
    ChatMessage,
    EscalationSummary,
    PatternAlert,
    RedFlag,
    RiskScore,
    SymptomLog,
    VisitSummary,
)
from ..ingestion.api_models import (
    ChatHistoryResponse,
    ChatResponse,
    EscalationsResponse,
    HistoryResponse,
    PanelResponse,
    PanelRow,
    PatientDetailResponse,
    SummaryResponse,
    WatchForResponse,
)

NOW = datetime.now(timezone.utc)
PATIENT_ID = "maria-chen"
PATIENT_NAME = "Maria Chen"


def _ago(days: float) -> datetime:
    return NOW - timedelta(days=days)


# ── Care-plan red flags (preeclampsia pack) ─────────────────────────────────
RED_FLAGS = [
    RedFlag(
        description="BP >= 140/90 on two readings",
        severity="escalate",
        escalation_message="Your blood pressure is above the threshold in your care plan.",
    ),
    RedFlag(
        description="Severe headache with visual changes",
        severity="escalate_urgent",
        escalation_message="A bad headache with vision changes is something your OB wants to know about right away.",
    ),
    RedFlag(
        description="Facial or hand swelling with elevated BP",
        severity="escalate",
        escalation_message="Swelling in your face or hands with higher BP is worth flagging.",
    ),
    RedFlag(
        description="Decreased fetal movement",
        severity="escalate",
        escalation_message="Let's tell your OB if baby is moving less than usual.",
    ),
]


# ── Symptom history (9 days, like Maria's seeded demo history) ───────────────
def _symptoms() -> list[SymptomLog]:
    series = [
        (9, 128, 84, 0, None),
        (8, 130, 85, 1, None),
        (7, 131, 86, 0, None),
        (6, 134, 87, 4, None),
        (5, 135, 88, 2, None),
        (4, 138, 88, 0, None),
        (3, 139, 89, 5, None),
        (2, 140, 89, 3, None),
        (0, 142, 91, 6, "face"),
    ]
    out: list[SymptomLog] = []
    for days, sys, dia, head, swell in series:
        out.append(
            SymptomLog(
                patient_id=PATIENT_ID,
                timestamp=_ago(days),
                bp_systolic=sys,
                bp_diastolic=dia,
                headache_severity=head,
                swelling_location=swell,
                vision_changes=False,
                fetal_movement="normal",
                medication_taken=True,
                raw_text=f"BP {sys}/{dia} this evening.",
                notes="Evening check-in.",
            )
        )
    return out


def _current_risk() -> RiskScore:
    return RiskScore(
        patient_id=PATIENT_ID,
        timestamp=NOW,
        severity="escalate",
        rationale="BP 142/91 and 140/90 this evening — above the 140/90 threshold on two readings.",
        recommended_action="Contact patient; consider advancing the appointment.",
        triggered_flags=["BP >= 140/90 on two readings"],
    )


def _patterns() -> list[PatternAlert]:
    return [
        PatternAlert(
            patient_id=PATIENT_ID,
            title="BP trending up 4 days",
            detail="128/84 → 142/91 over the last 4 days.",
            metric="bp_systolic",
            severity="monitor",
        ),
        PatternAlert(
            patient_id=PATIENT_ID,
            title="Recurring headaches",
            detail="Headaches reported on 3 of the last 9 days, increasing severity.",
            metric="headache_severity",
            severity="monitor",
        ),
    ]


def _visit_summary() -> VisitSummary:
    return VisitSummary(
        patient_id=PATIENT_ID,
        generated_at=NOW,
        period_start=_ago(9),
        period_end=NOW,
        patient_facing=(
            "Over the last week your blood pressure has crept up and you've had a few "
            "headaches. Bring these up with Dr. Reyes — they're already in her notes."
        ),
        clinician_facing=(
            "BP trending upward over 4 days (128/84 → 142/91), now above threshold on two "
            "readings tonight. Headaches on 3 of 9 days, increasing severity. No visual "
            "changes reported. Aspirin adherence good."
        ),
        conversation_starters=[
            "Ask about headache location and severity.",
            "Ask about sodium intake this week.",
            "Re-check BP in office before she leaves.",
            "Consider 24-hour urine protein if BP remains elevated.",
        ],
        key_metrics={"avg_bp": "135/87", "latest_bp": "142/91", "check_ins": "9"},
    )


def _escalation() -> EscalationSummary:
    return EscalationSummary(
        escalation_id="esc-maria-001",
        patient_id=PATIENT_ID,
        patient_name=PATIENT_NAME,
        timestamp=NOW,
        severity="escalate",
        summary="Maria Chen — BP 142/91 and 140/90 this evening. Headaches on 3 of last 9 days, increasing.",
        triggering_readings=["142/91", "140/90"],
        pattern_context=["BP trending up 4 days", "Recurring headaches"],
        recommended_action="Contact patient; consider advancing appointment.",
        acknowledged=False,
    )


# ── Endpoint payloads ───────────────────────────────────────────────────────
def chat_response() -> ChatResponse:
    return ChatResponse(
        reply=(
            "Thanks, Maria. Both readings are above the threshold from your care plan. "
            "I've flagged this for Dr. Reyes and added it to your appointment summary. "
            "How's your head feeling tonight?"
        ),
        flagged=True,
        risk=_current_risk(),
    )


def chat_history(session_id: str) -> ChatHistoryResponse:
    msgs = [
        ChatMessage(sender="cadence", text="Hi Maria! Evening check-in time. What was your BP tonight?", timestamp=_ago(0.02)),
        ChatMessage(sender="patient", text="142/91", timestamp=_ago(0.015)),
        ChatMessage(sender="cadence", text="Thanks. Can you take a second reading in 5 minutes?", timestamp=_ago(0.012)),
        ChatMessage(sender="patient", text="140/90", timestamp=_ago(0.008)),
        ChatMessage(sender="cadence", text="Got it — both above threshold. I've flagged this for Dr. Reyes.", timestamp=_ago(0.005), flagged=True),
    ]
    return ChatHistoryResponse(patient_id=PATIENT_ID, session_id=session_id, messages=msgs)


def history_response() -> HistoryResponse:
    entries = list(reversed(_symptoms()))  # newest first
    flags = sum(1 for e in entries if (e.bp_systolic or 0) >= 140)
    return HistoryResponse(
        patient_id=PATIENT_ID,
        entries=entries,
        check_in_count=len(entries),
        flags_count=flags,
    )


def watchfor_response() -> WatchForResponse:
    return WatchForResponse(patient_id=PATIENT_ID, red_flags=RED_FLAGS)


def summary_response() -> SummaryResponse:
    return SummaryResponse(patient_id=PATIENT_ID, visit_summary=_visit_summary())


def panel_response() -> PanelResponse:
    rows = [
        PanelRow(
            patient_id=PATIENT_ID,
            patient_name=PATIENT_NAME,
            severity="escalate",
            last_check_in=NOW,
            headline="BP elevated x2 tonight",
        ),
        PanelRow(
            patient_id="aisha-okoro",
            patient_name="Aisha Okoro",
            severity="monitor",
            last_check_in=_ago(0.4),
            headline="Mild swelling, BP stable",
        ),
        PanelRow(
            patient_id="jordan-lee",
            patient_name="Jordan Lee",
            severity="ok",
            last_check_in=_ago(0.9),
            headline="All readings in range",
        ),
    ]
    return PanelResponse(patients=rows)


def patient_detail(patient_id: str) -> PatientDetailResponse:
    return PatientDetailResponse(
        patient_id=patient_id,
        patient_name=PATIENT_NAME if patient_id == PATIENT_ID else patient_id,
        current_risk=_current_risk(),
        timeline=_symptoms(),
        patterns=_patterns(),
        visit_summary=_visit_summary(),
    )


def escalations_response() -> EscalationsResponse:
    return EscalationsResponse(escalations=[_escalation()])


def sample_escalation() -> EscalationSummary:
    return _escalation()
