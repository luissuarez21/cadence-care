"""
CAD-13 — unit tests for the pure risk classifier.

No Redis, no server, no network: build hardcoded SymptomLogs + a ProtocolJSON
(loaded from the real preeclampsia pack) and assert the severity decision.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from backend.ingestion.schema import ProtocolJSON, RedFlag, SymptomLog
from backend.risk.classifier import classify

PACK = json.loads(
    (Path(__file__).resolve().parents[1] / "packs" / "preeclampsia_risk.json").read_text()
)

PATIENT = "maria-chen"
DAY = datetime(2026, 6, 21, tzinfo=timezone.utc)


def _plan() -> ProtocolJSON:
    """Build a ProtocolJSON carrying the real pack red flags."""
    return ProtocolJSON(
        patient_id=PATIENT,
        condition=PACK["condition"],
        gestational_age_weeks=29,
        red_flags=[RedFlag(**rf) for rf in PACK["red_flags"]],
        created_at=DAY,
        last_updated=DAY,
    )


def _log(hour: int, **fields) -> SymptomLog:
    return SymptomLog(
        patient_id=PATIENT,
        timestamp=DAY.replace(hour=hour),
        **fields,
    )


# ── Required AC cases: escalate on high BP, monitor on borderline, ok on normal ──

def test_normal_readings_are_ok():
    logs = [_log(8, bp_systolic=118, bp_diastolic=76, headache_severity=0,
                 fetal_movement="normal", medication_taken=True)]
    score = classify(logs, _plan())
    assert score.severity == "ok"
    assert score.triggered_flags == []
    assert score.rationale  # never a black box


def test_two_elevated_readings_escalate():
    logs = [
        _log(8, bp_systolic=142, bp_diastolic=91),
        _log(20, bp_systolic=140, bp_diastolic=90),
    ]
    score = classify(logs, _plan())
    assert score.severity == "escalate"
    assert score.triggered_flags
    assert "142/91" in score.rationale


def test_single_borderline_reading_is_monitor():
    logs = [_log(8, bp_systolic=142, bp_diastolic=91)]
    score = classify(logs, _plan())
    assert score.severity == "monitor"


# ── Extra safety cases ──

def test_severe_bp_is_urgent():
    logs = [_log(8, bp_systolic=165, bp_diastolic=112)]
    score = classify(logs, _plan())
    assert score.severity == "escalate_urgent"


def test_severe_headache_with_vision_is_urgent():
    logs = [_log(8, bp_systolic=120, bp_diastolic=78,
                 headache_severity=8, vision_changes=True)]
    score = classify(logs, _plan())
    assert score.severity == "escalate_urgent"
    assert "8/10" in score.rationale


def test_decreased_fetal_movement_escalates():
    logs = [_log(8, bp_systolic=118, bp_diastolic=76, fetal_movement="decreased")]
    score = classify(logs, _plan())
    assert score.severity == "escalate"


def test_face_swelling_with_elevated_bp_escalates():
    logs = [_log(8, bp_systolic=144, bp_diastolic=92, swelling_location="face")]
    score = classify(logs, _plan())
    assert score.severity == "escalate"


def test_missed_aspirin_two_days_is_monitor():
    logs = [
        _log(8, bp_systolic=118, bp_diastolic=76, medication_taken=False),
        _log(9, bp_systolic=120, bp_diastolic=78, medication_taken=False),
    ]
    # second log is a different "day" only by hour; use distinct days for realism
    logs[0] = logs[0].model_copy(update={"timestamp": DAY.replace(day=20, hour=8)})
    score = classify(logs, _plan())
    assert score.severity == "monitor"


def test_no_symptoms_is_ok():
    score = classify([], _plan())
    assert score.severity == "ok"
    assert score.patient_id == PATIENT


def test_worst_severity_wins():
    # borderline BP (monitor) + severe headache+vision (urgent) → urgent
    logs = [_log(8, bp_systolic=142, bp_diastolic=91,
                 headache_severity=9, vision_changes=True)]
    score = classify(logs, _plan())
    assert score.severity == "escalate_urgent"
