"""
Cadence — escalation handler (CAD-15).

The handoff: a red flag becomes a clean clinical summary the OB can act on.

`escalate(patient_id)`:
  1. Reads the patient's symptom history, risk timeline, and plan from Redis.
  2. Builds a structured `EscalationSummary` (severity, plain-English summary,
     triggering readings, pattern context, recommended action).
  3. Writes it to `escalations:{patient_id}`.
  4. Triggers a zero-PHI Web Push to the clinician (no-op until the push story).
  5. Kicks off the async Arize LLM-as-judge eval (no-op until Luis's judge lands).

Returns the `EscalationSummary` so the agent can tell the patient what it did.
"""

from __future__ import annotations

import threading
import uuid
from datetime import datetime, timezone

from ..ingestion.schema import EscalationSummary, SymptomLog
from ..memory import redis_client


def _display_name(patient_id: str) -> str:
    """Synthetic full name from a patient_id, e.g. 'maria-chen' -> 'Maria Chen'."""
    if not patient_id:
        return "Unknown Patient"
    return " ".join(part.capitalize() for part in patient_id.split("-"))


def _recent_bp_readings(symptoms: list[SymptomLog], limit: int = 2) -> list[str]:
    readings = [
        f"{s.bp_systolic}/{s.bp_diastolic}"
        for s in symptoms
        if s.bp_systolic is not None and s.bp_diastolic is not None
    ]
    return readings[-limit:]


def _notify_clinician(escalation: EscalationSummary) -> None:
    """Fire a zero-PHI Web Push. No-op until the push story (CAD-?) lands."""
    try:
        from ..notifications import push  # type: ignore
    except Exception:
        return  # push module not built yet — escalation still succeeds
    try:
        push.notify_escalation(escalation)  # zero-PHI payload built inside push.py
    except Exception:
        # Never let a notification failure break the clinical handoff.
        return


def _kickoff_judge(escalation: EscalationSummary, symptoms: list[SymptomLog]) -> None:
    """Fire-and-forget the Arize LLM-as-judge eval. No-op until Luis's judge lands."""
    try:
        from ..eval import arize_judge  # type: ignore
    except Exception:
        return  # judge not built yet
    plan = redis_client.get_plan(escalation.patient_id)

    def _run() -> None:
        import asyncio
        try:
            asyncio.run(arize_judge.judge_escalation(escalation, symptoms, plan))
        except Exception:
            return

    threading.Thread(target=_run, daemon=True).start()


def escalate(patient_id: str) -> EscalationSummary:
    """Build, persist, and dispatch a clinical escalation for a patient."""
    symptoms = redis_client.get_symptom_history(patient_id)
    risk_timeline = redis_client.get_risk_timeline(patient_id)
    latest_risk = risk_timeline[-1] if risk_timeline else None

    # Pattern context (Luis's pure trend detector), best-effort.
    pattern_titles: list[str] = []
    try:
        from ..risk.patterns import detect

        pattern_titles = [p.title for p in detect(symptoms)]
    except Exception:
        pattern_titles = []

    severity = latest_risk.severity if latest_risk else "escalate"
    summary_text = (
        latest_risk.rationale
        if latest_risk
        else "Escalation requested for review of recent check-ins."
    )
    recommended = (
        latest_risk.recommended_action
        if latest_risk
        else "Review the patient's recent readings and consider contact."
    )
    triggered = (latest_risk.triggered_flags if latest_risk else []) or []

    escalation = EscalationSummary(
        escalation_id=f"esc-{patient_id}-{uuid.uuid4().hex[:8]}",
        patient_id=patient_id,
        patient_name=_display_name(patient_id),
        timestamp=datetime.now(timezone.utc),
        severity=severity,
        summary=summary_text,
        triggering_readings=_recent_bp_readings(symptoms) or triggered,
        pattern_context=pattern_titles,
        recommended_action=recommended,
    )

    redis_client.write_escalation(patient_id, escalation)
    redis_client.publish_escalation(escalation)  # live clinician WebSocket (CAD-29)
    _notify_clinician(escalation)
    _kickoff_judge(escalation, symptoms)
    return escalation


def escalate_safety(patient_id: str, verdict) -> EscalationSummary:
    """
    Escalate a SafetyVerdict from the semantic safety layer (backend/safety).

    Distinct from escalate(): the trigger is a condition-agnostic crisis signal
    (self-harm, abuse, acute emergency) detected on the patient's message, NOT a
    care-plan vitals threshold. Builds the clinical handoff from the verdict and
    dispatches it through the same Redis + WebSocket + Web Push path so it lands
    in the clinician inbox identically. Does NOT fire the vitals LLM-as-judge
    (that eval is about care-plan escalations).
    """
    _CATEGORY_LABEL = {
        "self_harm": "expressed thoughts of self-harm",
        "abuse": "indicated they may be unsafe or experiencing abuse",
        "medical_emergency": "reported a possible acute medical emergency",
        "acute_distress": "is in acute distress",
    }
    label = _CATEGORY_LABEL.get(verdict.category, "needs urgent review")
    escalation = EscalationSummary(
        escalation_id=f"esc-{patient_id}-{uuid.uuid4().hex[:8]}",
        patient_id=patient_id,
        patient_name=_display_name(patient_id),
        timestamp=datetime.now(timezone.utc),
        severity=verdict.severity,
        summary=(
            f"Safety alert: patient {label} in a check-in message. "
            f"{verdict.rationale}".strip()
        ),
        triggering_readings=[],
        pattern_context=[],
        recommended_action=(
            "Contact the patient now. This is a safety concern outside the care plan; "
            "follow your crisis-response protocol."
        ),
    )

    redis_client.write_escalation(patient_id, escalation)
    redis_client.publish_escalation(escalation)
    _notify_clinician(escalation)
    return escalation
