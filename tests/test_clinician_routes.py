"""CAD-24 / CAD-26 / CAD-29 — clinician routes. Redis + tools monkeypatched (no network)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.agent import tools
from backend.memory import redis_client
from backend.routes import clinician as clinician_route
from backend.ingestion.schema import (
    EscalationSummary,
    PatternAlert,
    RiskScore,
    SymptomLog,
)

NOW = datetime.now(timezone.utc)


def _clinician_client() -> TestClient:
    c = TestClient(app)
    c.cookies.set("cadence_role", "clinician")
    c.cookies.set("cadence_clinician_id", "dr-reyes")
    return c


def _risk(pid, severity, mins_ago=0, flags=None):
    return RiskScore(
        patient_id=pid, timestamp=NOW - timedelta(minutes=mins_ago),
        severity=severity, rationale=f"{severity} rationale",
        recommended_action="act", triggered_flags=flags or [],
    )


@pytest.fixture
def store(monkeypatch):
    risk = {
        "maria-chen": [_risk("maria-chen", "escalate", flags=["BP >= 140/90 on two readings"])],
        "aisha-okoro": [_risk("aisha-okoro", "monitor")],
        "jordan-lee": [],  # no risk scores -> defaults to ok
    }
    symptoms = {
        "maria-chen": [SymptomLog(patient_id="maria-chen", timestamp=NOW, bp_systolic=142, bp_diastolic=91)],
        "aisha-okoro": [SymptomLog(patient_id="aisha-okoro", timestamp=NOW - timedelta(hours=2), bp_systolic=128, bp_diastolic=84)],
        "jordan-lee": [],
    }
    escalations = {
        "maria-chen": [EscalationSummary(
            escalation_id="esc-1", patient_id="maria-chen", patient_name="Maria Chen",
            timestamp=NOW, severity="escalate", summary="BP 142/91 and 140/90",
            recommended_action="contact")],
        "aisha-okoro": [], "jordan-lee": [],
    }
    monkeypatch.setattr(redis_client, "scan_patient_ids", lambda: ["maria-chen", "aisha-okoro", "jordan-lee"])
    monkeypatch.setattr(redis_client, "get_risk_timeline", lambda pid: risk.get(pid, []))
    monkeypatch.setattr(redis_client, "get_symptom_history", lambda pid: symptoms.get(pid, []))
    monkeypatch.setattr(redis_client, "get_escalations", lambda pid: escalations.get(pid, []))
    return {"risk": risk, "symptoms": symptoms, "escalations": escalations}


# ── CAD-24: panel ────────────────────────────────────────────────────────────

def test_panel_ranks_highest_risk_first(store):
    r = _clinician_client().get("/api/clinician/panel")
    assert r.status_code == 200
    rows = r.json()["patients"]
    assert [p["patient_id"] for p in rows] == ["maria-chen", "aisha-okoro", "jordan-lee"]
    assert rows[0]["severity"] == "escalate"
    assert rows[0]["headline"] == "BP >= 140/90 on two readings"
    assert rows[2]["severity"] == "ok"  # jordan has no risk scores


def test_panel_requires_clinician_role(store):
    # patient cookie -> 403
    c = TestClient(app)
    c.cookies.set("cadence_role", "patient")
    c.cookies.set("cadence_patient_id", "maria-chen")
    assert c.get("/api/clinician/panel").status_code == 403


# ── CAD-26: patient detail ───────────────────────────────────────────────────

def test_patient_detail_timeline_patterns_risk(store, monkeypatch):
    monkeypatch.setattr(tools, "detect_pattern", lambda pid: [
        PatternAlert(patient_id=pid, title="BP trending up 4 days", detail="…", metric="bp_systolic")])
    monkeypatch.setattr(tools, "generate_visit_summary", lambda pid: (_ for _ in ()).throw(RuntimeError("no plan")))

    r = _clinician_client().get("/api/clinician/patient/maria-chen")
    assert r.status_code == 200
    body = r.json()
    assert body["patient_name"] == "Maria Chen"
    assert body["current_risk"]["severity"] == "escalate"
    assert len(body["timeline"]) == 1 and body["timeline"][0]["bp_systolic"] == 142
    assert body["patterns"][0]["title"] == "BP trending up 4 days"
    assert body["visit_summary"] is None  # generate_visit_summary raised -> graceful None


def test_patient_detail_pattern_failure_is_graceful(store, monkeypatch):
    monkeypatch.setattr(tools, "detect_pattern", lambda pid: (_ for _ in ()).throw(RuntimeError("boom")))
    monkeypatch.setattr(tools, "generate_visit_summary", lambda pid: (_ for _ in ()).throw(RuntimeError("no plan")))
    r = _clinician_client().get("/api/clinician/patient/maria-chen")
    assert r.status_code == 200
    assert r.json()["patterns"] == []


# ── CAD-29: escalations REST ─────────────────────────────────────────────────

def test_escalations_newest_first(store):
    r = _clinician_client().get("/api/clinician/escalations")
    assert r.status_code == 200
    escs = r.json()["escalations"]
    assert len(escs) == 1
    assert escs[0]["escalation_id"] == "esc-1"


# ── actions ──────────────────────────────────────────────────────────────────

def test_action_message_and_note(store, monkeypatch):
    pushed = []
    class _FakeClient:
        def rpush(self, key, val):
            pushed.append((key, val))
    monkeypatch.setattr(redis_client, "get_client", lambda: _FakeClient())

    c = _clinician_client()
    assert c.post("/api/clinician/action", json={"patient_id": "maria-chen", "action": "message", "content": "Hi Maria"}).json()["ok"]
    assert c.post("/api/clinician/action", json={"patient_id": "maria-chen", "action": "note", "content": "advance appt"}).json()["ok"]
    assert pushed[0][0] == redis_client.messages_key("maria-chen")
    assert pushed[1][0] == redis_client.notes_key("maria-chen")


# ── WS: live escalation push ─────────────────────────────────────────────────

def test_ws_pushes_published_escalation(store, monkeypatch):
    esc = EscalationSummary(
        escalation_id="esc-live", patient_id="maria-chen", patient_name="Maria Chen",
        timestamp=NOW, severity="escalate", summary="live one", recommended_action="contact")

    class _FakePubSub:
        def __init__(self):
            self._sent = False
        def get_message(self, ignore_subscribe_messages=True, timeout=1.0):
            if not self._sent:
                self._sent = True
                return {"type": "message", "data": esc.model_dump_json()}
            return None
        def close(self):
            pass

    monkeypatch.setattr(redis_client, "escalation_pubsub", lambda: _FakePubSub())

    with TestClient(app).websocket_connect("/ws/escalations") as ws:
        import json
        payload = json.loads(ws.receive_text())
        assert payload["escalation_id"] == "esc-live"
