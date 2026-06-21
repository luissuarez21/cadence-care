"""
Cadence — Risk Classifier (CAD-13)

Pure, deterministic risk engine for the preeclampsia condition pack.

    classify(symptoms: list[SymptomLog], plan: ProtocolJSON) -> RiskScore

Design notes
------------
- PURE: takes data in, returns a RiskScore. No Redis, no network, no patient_id-only
  lookups. The backend fetches the symptom logs + plan and hands them here.
- DETERMINISTIC: the severity decision is rule-based against the care plan's red-flag
  thresholds — NOT an LLM call. For a safety-critical triage gate this is the right
  call: it is auditable, reproducible, never hallucinates, and is unit-testable offline.
  Claude still runs the *conversation*; this function is the hard clinical gate behind it.
- "NO BLACK BOX": every RiskScore carries a plain-English `rationale` that names the
  actual readings that tripped a threshold, plus the exact care-plan flags in
  `triggered_flags`.

Severity ordering (worst wins): escalate_urgent > escalate > monitor > ok.
"""

from __future__ import annotations

from datetime import datetime, timezone

from ..ingestion.schema import ProtocolJSON, RiskScore, SymptomLog, Severity

# Worst-wins ordering so we can take the max severity across all triggered rules.
_SEVERITY_RANK: dict[str, int] = {
    "ok": 0,
    "monitor": 1,
    "escalate": 2,
    "escalate_urgent": 3,
}

# ── Clinical thresholds (ACOG preeclampsia surveillance) ─────────────────────
SEVERE_SYSTOLIC = 160
SEVERE_DIASTOLIC = 110
ELEVATED_SYSTOLIC = 140
ELEVATED_DIASTOLIC = 90
SEVERE_HEADACHE = 7  # 0–10 scale; >= this is "severe"

_DECREASED_MOVEMENT_WORDS = ("decreas", "less", "reduc", "none", "no movement", "fewer")


def _worst(a: Severity, b: Severity) -> Severity:
    """Return the higher-severity of two labels."""
    return a if _SEVERITY_RANK[a] >= _SEVERITY_RANK[b] else b


def _flag_text(plan: ProtocolJSON, *keywords: str, fallback: str) -> str:
    """
    Find the care-plan red flag whose description contains all keywords, so the
    RiskScore references the patient's actual plan language. Falls back to a
    generic description if the plan doesn't carry that flag.
    """
    for rf in plan.red_flags:
        desc = rf.description.lower()
        if all(k.lower() in desc for k in keywords):
            return rf.description
    return fallback


def _is_elevated(sys: int | None, dia: int | None) -> bool:
    return (sys is not None and sys >= ELEVATED_SYSTOLIC) or (
        dia is not None and dia >= ELEVATED_DIASTOLIC
    )


def _is_severe(sys: int | None, dia: int | None) -> bool:
    return (sys is not None and sys >= SEVERE_SYSTOLIC) or (
        dia is not None and dia >= SEVERE_DIASTOLIC
    )


def _fmt_bp(log: SymptomLog) -> str:
    return f"{log.bp_systolic}/{log.bp_diastolic}"


