"""
Cadence — Visit Summary generator (CAD-16)

Pure pre-appointment brief in two voices.

    summarize(symptoms, risk_timeline, plan) -> VisitSummary

- patient_facing  : warm, plain-English, "what to bring up with your OB"
- clinician_facing: clinical summary + the trends detect() surfaced
- conversation_starters: pre-visit prep questions for the OB
- key_metrics     : compact numbers for the dashboard header

Design notes
------------
PURE + DETERMINISTIC: built from the data with templates so it is reproducible
and unit-testable offline (and demo-safe — no live LLM call to fail on stage).
The companion prompt templates in `backend/agent/prompts/visit_summary_*.txt`
are written for an optional Claude-polished variant the orchestrator can use
later; the shapes returned here are identical either way.
"""

from __future__ import annotations

from datetime import datetime, timezone

from ..ingestion.schema import (
    ProtocolJSON,
    RiskScore,
    SymptomLog,
    VisitSummary,
)
from ..risk.classifier import classify
from ..risk.patterns import detect

_DECREASED_MOVEMENT_WORDS = ("decreas", "less", "reduc", "none", "no movement", "fewer")
_FACE_HAND = ("face", "hands", "hand", "facial", "face and hands")


def _ob_name(plan: ProtocolJSON) -> str:
    """Pull the OB's name from patient_context if present, else a neutral fallback."""
    ctx = plan.patient_context or ""
    for marker in ("Dr. ", "Dr ", "OB: "):
        if marker in ctx:
            tail = ctx.split(marker, 1)[1]
            name = tail.split(".")[0].split(",")[0].split("\n")[0].strip()
            if name:
                return ("Dr. " + name) if marker.startswith("Dr") else name
    return "your OB"


def _bp_readings(symptoms: list[SymptomLog]) -> list[SymptomLog]:
    return [s for s in symptoms if s.bp_systolic is not None and s.bp_diastolic is not None]


def _avg_bp(readings: list[SymptomLog]) -> tuple[int, int] | None:
    if not readings:
        return None
    sys = round(sum(r.bp_systolic for r in readings) / len(readings))
    dia = round(sum(r.bp_diastolic for r in readings) / len(readings))
    return sys, dia


def _peak_bp(readings: list[SymptomLog]) -> SymptomLog | None:
    return max(readings, key=lambda r: r.bp_systolic) if readings else None


def _headache_days(symptoms: list[SymptomLog]) -> int:
    days = {s.timestamp.date() for s in symptoms
            if s.headache_severity is not None and s.headache_severity >= 1}
    return len(days)


def _missed_aspirin_days(symptoms: list[SymptomLog]) -> int:
    days = {s.timestamp.date() for s in symptoms if s.medication_taken is False}
    return len(days)


def _empty_summary(plan: ProtocolJSON) -> VisitSummary:
    now = datetime.now(timezone.utc)
    return VisitSummary(
        patient_id=plan.patient_id,
        generated_at=now,
        period_start=now,
        period_end=now,
        patient_facing=(
            "You don't have any check-ins logged for this period yet. Once you start "
            "checking in with Cadence, this page will gather everything worth bringing "
            "up at your next appointment."
        ),
        clinician_facing="No check-ins recorded for this period.",
        conversation_starters=[],
        key_metrics={},
    )


