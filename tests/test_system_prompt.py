"""
CAD-6 — guard tests for the agent system prompt + rubric.

These assert the acceptance criteria mechanically so the prompt can't silently
drift (e.g. someone hardcodes an old model or drops the no-diagnosis rule).
"""

from __future__ import annotations

from pathlib import Path

PROMPTS = Path(__file__).resolve().parents[1] / "backend" / "agent" / "prompts"
SYSTEM = (PROMPTS / "system.txt").read_text()
RUBRIC = (PROMPTS / "rubrics" / "preeclampsia.txt").read_text()

# Old model ids that must never be hardcoded anywhere in the prompts.
BANNED_MODELS = ["claude-3", "claude-2", "claude-instant", "sonnet-3", "opus-3", "gpt-"]


def test_injects_context_pack_and_tone():
    for token in ("{{patient_context}}", "{{tone}}", "{{daily_questions}}",
                  "{{red_flags}}", "{{patient_name}}", "{{coaching_topics}}"):
        assert token in SYSTEM, f"missing injection token {token}"


def test_hard_blocks_diagnosis():
    low = SYSTEM.lower()
    assert "never diagnose" in low
    assert "constitutional" in low
    assert "preeclampsia" in low  # the explicit "never say you may have preeclampsia" example


def test_instructs_collect_triage_escalate_tooluse():
    low = SYSTEM.lower()
    for phase in ("collect", "triage", "escalate"):
        assert phase in low
    for tool in ("log_symptom", "assess_risk", "detect_pattern", "escalate_to_clinician"):
        assert tool in SYSTEM, f"system prompt should reference {tool}"


def test_uses_current_model_only():
    assert "claude-sonnet-4-6" in SYSTEM
    for bad in BANNED_MODELS:
        assert bad not in SYSTEM.lower(), f"banned/old model id present: {bad}"


def test_rubric_defines_all_four_severities():
    for sev in ("ok", "monitor", "escalate", "escalate_urgent"):
        assert sev in RUBRIC
    # rubric thresholds must match the classifier's
    assert "160" in RUBRIC and "110" in RUBRIC      # severe range
    assert "140" in RUBRIC and "90" in RUBRIC        # elevated
    assert "no black box" in RUBRIC.lower()
