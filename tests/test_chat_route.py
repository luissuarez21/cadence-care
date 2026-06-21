"""CAD-17 — POST /api/chat/message. Orchestrator + Redis mocked (no network)."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.agent import orchestrator
from backend.memory import redis_client
from backend.routes import chat as chat_route
from backend.ingestion.schema import ChatMessage, RiskScore

client = TestClient(app)


@pytest.fixture
def captured(monkeypatch):
    """Capture persisted turns; stub the orchestrator with a scripted reply."""
    store: dict[str, list[ChatMessage]] = {}

    def fake_append(pid, sid, msg):
        store.setdefault(f"{pid}:{sid}", []).append(msg)
        return msg

    def fake_get_session(pid, sid):
        return list(store.get(f"{pid}:{sid}", []))

    monkeypatch.setattr(redis_client, "append_message", fake_append)
    monkeypatch.setattr(redis_client, "get_session", fake_get_session)
    return store


def _ok_orchestrator(monkeypatch, *, flagged=False, risk=None, text="Thanks, noted!"):
    monkeypatch.setattr(
        orchestrator, "respond",
        lambda pid, sid, msg: SimpleNamespace(text=text, flagged=flagged, risk=risk),
    )


def test_message_returns_reply_and_persists_both_turns(captured, monkeypatch):
    _ok_orchestrator(monkeypatch, text="Got it, Maria.")
    r = client.post("/api/chat/message", json={"patient_id": "maria-chen", "message": "142/91"})
    assert r.status_code == 200
    body = r.json()
    assert body["reply"] == "Got it, Maria."
    assert body["flagged"] is False

    sid = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    turns = captured[f"maria-chen:{sid}"]
    assert [t.sender for t in turns] == ["patient", "cadence"]
    assert turns[0].text == "142/91"
    assert turns[1].text == "Got it, Maria."


def test_flag_and_risk_passed_through(captured, monkeypatch):
    risk = RiskScore(patient_id="maria-chen", timestamp=datetime.now(timezone.utc),
                     severity="escalate", rationale="BP above threshold.",
                     recommended_action="Contact patient.")
    _ok_orchestrator(monkeypatch, flagged=True, risk=risk)
    r = client.post("/api/chat/message", json={"patient_id": "maria-chen", "message": "142/91"})
    body = r.json()
    assert body["flagged"] is True
    assert body["risk"]["severity"] == "escalate"
    # the cadence turn is marked flagged when persisted
    sid = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    assert captured[f"maria-chen:{sid}"][1].flagged is True


def test_orchestrator_failure_is_demo_safe(captured, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("model down")
    monkeypatch.setattr(orchestrator, "respond", boom)
    r = client.post("/api/chat/message", json={"patient_id": "maria-chen", "message": "hi"})
    assert r.status_code == 200
    assert "trouble" in r.json()["reply"].lower()
    assert r.json()["flagged"] is False
    # turn still recorded
    sid = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    assert len(captured[f"maria-chen:{sid}"]) == 2


def _client_with_cookies(**cookies) -> TestClient:
    c = TestClient(app)
    for k, v in cookies.items():
        c.cookies.set(k, v)
    return c


def test_clinician_cookie_is_forbidden(captured, monkeypatch):
    _ok_orchestrator(monkeypatch)
    c = _client_with_cookies(cadence_role="clinician", cadence_clinician_id="dr-reyes")
    r = c.post("/api/chat/message", json={"patient_id": "maria-chen", "message": "hi"})
    assert r.status_code == 403


def test_authenticated_patient_cannot_touch_another_patient(captured, monkeypatch):
    _ok_orchestrator(monkeypatch)
    c = _client_with_cookies(cadence_role="patient", cadence_patient_id="maria-chen")
    r = c.post("/api/chat/message", json={"patient_id": "someone-else", "message": "hi"})
    assert r.status_code == 403


def test_history_reads_session(captured, monkeypatch):
    _ok_orchestrator(monkeypatch)
    client.post("/api/chat/message", json={"patient_id": "maria-chen", "message": "hello"})
    r = client.get("/api/chat/history", params={"patient_id": "maria-chen"})
    assert r.status_code == 200
    msgs = r.json()["messages"]
    assert msgs[0]["sender"] == "patient" and msgs[0]["text"] == "hello"
