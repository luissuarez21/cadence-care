"""
CAD-16 — unit tests for the pure visit-summary generator.

No Redis/server: build sample logs (+ optional risk timeline) and assert both
variants come back populated with the required fields.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from backend.ingestion.schema import ProtocolJSON, RedFlag, RiskScore, SymptomLog
from backend.summaries.visit_summary import summarize

PACK = json.loads(
    (Path(__file__).resolve().parents[1] / "packs" / "preeclampsia_risk.json").read_text()
)
PATIENT = "maria-chen"
BASE = datetime(2026, 6, 12, 8, 0, tzinfo=timezone.utc)


def _plan() -> ProtocolJSON:
    return ProtocolJSON(
        patient_id=PATIENT,
        condition=PACK["condition"],
        gestational_age_weeks=29,
        red_flags=[RedFlag(**rf) for rf in PACK["red_flags"]],
        patient_context="Patient of Dr. Reyes (MFM). Low-dose aspirin daily.",
        created_at=BASE,
        last_updated=BASE,
    )


def _day(n: int, **fields) -> SymptomLog:
    return SymptomLog(patient_id=PATIENT, timestamp=BASE.replace(day=12 + n), **fields)


def _sample_logs() -> list[SymptomLog]:
    return [
        _day(0, bp_systolic=124, bp_diastolic=80, headache_severity=0,
             fetal_movement="normal", medication_taken=True),
        _day(1, bp_systolic=128, bp_diastolic=82, headache_severity=4,
             fetal_movement="normal", medication_taken=True),
        _day(2, bp_systolic=134, bp_diastolic=86, headache_severity=5,
             fetal_movement="normal", medication_taken=True),
        _day(3, bp_systolic=142, bp_diastolic=91, headache_severity=6,
             swelling_location="face", fetal_movement="normal", medication_taken=True),
    ]


def test_both_variants_populated():
    summary = summarize(_sample_logs(), [], _plan())
    assert summary.patient_id == PATIENT
    assert summary.patient_facing.strip()
    assert summary.clinician_facing.strip()
    assert summary.conversation_starters          # non-empty list
    assert summary.key_metrics                    # non-empty dict


def test_period_and_metrics_make_sense():
    summary = summarize(_sample_logs(), [], _plan())
    assert summary.period_start < summary.period_end
    assert summary.key_metrics["check_ins"] == "4"
    assert "avg_bp" in summary.key_metrics
    assert summary.key_metrics["peak_bp"] == "142/91"


def test_patient_voice_is_non_clinical_and_safe():
    summary = summarize(_sample_logs(), [], _plan())
    text = summary.patient_facing.lower()
    # The patient voice must never diagnose; it explicitly disclaims diagnosis.
    assert "not a diagnosis" in text
    # mentions the OB pulled from patient_context
    assert "dr. reyes" in summary.patient_facing.lower()


def test_clinician_voice_has_signal():
    summary = summarize(_sample_logs(), [], _plan())
    c = summary.clinician_facing.lower()
    assert "bp" in c or "blood pressure" in c
    assert "risk" in c
    # the rising BP series should surface as a trend
    assert "trend" in c or "trending" in c


def test_conversation_starters_reflect_data():
    summary = summarize(_sample_logs(), [], _plan())
    joined = " ".join(summary.conversation_starters).lower()
    assert "headache" in joined       # headaches were present
    assert "bp" in joined or "re-check" in joined


def test_uses_risk_timeline_when_provided():
    risk = RiskScore(
        patient_id=PATIENT, timestamp=BASE.replace(day=15),
        severity="escalate", rationale="Two readings >= 140/90.",
        recommended_action="Contact patient.", triggered_flags=["BP >= 140/90 on two readings"],
    )
    summary = summarize(_sample_logs(), [risk], _plan())
    assert summary.key_metrics["current_risk"] == "escalate"


def test_empty_logs_returns_safe_placeholder():
    summary = summarize([], [], _plan())
    assert summary.patient_facing.strip()
    assert summary.clinician_facing.strip()
    assert summary.conversation_starters == []
    assert summary.key_metrics == {}
