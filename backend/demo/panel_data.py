"""
Cadence — Multi-patient panel seed (CAD-38)

The "breadth" pass that pairs with the Maria "depth" record (CAD-8). Seeds a roster
of synthetic patients so the clinician panel actually ranks 50 → 3 instead of showing
a single row.

PURE: builds each patient as (plan, symptoms, risk_timeline) in memory. No Redis here
— seed_data.py writes them. The clinician panel route reads risk_timeline (latest
entry → severity + headline) and symptoms (last check-in), and derives the display
name from the patient_id ("rosa-martinez" → "Rosa Martinez").

NO HAND-FAKED RISK: every patient's risk_timeline is computed by the real classify()
from their symptoms, so the panel severities are genuine engine output, not literals.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ..ingestion.schema import Medication, ProtocolJSON, RedFlag, RiskScore, SymptomLog
from ..risk.classifier import classify

_PACK = json.loads(
    (Path(__file__).resolve().parents[2] / "packs" / "preeclampsia_risk.json").read_text()
)
_RED_FLAGS = [RedFlag(**rf) for rf in _PACK["red_flags"]]

# Roster is anchored a few days before "today" so check-ins look recent.
_TODAY = datetime(2026, 6, 21, tzinfo=timezone.utc)


def _plan(patient_id: str, ga_weeks: int) -> ProtocolJSON:
    return ProtocolJSON(
        patient_id=patient_id,
        condition=_PACK["condition"],
        gestational_age_weeks=ga_weeks,
        medications=[Medication(name="Low-dose aspirin", dose="81 mg", frequency="once daily")],
        check_in_cadence_hours=_PACK["check_in_cadence_hours"],
        red_flags=_RED_FLAGS,
        patient_context=f"Synthetic panel patient, {ga_weeks} weeks, preeclampsia surveillance.",
        created_at=_TODAY - timedelta(days=10),
        last_updated=_TODAY,
    )


# Each spec: id, gestational age, and the LATEST-day clinical picture that drives
# the (real, classify-computed) severity. `days_ago` staggers last check-in so the
# panel's tie-break (most recent first within a severity) is exercised.
# Target severity is documented for review; it is asserted in tests, not hardcoded.
_SPECS: list[dict] = [
    # ── escalate_urgent ──
    dict(id="priya-anand", ga=33, days_ago=0, target="escalate_urgent",
         latest=dict(bp_systolic=168, bp_diastolic=114)),                       # severe range
    # ── escalate ──
    dict(id="rosa-martinez", ga=31, days_ago=0, target="escalate",
         two_readings=[(144, 92), (141, 90)]),                                  # two >=140/90
    dict(id="ana-okafor", ga=29, days_ago=1, target="escalate",
         latest=dict(bp_systolic=122, bp_diastolic=78, fetal_movement="decreased")),
    # ── monitor ──
    dict(id="chloe-bennett", ga=27, days_ago=0, target="monitor",
         latest=dict(bp_systolic=142, bp_diastolic=90)),                        # single elevated
    dict(id="leah-kim", ga=28, days_ago=2, target="monitor",
         latest=dict(bp_systolic=126, bp_diastolic=82, headache_severity=5)),   # moderate headache
    dict(id="fatima-hassan", ga=26, days_ago=1, target="monitor",
         missed_aspirin=True,
         latest=dict(bp_systolic=124, bp_diastolic=80)),                        # 2-day nonadherence
    # ── ok ──
    dict(id="grace-nguyen", ga=24, days_ago=0, target="ok"),
    dict(id="sofia-rossi", ga=30, days_ago=1, target="ok"),
    dict(id="amara-diallo", ga=22, days_ago=2, target="ok"),
    dict(id="mei-tanaka", ga=35, days_ago=0, target="ok"),
    dict(id="hannah-cohen", ga=19, days_ago=3, target="ok"),
    dict(id="jade-thompson", ga=32, days_ago=1, target="ok"),
]


def _normal_evening(day: datetime) -> dict:
    return dict(bp_systolic=118, bp_diastolic=76, fetal_movement="normal", medication_taken=True)


def _build_symptoms(spec: dict) -> list[SymptomLog]:
    """A short, realistic history ending `days_ago` before today."""
    pid = spec["id"]
    end = _TODAY - timedelta(days=spec.get("days_ago", 0))
    logs: list[SymptomLog] = []

    # Two calm prior days so trends/last-check-in look real.
    for d in (2, 1):
        day = end - timedelta(days=d)
        logs.append(SymptomLog(patient_id=pid, timestamp=day.replace(hour=20),
                               **_normal_evening(day)))

    if spec.get("missed_aspirin"):  # override adherence on the two prior days
        logs[0] = logs[0].model_copy(update={"medication_taken": False})
        logs[1] = logs[1].model_copy(update={"medication_taken": False})

    if "two_readings" in spec:
        (ms, md), (es, ed) = spec["two_readings"]
        logs.append(SymptomLog(patient_id=pid, timestamp=end.replace(hour=8),
                               bp_systolic=ms, bp_diastolic=md, medication_taken=True))
        logs.append(SymptomLog(patient_id=pid, timestamp=end.replace(hour=20),
                               bp_systolic=es, bp_diastolic=ed, medication_taken=True))
    else:
        latest = spec.get("latest") or _normal_evening(end)
        latest.setdefault("medication_taken", not spec.get("missed_aspirin", False))
        logs.append(SymptomLog(patient_id=pid, timestamp=end.replace(hour=20), **latest))

    return logs


def _build_risk_timeline(plan: ProtocolJSON, symptoms: list[SymptomLog]) -> list[RiskScore]:
    """Current risk computed by the real classifier (not hardcoded)."""
    score = classify(symptoms, plan)
    return [score.model_copy(update={"timestamp": symptoms[-1].timestamp})]


def build_panel_patients() -> list[tuple[ProtocolJSON, list[SymptomLog], list[RiskScore]]]:
    """All synthetic panel patients as (plan, symptoms, risk_timeline) tuples."""
    out = []
    for spec in _SPECS:
        plan = _plan(spec["id"], spec["ga"])
        symptoms = _build_symptoms(spec)
        timeline = _build_risk_timeline(plan, symptoms)
        out.append((plan, symptoms, timeline))
    return out


PANEL_PATIENTS = build_panel_patients()