def summarize(
    symptoms: list[SymptomLog],
    risk_timeline: list[RiskScore],
    plan: ProtocolJSON,
) -> VisitSummary:
    """Generate patient + clinician visit briefs from logs since the last appointment."""
    if not symptoms:
        return _empty_summary(plan)

    ordered = sorted(symptoms, key=lambda s: s.timestamp)
    period_start = ordered[0].timestamp
    period_end = ordered[-1].timestamp
    check_in_days = len({s.timestamp.date() for s in ordered})

    readings = _bp_readings(ordered)
    avg = _avg_bp(readings)
    peak = _peak_bp(readings)
    headache_days = _headache_days(ordered)
    missed_aspirin = _missed_aspirin_days(ordered)
    swelling_days = sorted({
        (s.swelling_location or "").lower() for s in ordered
        if (s.swelling_location or "").lower() in _FACE_HAND
    })
    movement_flags = [
        s for s in ordered
        if s.fetal_movement and any(w in s.fetal_movement.lower() for w in _DECREASED_MOVEMENT_WORDS)
    ]

    patterns = detect(ordered)
    # Current risk: prefer the latest entry in the timeline, else classify now.
    current_risk = (
        sorted(risk_timeline, key=lambda r: r.timestamp)[-1]
        if risk_timeline else classify(ordered, plan)
    )

    ob = _ob_name(plan)

    # ── key_metrics (compact, all strings) ──
    key_metrics: dict[str, str] = {"check_ins": str(check_in_days)}
    if avg:
        key_metrics["avg_bp"] = f"{avg[0]}/{avg[1]}"
    if peak:
        key_metrics["peak_bp"] = f"{peak.bp_systolic}/{peak.bp_diastolic}"
    key_metrics["headache_days"] = str(headache_days)
    if missed_aspirin:
        key_metrics["missed_aspirin_days"] = str(missed_aspirin)
    key_metrics["current_risk"] = current_risk.severity

    # ── patient-facing (warm, plain English) ──
    p: list[str] = []
    p.append(
        f"Over the last {check_in_days} day(s) you checked in with Cadence — nice work "
        f"staying on top of it. Here's a simple recap to bring to {ob}."
    )
    if avg:
        p.append(f"Your blood pressure averaged about {avg[0]}/{avg[1]}.")
    if peak and peak.bp_systolic >= 140:
        p.append(
            f"Your highest reading was {peak.bp_systolic}/{peak.bp_diastolic} on "
            f"{peak.timestamp.date().isoformat()} — worth mentioning."
        )
    if headache_days:
        p.append(f"You mentioned headaches on {headache_days} day(s).")
    if swelling_days:
        p.append(f"You noticed swelling in your {', '.join(swelling_days)}.")
    if movement_flags:
        p.append("You felt baby moving less than usual on at least one day.")
    if missed_aspirin:
        p.append(
            f"Your aspirin was missed on {missed_aspirin} day(s) — let's get back on track."
        )
    p.append("This is not a diagnosis — just what to share so your OB has the full picture.")
    patient_facing = " ".join(p)

    # ── clinician-facing (clinical) ──
    c: list[str] = []
    c.append(
        f"{check_in_days} check-in day(s) from {period_start.date().isoformat()} to "
        f"{period_end.date().isoformat()}. Current Cadence risk: {current_risk.severity}."
    )
    if avg and peak:
        c.append(
            f"BP: mean {avg[0]}/{avg[1]}, peak {peak.bp_systolic}/{peak.bp_diastolic} "
            f"({peak.timestamp.date().isoformat()})."
        )
    if headache_days:
        c.append(f"Headache reported on {headache_days} day(s).")
    if swelling_days:
        c.append(f"Facial/hand swelling reported ({', '.join(swelling_days)}).")
    if movement_flags:
        c.append(f"Decreased fetal movement on {len(movement_flags)} occasion(s).")
    if missed_aspirin:
        c.append(f"Low-dose aspirin missed on {missed_aspirin} day(s).")
    if patterns:
        c.append("Trends: " + "; ".join(f"{a.title} — {a.detail}" for a in patterns))
    if current_risk.rationale:
        c.append(f"Latest rationale: {current_risk.rationale}")
    clinician_facing = " ".join(c)

    # ── conversation starters (pre-visit prep for the OB) ──
    starters: list[str] = []
    if headache_days:
        starters.append("Ask about headache frequency, location, and severity.")
    if peak and peak.bp_systolic >= 140:
        starters.append("Re-check BP in office before she leaves.")
    if any(a.metric == "bp_systolic" for a in patterns):
        starters.append("Review the upward BP trend; consider 24-hour urine protein if it persists.")
    if swelling_days:
        starters.append("Examine for new facial/hand edema.")
    if movement_flags:
        starters.append("Confirm fetal movement and consider an NST if reduced.")
    if missed_aspirin:
        starters.append("Reinforce low-dose aspirin adherence.")
    starters.append("Ask about sodium intake and hydration this week.")

    return VisitSummary(
        patient_id=plan.patient_id,
        generated_at=datetime.now(timezone.utc),
        period_start=period_start,
        period_end=period_end,
        patient_facing=patient_facing,
        clinician_facing=clinician_facing,
        conversation_starters=starters,
        key_metrics=key_metrics,
    )
