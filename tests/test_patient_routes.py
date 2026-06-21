"""Backend: wire /patient/* endpoints to Redis (kill mocks) — route tests."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.ingestion.schema import (
    ProtocolJSON,
    RedFlag,
    RiskScore,
    SymptomLog,
    VisitSummary,
)

client = TestClient(app)
NOW = datetime.now(timezone.utc)


def _plan(red_flags: list[RedFlag] | None = None) -> ProtocolJSON:
    return ProtocolJSON(
        patient_id="maria-chen",
        condition="high_risk_pregnancy_preeclampsia",
        red_flags=red_flags or [],
        created_at=NOW,
        last_updated=NOW,
    )


def _symptom(systolic: int, diastolic: int, days_ago: float = 0.0) -> SymptomLog:
    from datetime import timedelta
    return SymptomLog(
        patient_id="maria-chen",
        timestamp=NOW - timedelta(days=days_ago),
        bp_systolic=systolic,
        bp_diastolic=diastolic,
    )


def _visit_summary() -> VisitSummary:
    return VisitSummary(
        patient_id="maria-chen",
        generated_at=NOW,
        period_start=NOW,
        period_end=NOW,
        patient_facing="You had a healthy week.",
        clinician_facing="BP stable.",
        conversation_starters=["Ask about aspirin adherence."],
        key_metrics={"check_ins": "3"},
    )


# ── GET /api/patient/watchfor ─────────────────────────────────────────────────

def test_watchfor_returns_plan_red_flags():
    flags = [
        RedFlag(description="BP >= 140/90", severity="escalate", escalation_message="BP above threshold."),
        RedFlag(description="Severe headache", severity="escalate_urgent", escalation_message="Call OB now."),
    ]
    with patch("backend.routes.patient.redis_client.get_plan", return_value=_plan(flags)):
        resp = client.get("/api/patient/watchfor", params={"patient_id": "maria-chen"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["patient_id"] == "maria-chen"
    assert len(data["red_flags"]) == 2
    assert data["red_flags"][0]["description"] == "BP >= 140/90"


def test_watchfor_returns_empty_list_when_no_plan():
    with patch("backend.routes.patient.redis_client.get_plan", return_value=None):
        resp = client.get("/api/patient/watchfor", params={"patient_id": "unknown"})
    assert resp.status_code == 200
    assert resp.json()["red_flags"] == []


def test_watchfor_returns_empty_list_for_plan_with_no_flags():
    with patch("backend.routes.patient.redis_client.get_plan", return_value=_plan([])):
        resp = client.get("/api/patient/watchfor", params={"patient_id": "maria-chen"})
    assert resp.status_code == 200
    assert resp.json()["red_flags"] == []


# ── GET /api/patient/history ──────────────────────────────────────────────────

def test_history_returns_newest_first():
    # oldest-first from Redis (as redis_client.get_symptom_history returns)
    symptoms_oldest_first = [
        _symptom(128, 84, days_ago=2),
        _symptom(135, 88, days_ago=1),
        _symptom(142, 91, days_ago=0),
    ]
    with patch("backend.routes.patient.redis_client.get_symptom_history", return_value=symptoms_oldest_first):
        resp = client.get("/api/patient/history", params={"patient_id": "maria-chen"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["check_in_count"] == 3
    # newest first: 142 should be first
    assert data["entries"][0]["bp_systolic"] == 142


def test_history_counts_flags_correctly():
    symptoms = [
        _symptom(128, 84, days_ago=3),   # ok
        _symptom(138, 88, days_ago=2),   # ok (< 140)
        _symptom(140, 90, days_ago=1),   # flagged (== 140)
        _symptom(142, 91, days_ago=0),   # flagged
    ]
    with patch("backend.routes.patient.redis_client.get_symptom_history", return_value=symptoms):
        resp = client.get("/api/patient/history", params={"patient_id": "maria-chen"})
    data = resp.json()
    assert data["check_in_count"] == 4
    assert data["flags_count"] == 2


def test_history_empty_when_no_data():
    with patch("backend.routes.patient.redis_client.get_symptom_history", return_value=[]):
        resp = client.get("/api/patient/history", params={"patient_id": "new-patient"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["entries"] == []
    assert data["check_in_count"] == 0
    assert data["flags_count"] == 0


# ── GET /api/patient/summary ──────────────────────────────────────────────────

def test_summary_returns_visit_summary():
    vs = _visit_summary()
    with patch("backend.routes.patient.generate_visit_summary", return_value=vs):
        resp = client.get("/api/patient/summary", params={"patient_id": "maria-chen"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["patient_id"] == "maria-chen"
    assert data["visit_summary"]["patient_facing"] == "You had a healthy week."
    assert data["visit_summary"]["conversation_starters"] == ["Ask about aspirin adherence."]


def test_summary_returns_404_when_no_plan():
    with patch(
        "backend.routes.patient.generate_visit_summary",
        side_effect=RuntimeError("No care plan on file for patient 'unknown'."),
    ):
        resp = client.get("/api/patient/summary", params={"patient_id": "unknown"})
    assert resp.status_code == 404
    assert "care plan" in resp.json()["detail"]
