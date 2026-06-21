"""
CAD-36 — offline tests for the de-identification, judge prompt/parse, and the
LLM-as-judge with an injected (fake) model call. No Arize SDK, no network.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from backend.demo import maria_data
from backend.eval.arize_judge import (
    JudgeResult,
    agent_span,
    build_judge_prompt,
    de_identify,
    judge_escalation,
    parse_judge,
    patient_token,
    setup_tracing,
)
from backend.ingestion.schema import EscalationSummary

DAY9 = datetime(2026, 6, 21, tzinfo=timezone.utc)


def _escalation() -> EscalationSummary:
    return EscalationSummary(
        escalation_id="esc-1",
        patient_id="maria-chen",
        patient_name="Maria Chen",
        timestamp=DAY9,
        severity="escalate",
        summary="BP 142/91 and 140/90 this evening; above the care-plan threshold.",
        triggering_readings=["142/91", "140/90"],
        recommended_action="Contact patient; consider advancing the appointment.",
    )


# ── de-identification ──

def test_patient_token_is_stable_and_not_raw():
    t = patient_token("maria-chen")
    assert t == patient_token("maria-chen")          # deterministic
    assert "maria" not in t and t.startswith("pt_")   # not the raw id


def test_de_identify_strips_phi_and_hashes_id():
    safe = de_identify({
        "patient_id": "maria-chen",
        "raw_text": "I have a headache",
        "notes": "evening reading",
        "severity": "escalate",
        "tool_called": "assess_risk",
    })
    assert "patient_id" not in safe and "patient_token" in safe
    assert "raw_text" not in safe and "notes" not in safe   # PHI/free text dropped
    assert safe["severity"] == "escalate"                    # structured fields kept
    assert safe["tool_called"] == "assess_risk"


# ── tracing degrades gracefully ──

def test_setup_tracing_is_strict_by_default():
    # No ARIZE_* env in tests → must RAISE, never silently no-op.
    import pytest
    with pytest.raises(RuntimeError):
        setup_tracing()


def test_setup_tracing_noop_only_as_explicit_optout():
    # The no-op path is allowed ONLY when explicitly requested.
    assert setup_tracing(required=False) is None


def test_agent_span_noops_with_explicit_none_tracer():
    # tracer=None is an explicit opt-out (used by tests), not a silent prod fallback.
    with agent_span("x", tracer=None, patient_id="maria-chen", severity="escalate") as span:
        assert span is None


# ── prompt building + parsing (pure) ──

def test_prompt_includes_thresholds_readings_and_severity():
    prompt = build_judge_prompt(_escalation(), maria_data.SYMPTOMS, maria_data.PLAN)
    assert "142/91" in prompt                       # triggering reading
    assert "140/90" in prompt or "140" in prompt
    assert "escalate" in prompt                       # severity
    assert "BP >= 140" in prompt or "140/90" in prompt  # a red-flag threshold
    assert "{{" not in prompt                          # all tokens rendered


def test_parse_judge_handles_json():
    appropriate, conf, rationale = parse_judge(
        'Here is my verdict: {"appropriate": true, "confidence": 0.97, "rationale": "Two readings >= 140/90."}'
    )
    assert appropriate is True
    assert conf == 0.97
    assert "140/90" in rationale


def test_parse_judge_fallback_yes_no():
    appropriate, conf, _ = parse_judge("YES, appropriate. Confidence 0.9.")
    assert appropriate is True and conf == 0.9
    no_app, _, _ = parse_judge("NO — this was inappropriate.")
    assert no_app is False


def test_parse_judge_clamps_confidence():
    _, conf, _ = parse_judge('{"appropriate": true, "confidence": 1.7, "rationale": "x"}')
    assert conf == 1.0


# ── end-to-end judge with an injected fake model ──

def test_judge_escalation_with_injected_model():
    fake = lambda prompt: '{"appropriate": true, "confidence": 0.97, "rationale": "Met threshold."}'
    result = asyncio.run(judge_escalation(
        _escalation(), maria_data.SYMPTOMS, maria_data.PLAN, complete=fake,
    ))
    assert isinstance(result, JudgeResult)
    assert result.appropriate is True
    assert result.confidence == 0.97
    assert result.patient_token == patient_token("maria-chen")


def test_judge_escalation_supports_async_model():
    async def fake_async(prompt):
        return '{"appropriate": false, "confidence": 0.3, "rationale": "Over-reacted."}'
    result = asyncio.run(judge_escalation(
        _escalation(), maria_data.SYMPTOMS, maria_data.PLAN, complete=fake_async,
    ))
    assert result.appropriate is False
    assert result.confidence == 0.3
