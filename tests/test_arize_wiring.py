"""CAD-51 — Arize spans wired into orchestrator (dispatch_tool + _fire_judge)."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone

import pytest

from backend.agent import orchestrator
from backend.ingestion.schema import EscalationSummary, RiskScore


NOW = datetime.now(timezone.utc)


def _fake_risk(pid):
    return RiskScore(
        patient_id=pid, timestamp=NOW, severity="ok",
        rationale="All good", recommended_action="continue",
    )


def _fake_esc(pid):
    return EscalationSummary(
        escalation_id="esc-1", patient_id=pid, patient_name="Maria Chen",
        timestamp=NOW, severity="escalate", summary="BP elevated",
        recommended_action="contact",
    )


# ── dispatch_tool records an agent_span ───────────────────────────────────────

def test_dispatch_tool_records_agent_span(monkeypatch):
    """Each successful tool call wraps its result in an agent_span."""
    spans = []

    @contextmanager
    def _fake_span(name, tracer=None, **attrs):
        spans.append({"name": name, "attrs": attrs})
        yield None

    monkeypatch.setattr(orchestrator, "agent_span", _fake_span)
    monkeypatch.setitem(orchestrator.TOOL_REGISTRY, "assess_risk", _fake_risk)

    orchestrator.dispatch_tool("assess_risk", {}, "maria-chen", tracer=object())

    assert any(s["name"] == "tool.assess_risk" for s in spans)
    span = next(s for s in spans if s["name"] == "tool.assess_risk")
    assert span["attrs"]["patient_id"] == "maria-chen"
    assert span["attrs"]["tool_called"] == "assess_risk"


def test_dispatch_tool_span_includes_severity_when_present(monkeypatch):
    spans = []

    @contextmanager
    def _fake_span(name, tracer=None, **attrs):
        spans.append({"name": name, "attrs": attrs})
        yield None

    fake_risk = RiskScore(
        patient_id="maria-chen", timestamp=NOW, severity="escalate",
        rationale="BP elevated", recommended_action="contact",
    )

    monkeypatch.setattr(orchestrator, "agent_span", _fake_span)
    monkeypatch.setitem(orchestrator.TOOL_REGISTRY, "assess_risk", lambda pid: fake_risk)

    orchestrator.dispatch_tool("assess_risk", {}, "maria-chen", tracer=object())

    span = next((s for s in spans if s["name"] == "tool.assess_risk"), None)
    assert span is not None
    assert span["attrs"]["severity"] == "escalate"


# ── _fire_judge is called after escalate_to_clinician ────────────────────────

def test_dispatch_tool_fires_judge_on_escalation(monkeypatch):
    fired = []

    @contextmanager
    def _noop_span(name, tracer=None, **attrs):
        yield None

    monkeypatch.setattr(orchestrator, "agent_span", _noop_span)
    monkeypatch.setattr(orchestrator, "_fire_judge", lambda pid, tr: fired.append(pid))
    monkeypatch.setitem(orchestrator.TOOL_REGISTRY, "escalate_to_clinician", _fake_esc)

    orchestrator.dispatch_tool("escalate_to_clinician", {}, "maria-chen", tracer=object())

    assert "maria-chen" in fired


def test_dispatch_tool_does_not_fire_judge_on_error(monkeypatch):
    fired = []

    @contextmanager
    def _noop_span(name, tracer=None, **attrs):
        yield None

    def _boom(pid):
        raise RuntimeError("Redis down")

    monkeypatch.setattr(orchestrator, "agent_span", _noop_span)
    monkeypatch.setattr(orchestrator, "_fire_judge", lambda pid, tr: fired.append(pid))
    monkeypatch.setitem(orchestrator.TOOL_REGISTRY, "escalate_to_clinician", _boom)

    outcome = orchestrator.dispatch_tool("escalate_to_clinician", {}, "maria-chen", tracer=object())

    assert outcome.is_error
    assert fired == []  # judge not fired on error


# ── tracer=None is safe (no-op path) ─────────────────────────────────────────

def test_dispatch_tool_without_tracer_does_not_crash(monkeypatch):
    monkeypatch.setitem(orchestrator.TOOL_REGISTRY, "assess_risk", _fake_risk)

    outcome = orchestrator.dispatch_tool("assess_risk", {}, "maria-chen", tracer=None)
    assert not outcome.is_error
