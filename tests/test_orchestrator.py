"""CAD-7 — orchestrator loop tests. No network: a fake Anthropic client is injected."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from backend.agent import orchestrator
from backend.ingestion.schema import RiskScore, SymptomLog


# ── Fake Anthropic streaming client ─────────────────────────────────────────

class _FakeStream:
    def __init__(self, chunks, final):
        self.text_stream = iter(chunks)
        self._final = final

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def get_final_message(self):
        return self._final


class _FakeMessages:
    def __init__(self, rounds):
        self._rounds = list(rounds)
        self.calls = 0

    def stream(self, **kwargs):
        chunks, final = self._rounds[self.calls]
        self.calls += 1
        return _FakeStream(chunks, final)


class _FakeClient:
    def __init__(self, rounds):
        self.messages = _FakeMessages(rounds)


def _tool_use(name, tool_id, tool_input):
    return SimpleNamespace(type="tool_use", name=name, id=tool_id, input=tool_input)


def _text_block(text):
    return SimpleNamespace(type="text", text=text)


def test_multi_tool_turn_streams_final_text(monkeypatch):
    """Round 1: model calls assess_risk. Round 2: model returns final text. Loop must
    dispatch the tool, capture the RiskScore, and stream the final reply."""
    risk = RiskScore(
        patient_id="maria-chen", timestamp=datetime.now(timezone.utc), severity="escalate",
        rationale="BP above threshold on two readings.", recommended_action="Contact patient.",
    )
    monkeypatch.setitem(orchestrator.TOOL_REGISTRY, "assess_risk", lambda pid: risk)

    rounds = [
        (["Let me check that. "], SimpleNamespace(
            stop_reason="tool_use",
            content=[_tool_use("assess_risk", "tu_1", {})],
        )),
        (["Both readings are above your range — I've noted it."], SimpleNamespace(
            stop_reason="end_turn",
            content=[_text_block("Both readings are above your range — I've noted it.")],
        )),
    ]
    monkeypatch.setattr(orchestrator, "_client", lambda: _FakeClient(rounds))

    result = orchestrator.AgentResult()
    chunks = list(orchestrator.stream_agent("maria-chen", "SYS", [{"role": "user", "content": "142/91"}], result))

    assert "".join(chunks) == "Let me check that. Both readings are above your range — I've noted it."
    assert result.text == "".join(chunks)
    assert result.tool_calls == ["assess_risk"]
    assert result.risk == risk
    assert result.flagged is False  # assess_risk alone doesn't flag


def test_escalation_sets_flagged(monkeypatch):
    monkeypatch.setitem(orchestrator.TOOL_REGISTRY, "escalate_to_clinician", lambda pid: SimpleNamespace(
        model_dump_json=lambda: '{"escalation_id":"esc-1"}'))
    rounds = [
        ([""], SimpleNamespace(stop_reason="tool_use", content=[_tool_use("escalate_to_clinician", "tu_1", {})])),
        (["Done — I've let Dr. Reyes know."], SimpleNamespace(
            stop_reason="end_turn", content=[_text_block("Done — I've let Dr. Reyes know.")])),
    ]
    monkeypatch.setattr(orchestrator, "_client", lambda: _FakeClient(rounds))

    result = orchestrator.AgentResult()
    list(orchestrator.stream_agent("maria-chen", "SYS", [{"role": "user", "content": "hi"}], result))
    assert result.flagged is True


def test_dispatch_log_symptom_builds_schema(monkeypatch):
    captured = {}
    def fake_log(pid, symptom):
        captured["pid"] = pid
        captured["symptom"] = symptom
        return symptom
    monkeypatch.setitem(orchestrator.TOOL_REGISTRY, "log_symptom", fake_log)

    out = orchestrator.dispatch_tool("log_symptom", {"bp_systolic": 142, "bp_diastolic": 91}, "maria-chen")
    assert out.is_error is False
    assert isinstance(captured["symptom"], SymptomLog)
    assert captured["symptom"].patient_id == "maria-chen"
    assert captured["symptom"].bp_systolic == 142


def test_stub_tool_error_is_recoverable():
    """A NotImplementedError stub must come back as a recoverable tool error, not crash."""
    # lookup_plan is still a stub (RAG story); it must fail gracefully, not crash the loop.
    out = orchestrator.dispatch_tool("lookup_plan", {"query": "aspirin"}, "maria-chen")
    assert out.is_error is True
    assert "not implemented" in out.content.lower()


def test_patient_id_never_exposed_to_model():
    """Security: the model must not be able to choose patient_id on any tool."""
    for schema in orchestrator.anthropic_tool_schemas():
        props = schema["input_schema"].get("properties", {})
        assert "patient_id" not in props, f"{schema['name']} leaks patient_id to the model"


def test_render_system_prompt_replaces_tokens(monkeypatch, tmp_path):
    template = (
        "[CADENCE AGENT SYSTEM PROMPT — run on model: claude-sonnet-4-6]\n"
        "# ── INJECTION CONTRACT ──\n"
        "# {{patient_name}} etc.\n"
        "\n"
        "Patient: {{patient_name}}, {{gestational_age_weeks}} weeks.\n"
        "Tone: {{tone}}\n"
        "Questions:\n{{daily_questions}}\n"
    )
    pdir = tmp_path / "prompts"
    pdir.mkdir()
    (pdir / "system.txt").write_text(template)
    monkeypatch.setattr(orchestrator, "_PROMPTS_DIR", pdir)

    from backend.ingestion.schema import ProtocolJSON
    now = datetime.now(timezone.utc)
    plan = ProtocolJSON(patient_id="maria-chen", condition="high_risk_pregnancy_preeclampsia",
                        gestational_age_weeks=29, created_at=now, last_updated=now)
    pack = {"patient_tone": "warm and calm", "daily_questions": [{"prompt": "What was your BP?"}]}

    out = orchestrator.render_system_prompt(plan, pack, "Maria")
    assert "Patient: Maria, 29 weeks." in out
    assert "Tone: warm and calm" in out
    assert "- What was your BP?" in out
    assert "{{" not in out  # no unrendered tokens leak
    assert "INJECTION CONTRACT" not in out  # directive/comment header stripped


def test_render_falls_back_to_placeholder(monkeypatch, tmp_path):
    monkeypatch.setattr(orchestrator, "_PROMPTS_DIR", tmp_path / "nope")
    out = orchestrator.render_system_prompt(None, None, None)
    assert "Cadence" in out and "never diagnose" in out.lower()
