"""
End-to-end proof that a self-harm message routes to the clinician.

Stubs only the network edges (the Haiku classifier call + Redis writes) and runs
the REAL orchestrator.respond → safety.classify → escalate_safety path. Asserts:
  1. the agent is short-circuited (patient gets CRISIS_RESPONSE, not an LLM reply),
  2. an EscalationSummary is written to escalations:{id} (the clinician inbox), and
  3. a RiskScore(escalate_urgent) is written to risk_timeline (panel re-ranks).
"""

from __future__ import annotations

import pytest

from backend.agent import orchestrator
from backend.safety import classifier as safety
from backend.escalation import handler
from backend.memory import redis_client


CRISIS_JSON = (
    '{"category":"self_harm","severity":"escalate_urgent","confidence":0.96,'
    '"rationale":"patient expressed intent to end their life"}'
)


@pytest.fixture
def wired(monkeypatch):
    """Stub the classifier's model call (→ crisis) and capture Redis writes."""
    written = {"escalations": [], "risks": [], "published": []}

    # 1. The Haiku classifier returns a crisis verdict (no network).
    monkeypatch.setattr(safety, "_anthropic_complete", lambda _prompt: CRISIS_JSON)

    # 2. Capture what escalate_safety writes; stub the rest of Redis read paths.
    monkeypatch.setattr(redis_client, "get_plan", lambda pid: None)
    monkeypatch.setattr(redis_client, "load_pack_for_condition", lambda c: None, raising=False)
    monkeypatch.setattr(orchestrator, "load_pack_for_condition", lambda c: None)
    monkeypatch.setattr(redis_client, "get_session", lambda pid, sid: [])
    monkeypatch.setattr(redis_client, "write_escalation",
                        lambda pid, esc: written["escalations"].append(esc))
    monkeypatch.setattr(redis_client, "append_risk",
                        lambda pid, score: written["risks"].append(score))
    monkeypatch.setattr(redis_client, "publish_escalation",
                        lambda esc: written["published"].append(esc))
    # Web Push is already a no-op without the module; force it just in case.
    monkeypatch.setattr(handler, "_notify_clinician", lambda esc: None)
    # No tracer (arize not required for the test).
    monkeypatch.setattr(orchestrator, "_TRACER", None)
    monkeypatch.setattr(orchestrator, "_TRACER_INITIALIZED", True)
    return written


def test_self_harm_message_alerts_the_clinician(wired):
    result = orchestrator.respond("maria-chen", "2026-06-21", "I'm gonna kms")

    # 1. Patient is given the calm crisis response — the agent did NOT freelance.
    assert result.text == safety.CRISIS_RESPONSE
    assert result.flagged is True

    # 2. An escalation landed in the clinician inbox (escalations:{id} + WS publish).
    assert len(wired["escalations"]) == 1
    esc = wired["escalations"][0]
    assert esc.severity == "escalate_urgent"
    assert "self" in esc.summary.lower()
    assert len(wired["published"]) == 1  # live WebSocket push to the dashboard

    # 3. A RiskScore was written so the patient tops the risk-ranked panel.
    assert len(wired["risks"]) == 1
    assert wired["risks"][0].severity == "escalate_urgent"


def test_ordinary_message_does_not_escalate(monkeypatch):
    safe_json = '{"category":"none","severity":"ok","confidence":0.9,"rationale":"routine"}'
    monkeypatch.setattr(safety, "_anthropic_complete", lambda _p: safe_json)
    monkeypatch.setattr(orchestrator, "_TRACER", None)
    monkeypatch.setattr(orchestrator, "_TRACER_INITIALIZED", True)
    monkeypatch.setattr(redis_client, "get_plan", lambda pid: None)
    monkeypatch.setattr(orchestrator, "load_pack_for_condition", lambda c: None)
    monkeypatch.setattr(redis_client, "get_session", lambda pid, sid: [])

    calls = []
    monkeypatch.setattr(handler, "escalate_safety", lambda pid, v: calls.append(v))
    # Stub the agent loop so no real Claude call happens for the safe path.
    monkeypatch.setattr(orchestrator, "stream_agent",
                        lambda *a, **k: iter(()))

    result = orchestrator.respond("maria-chen", "2026-06-21", "my bp was 118/76 today")
    assert calls == []          # no safety escalation
    assert result.flagged is False