def classify(symptoms: list[SymptomLog], plan: ProtocolJSON) -> RiskScore:
    """
    Evaluate the latest check-in (and same-day readings) against the care plan's
    red flags and return a RiskScore with a plain-English rationale.
    """
    patient_id = plan.patient_id

    if not symptoms:
        return RiskScore(
            patient_id=patient_id,
            timestamp=datetime.now(timezone.utc),
            severity="ok",
            rationale="No check-ins logged yet, so there is nothing to evaluate.",
            recommended_action="Continue routine monitoring; await the next check-in.",
            triggered_flags=[],
        )

    ordered = sorted(symptoms, key=lambda s: s.timestamp)
    latest = ordered[-1]
    latest_day = latest.timestamp.date()

    # All BP readings from the most recent check-in day (preeclampsia needs two).
    bp_today = [
        s for s in ordered
        if s.timestamp.date() == latest_day
        and (s.bp_systolic is not None or s.bp_diastolic is not None)
    ]
    severe_today = [s for s in bp_today if _is_severe(s.bp_systolic, s.bp_diastolic)]
    elevated_today = [s for s in bp_today if _is_elevated(s.bp_systolic, s.bp_diastolic)]

    severity: Severity = "ok"
    rationale_parts: list[str] = []
    triggered: list[str] = []

    # ── Rule 1: severe-range BP on any single reading → escalate_urgent ──
    if severe_today:
        r = severe_today[0]
        severity = _worst(severity, "escalate_urgent")
        triggered.append(_flag_text(
            plan, "160", fallback="Systolic BP >= 160 OR diastolic BP >= 110 on a single reading",
        ))
        rationale_parts.append(
            f"A blood pressure reading of {_fmt_bp(r)} is in the severe range "
            f"(at or above {SEVERE_SYSTOLIC}/{SEVERE_DIASTOLIC})."
        )
    # ── Rule 2: two elevated readings same day → escalate; one → monitor ──
    elif len(elevated_today) >= 2:
        severity = _worst(severity, "escalate")
        triggered.append(_flag_text(
            plan, "two readings", fallback="BP >= 140/90 on two readings",
        ))
        readings = ", ".join(_fmt_bp(s) for s in elevated_today[:3])
        rationale_parts.append(
            f"Two or more blood pressure readings today were at or above "
            f"{ELEVATED_SYSTOLIC}/{ELEVATED_DIASTOLIC} ({readings})."
        )
    elif len(elevated_today) == 1:
        severity = _worst(severity, "monitor")
        rationale_parts.append(
            f"One blood pressure reading today ({_fmt_bp(elevated_today[0])}) was at "
            f"or above {ELEVATED_SYSTOLIC}/{ELEVATED_DIASTOLIC}; a single elevated "
            f"reading is worth watching but not yet a two-reading escalation."
        )

    elevated_now = _is_elevated(latest.bp_systolic, latest.bp_diastolic)

    # ── Rule 3/4: severe headache (with or without vision changes) ──
    severe_headache = (
        latest.headache_severity is not None
        and latest.headache_severity >= SEVERE_HEADACHE
    )
    if severe_headache and latest.vision_changes:
        severity = _worst(severity, "escalate_urgent")
        triggered.append(_flag_text(
            plan, "headache", "vision",
            fallback="Severe headache AND vision changes",
        ))
        rationale_parts.append(
            f"A severe headache (rated {latest.headache_severity}/10) together with "
            f"vision changes are warning signs the care plan flags urgently."
        )
    elif severe_headache:
        severity = _worst(severity, "escalate")
        triggered.append(_flag_text(
            plan, "headache", fallback="Severe persistent headache",
        ))
        rationale_parts.append(
            f"A severe headache was reported (rated {latest.headache_severity}/10)."
        )
    elif latest.headache_severity is not None and latest.headache_severity >= 4:
        severity = _worst(severity, "monitor")
        rationale_parts.append(
            f"A moderate headache was reported (rated {latest.headache_severity}/10)."
        )

    # ── Rule 5: new vision changes ──
    if latest.vision_changes and not severe_headache:
        severity = _worst(severity, "escalate")
        triggered.append(_flag_text(
            plan, "vision", fallback="New vision changes",
        ))
        rationale_parts.append("New vision changes were reported.")

    # ── Rule 6: facial/hand swelling with elevated BP ──
    swelling = (latest.swelling_location or "").lower()
    if swelling in ("face", "hands", "hand", "face and hands", "facial"):
        if elevated_now or elevated_today:
            severity = _worst(severity, "escalate")
            triggered.append(_flag_text(
                plan, "swelling", fallback="New facial or hand swelling with elevated BP",
            ))
            rationale_parts.append(
                f"Swelling in the {swelling} was reported alongside an elevated blood "
                f"pressure reading."
            )
        else:
            severity = _worst(severity, "monitor")
            rationale_parts.append(
                f"Swelling in the {swelling} was reported (blood pressure not elevated)."
            )

    # ── Rule 7: decreased / absent fetal movement ──
    movement = (latest.fetal_movement or "").lower()
    if movement and any(w in movement for w in _DECREASED_MOVEMENT_WORDS):
        severity = _worst(severity, "escalate")
        triggered.append(_flag_text(
            plan, "fetal movement", fallback="Decreased or absent fetal movement",
        ))
        rationale_parts.append("Reduced fetal movement was reported compared to baseline.")

    # ── Rule 8: aspirin not taken 2+ consecutive recent days ──
    med_logs = [s for s in ordered if s.medication_taken is not None]
    if len(med_logs) >= 2 and not med_logs[-1].medication_taken and not med_logs[-2].medication_taken:
        severity = _worst(severity, "monitor")
        triggered.append(_flag_text(
            plan, "aspirin", fallback="Low-dose aspirin missed 2+ consecutive days",
        ))
        rationale_parts.append(
            "Low-dose aspirin was not taken on the two most recent check-ins."
        )

    if severity == "ok" and not rationale_parts:
        rationale_parts.append(
            "All readings on the latest check-in are within the care plan's normal range."
        )

    recommended_action = {
        "escalate_urgent": "Contact the patient now; consider same-day clinical evaluation.",
        "escalate": "Review today and reach out to the patient; consider advancing the appointment.",
        "monitor": "No action needed now — keep an eye on this at the next check-in.",
        "ok": "Continue routine monitoring.",
    }[severity]

    return RiskScore(
        patient_id=patient_id,
        timestamp=latest.timestamp,
        severity=severity,
        rationale=" ".join(rationale_parts),
        recommended_action=recommended_action,
        triggered_flags=triggered,
    )
