"""
Cadence — Maria Chen demo data (CAD-8)

The hero patient, 100% synthetic. This module is PURE: it builds the plan, the
9-day symptom history, and the derived risk timeline as in-memory objects. No
Redis here — `seed_data.py` writes these into Redis using Adit's redis_client.

The 9-day story is engineered for the demo: blood pressure climbs steadily and
crosses the care-plan threshold on the final evening (two readings, 142/91 then
140/90), with headaches recurring on days 3, 6, and 9 (increasing). That makes
detect_pattern light up (BP up-trend + recurring headaches) and classify() return
`escalate` on the latest check-in — exactly the golden-path demo beat.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ..ingestion.schema import (
    Medication,
    ProtocolJSON,
    RedFlag,
    RiskScore,
    SymptomLog,
    Task,
)
from ..risk.classifier import classify

PATIENT_ID = "maria-chen"
PATIENT_NAME = "Maria Chen"
GESTATIONAL_AGE_WEEKS = 29

_PACK = json.loads(
    (Path(__file__).resolve().parents[2] / "packs" / "preeclampsia_risk.json").read_text()
)

# Day 9 (the escalation evening) is "today"; the history runs the 8 days before it.
_DAY9 = datetime(2026, 6, 21, tzinfo=timezone.utc)
_DAY1 = _DAY9 - timedelta(days=8)


def build_plan() -> ProtocolJSON:
    """Maria's parsed care plan — red flags come straight from the preeclampsia pack."""
    return ProtocolJSON(
        patient_id=PATIENT_ID,
        condition=_PACK["condition"],
        gestational_age_weeks=GESTATIONAL_AGE_WEEKS,
        goals=[
            "Keep blood pressure within the care-plan range",
            "Take low-dose aspirin every day",
            "Report warning signs to Cadence promptly",
        ],
        medications=[
            Medication(
                name="Low-dose aspirin",
                dose="81 mg",
                frequency="once daily",
                instructions="Take in the evening with food.",
            )
        ],
        tasks=[
            Task(task="Check blood pressure", frequency="twice daily",
                 instructions="Seated, rested, arm at heart level — morning and evening."),
            Task(task="Daily Cadence check-in", frequency="once daily",
                 instructions="Answer the evening check-in questions."),
        ],
        check_in_cadence_hours=_PACK["check_in_cadence_hours"],
        red_flags=[RedFlag(**rf) for rf in _PACK["red_flags"]],
        patient_context=(
            "Patient of Dr. Reyes (MFM). 29 weeks, first pregnancy, preeclampsia risk. "
            "On low-dose aspirin. History of borderline blood pressure. Lives 40 minutes "
            "from the clinic."
        ),
        created_at=_DAY1,
        last_updated=_DAY9,
    )


# (morning_sys, morning_dia, evening_sys, evening_dia, headache, fetal_movement)
# Steady upward BP; headaches on days 3, 6, 9; aspirin taken every day.
_DAYS: list[tuple[int, int, int, int, int | None, str]] = [
    (118, 76, 116, 75, None, "normal"),   # day 1
    (120, 78, 119, 77, None, "normal"),   # day 2
    (122, 79, 124, 80, 4, "normal"),      # day 3  — first headache
    (126, 82, 125, 81, None, "normal"),   # day 4
    (128, 83, 130, 84, None, "normal"),   # day 5
    (132, 85, 131, 85, 5, "normal"),      # day 6  — headache, worsening
    (134, 86, 136, 87, None, "normal"),   # day 7
    (138, 88, 137, 88, None, "normal"),   # day 8
    (142, 91, 140, 90, 6, "normal"),      # day 9  — crosses threshold, headache
]


def build_symptoms() -> list[SymptomLog]:
    """9 days × 2 readings (morning + evening) of synthetic check-in data."""
    logs: list[SymptomLog] = []
    for i, (m_sys, m_dia, e_sys, e_dia, headache, movement) in enumerate(_DAYS):
        day = _DAY1 + timedelta(days=i)
        logs.append(SymptomLog(
            patient_id=PATIENT_ID,
            timestamp=day.replace(hour=8),
            bp_systolic=m_sys, bp_diastolic=m_dia,
            fetal_movement=movement, medication_taken=True,
            raw_text=f"Morning BP {m_sys}/{m_dia}.",
            notes="Morning reading.",
        ))
        logs.append(SymptomLog(
            patient_id=PATIENT_ID,
            timestamp=day.replace(hour=20),
            bp_systolic=e_sys, bp_diastolic=e_dia,
            headache_severity=headache,
            fetal_movement=movement, medication_taken=True,
            raw_text=(f"Evening BP {e_sys}/{e_dia}."
                      + (f" Headache about {headache}/10." if headache else "")),
            notes="Evening reading." + (" Headache reported." if headache else ""),
        ))
    return logs


def build_risk_timeline(plan: ProtocolJSON, symptoms: list[SymptomLog]) -> list[RiskScore]:
    """
    One RiskScore per day, classifying the history available through that day —
    so the clinician timeline shows risk evolving (ok → monitor → escalate).
    """
    timeline: list[RiskScore] = []
    for i in range(len(_DAYS)):
        day_end = (_DAY1 + timedelta(days=i)).replace(hour=23, minute=59)
        through_day = [s for s in symptoms if s.timestamp <= day_end]
        score = classify(through_day, plan)
        # Stamp the score at that day so the timeline is chronological.
        timeline.append(score.model_copy(update={"timestamp": day_end}))
    return timeline


# Convenience module-level objects for importers (built once).
PLAN = build_plan()
SYMPTOMS = build_symptoms()
RISK_TIMELINE = build_risk_timeline(PLAN, SYMPTOMS)
