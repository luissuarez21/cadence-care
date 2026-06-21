"""Semantic safety layer — pure prompt build, parse, and gating. No network."""

from __future__ import annotations

from backend.safety import classifier as safety
from backend.ingestion.schema import SafetyVerdict


def _runner(payload: str):
    """An injected 'model call' that returns a fixed raw string."""
    return lambda _prompt: payload


# ── parse_verdict ────────────────────────────────────────────────────────────

def test_parses_crisis_json():
    v = safety.parse_verdict(
        '{"category":"self_harm","severity":"escalate_urgent","confidence":0.95,'
        '"rationale":"states wanting to die"}'
    )
    assert v.category == "self_harm"
    assert v.severity == "escalate_urgent"
    assert v.confidence == 0.95


def test_parses_json_embedded_in_prose():
    v = safety.parse_verdict('Sure: {"category":"abuse","severity":"escalate_urgent"} done')
    assert v.category == "abuse"
    assert v.severity == "escalate_urgent"


def test_malformed_fails_open_to_safe():
    # A transient classifier failure must never fabricate a crisis.
    assert safety.parse_verdict("not json at all").category == "none"
    assert safety.parse_verdict("").severity == "ok"


def test_invalid_category_coerced_to_none():
    v = safety.parse_verdict('{"category":"banana","severity":"escalate"}')
    assert v.category == "none"


def test_confidence_clamped():
    assert safety.parse_verdict('{"category":"none","confidence":5}').confidence == 1.0
    assert safety.parse_verdict('{"category":"none","confidence":-2}').confidence == 0.0


def test_real_category_cannot_be_ok_or_monitor():
    # Safety invariant: a real category is forced to at least 'escalate'.
    v = safety.parse_verdict('{"category":"abuse","severity":"ok"}')
    assert v.severity == "escalate"
    v2 = safety.parse_verdict('{"category":"medical_emergency","severity":"monitor"}')
    assert v2.severity == "escalate"


# ── gating helpers ────────────────────────────────────────────────────────────

def test_is_escalating_and_short_circuit():
    urgent = SafetyVerdict(category="self_harm", severity="escalate_urgent")
    distress = SafetyVerdict(category="acute_distress", severity="escalate")
    safe = SafetyVerdict()

    assert safety.is_escalating(urgent) and safety.is_short_circuit(urgent)
    # 'escalate' (not urgent) routes to the clinician but does NOT short-circuit.
    assert safety.is_escalating(distress) and not safety.is_short_circuit(distress)
    assert not safety.is_escalating(safe) and not safety.is_short_circuit(safe)


# ── classify (injected runner; traces no-op without a tracer) ─────────────────

def test_classify_crisis_via_injected_runner():
    v = safety.classify(
        "i want to kms",
        complete=_runner('{"category":"self_harm","severity":"escalate_urgent","confidence":0.9}'),
        patient_id="maria-chen",
    )
    assert safety.is_short_circuit(v)


def test_classify_swallows_model_errors_as_safe():
    def boom(_prompt):
        raise RuntimeError("model down")

    v = safety.classify("hello", complete=boom, patient_id="maria-chen")
    assert v.category == "none" and v.severity == "ok"
