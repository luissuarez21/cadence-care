"""CAD-18 — Web Push: backend/notifications/push.py + /api/push/subscribe route."""

from __future__ import annotations

import json
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.memory import redis_client
from backend.notifications import push as push_module
from backend.ingestion.schema import EscalationSummary
from datetime import datetime, timezone


# ── /api/push/subscribe ──────────────────────────────────────────────────────

def test_subscribe_stores_in_redis(monkeypatch):
    stored = {}

    def _fake_save(clinician_id, subscription):
        stored[clinician_id] = subscription

    monkeypatch.setattr(redis_client, "save_push_subscription", _fake_save)

    c = TestClient(app)
    sub = {"endpoint": "https://push.example/abc", "keys": {"auth": "aaa", "p256dh": "bbb"}}
    r = c.post("/api/push/subscribe", json={"clinician_id": "dr-reyes", "subscription": sub})
    assert r.status_code == 200
    assert r.json()["ok"] is True
    assert stored["dr-reyes"]["endpoint"] == "https://push.example/abc"


# ── notify_escalation — no VAPID keys → skips gracefully ────────────────────

def test_notify_escalation_skips_when_no_vapid_keys(monkeypatch):
    monkeypatch.delenv("VAPID_PRIVATE_KEY", raising=False)
    monkeypatch.delenv("VAPID_PUBLIC_KEY", raising=False)

    esc = EscalationSummary(
        escalation_id="esc-test", patient_id="maria-chen", patient_name="Maria Chen",
        timestamp=datetime.now(timezone.utc), severity="escalate",
        summary="BP elevated", recommended_action="contact",
    )
    # Should return without error even when keys are absent
    push_module.notify_escalation(esc)


# ── notify_escalation — with VAPID keys → fans out to subscriptions ──────────

def test_notify_escalation_fans_out_to_all_subscriptions(monkeypatch):
    monkeypatch.setenv("VAPID_PRIVATE_KEY", "fake-private-key")
    monkeypatch.setenv("VAPID_PUBLIC_KEY", "fake-public-key")
    monkeypatch.setenv("VAPID_SUBJECT", "mailto:test@example.com")

    sub1 = {"endpoint": "https://push.example/1", "keys": {"auth": "a", "p256dh": "b"}}
    sub2 = {"endpoint": "https://push.example/2", "keys": {"auth": "c", "p256dh": "d"}}

    # Fake redis client: scan_iter returns two keys, get returns subscriptions
    class _FakeRedis:
        def scan_iter(self, match=None):
            return ["push_subscriptions:dr-reyes", "push_subscriptions:dr-smith"]

        def get(self, key):
            if key == "push_subscriptions:dr-reyes":
                return json.dumps(sub1)
            return json.dumps(sub2)

    monkeypatch.setattr(redis_client, "get_client", lambda: _FakeRedis())

    sent = []
    monkeypatch.setattr(push_module, "send_push", lambda sub: sent.append(sub["endpoint"]))

    esc = EscalationSummary(
        escalation_id="esc-fan", patient_id="maria-chen", patient_name="Maria Chen",
        timestamp=datetime.now(timezone.utc), severity="escalate",
        summary="BP elevated", recommended_action="contact",
    )
    push_module.notify_escalation(esc)

    assert "https://push.example/1" in sent
    assert "https://push.example/2" in sent


# ── notify_escalation — failed push on one subscription doesn't block others ─

def test_notify_escalation_continues_after_one_failure(monkeypatch):
    monkeypatch.setenv("VAPID_PRIVATE_KEY", "fake-private-key")
    monkeypatch.setenv("VAPID_PUBLIC_KEY", "fake-public-key")

    sub = {"endpoint": "https://push.example/good", "keys": {"auth": "a", "p256dh": "b"}}

    class _FakeRedis:
        def scan_iter(self, match=None):
            return ["push_subscriptions:bad", "push_subscriptions:good"]

        def get(self, key):
            if key == "push_subscriptions:bad":
                return json.dumps({"endpoint": "https://push.example/bad"})
            return json.dumps(sub)

    monkeypatch.setattr(redis_client, "get_client", lambda: _FakeRedis())

    sent = []

    def _fake_send(s):
        if s["endpoint"] == "https://push.example/bad":
            raise RuntimeError("push failed")
        sent.append(s["endpoint"])

    monkeypatch.setattr(push_module, "send_push", _fake_send)

    esc = EscalationSummary(
        escalation_id="esc-fault", patient_id="maria-chen", patient_name="Maria Chen",
        timestamp=datetime.now(timezone.utc), severity="escalate",
        summary="BP elevated", recommended_action="contact",
    )
    push_module.notify_escalation(esc)

    # Good subscription still got notified despite bad one failing
    assert "https://push.example/good" in sent
