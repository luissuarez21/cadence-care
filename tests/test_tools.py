"""CAD-12 + CAD-15 — tool wiring + escalation handler. Redis is monkeypatched (no network)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from backend.agent import tools
from backend.escalation import handler
from backend.memory import redis_client
from backend.ingestion.schema import (
    Medication,
    ProtocolJSON,
    RedFlag,
    RiskScore,
    SymptomLog,
)

NOW = datetime.now(timezone.utc)
PID = "maria-chen"


def _plan() -> ProtocolJSON:
    return ProtocolJSON(
        patient_id=PID,
        condition="high_risk_pregnancy_preeclampsia",
        gestational_age_weeks=29,
        medications=[Medication(name="Low-dose aspirin", dose="81mg", frequency="daily")],
        red_flags=[RedFlag(description="BP >= 140/90 on two readings", severity="escalate",
                           escalation_message="BP above threshold.")],
        created_at=NOW, last_updated=NOW,
    )


def _symptoms() -> list[SymptomLog]:
    return [
        SymptomLog(patient_id=PID, timestamp=NOW, bp_systolic=142, bp_diastolic=91, headache_severity=6),
        SymptomLog(patient_id=PID, timestamp=NOW, bp_systolic=140, bp_diastolic=90),
    ]


class _FakeStore:
    def __init__(self):
        self.symptoms: list[SymptomLog] = []
        self.risks: list[RiskScore] = []
        self.escalations = []
        self.plan = None


@pytest.fixture
def store(monkeypatch):
    s = _FakeStore()
    monkeypatch.setattr(redis_client, "get_plan", lambda pid: s.plan)
    monkeypatch.setattr(redis_client, "get_symptom_history", lambda pid: list(s.symptoms))
    monkeypatch.setattr(redis_client, "get_risk_timeline", lambda pid: list(s.risks))
    monkeypatch.setattr(redis_client, "log_symptom", lambda pid, d: (s.symptoms.append(d) or d))
    monkeypatch.setattr(redis_client, "append_risk", lambda pid, r: (s.risks.append(r) or r))
    monkeypatch.setattr(redis_client, "write_escalation", lambda pid, e: (s.escalations.append(e) or e))
    return s


# ── CAD-12: log_symptom ──────────────────────────────────────────────────────

def test_log_symptom_writes_and_reads_back(store):
    entry = SymptomLog(patient_id=PID, timestamp=NOW, bp_systolic=142, bp_diastolic=91,
                       headache_severity=6, swelling_location="face", vision_changes=False,
                       fetal_movement="normal", medication_taken=True)
    out = tools.log_symptom(PID, entry)
    assert out is entry
    history = redis_client.get_symptom_history(PID)
    assert len(history) == 1
    h = history[0]
    # captures BP, headache severity, swelling, vision, fetal movement, meds
    assert (h.bp_systolic, h.bp_diastolic) == (142, 91)
    assert h.headache_severity == 6
    assert h.swelling_location == "face"
    assert h.vision_changes is False
    assert h.fetal_movement == "normal"
    assert h.medication_taken is True


# ── Luis's pure fns wired through the registry ───────────────────────────────

def test_assess_risk_classifies_and_persists(store):
    store.plan = _plan()
    store.symptoms = _symptoms()
    score = tools.assess_risk(PID)
    assert isinstance(score, RiskScore)
    assert score.severity in ("ok", "monitor", "escalate", "escalate_urgent")
    assert store.risks and store.risks[-1] is score  # persisted to risk_timeline


def test_assess_risk_without_plan_is_recoverable_error(store):
    store.plan = None
    with pytest.raises(RuntimeError):
        tools.assess_risk(PID)


def test_detect_pattern_returns_alerts(store):
    store.symptoms = _symptoms()
    alerts = tools.detect_pattern(PID)
    assert isinstance(alerts, list)


def test_generate_visit_summary_wired(store):
    store.plan = _plan()
    store.symptoms = _symptoms()
    vs = tools.generate_visit_summary(PID)
    assert vs.patient_id == PID
    assert vs.patient_facing and vs.clinician_facing


# ── CAD-15: escalate_to_clinician ────────────────────────────────────────────

def test_escalate_builds_and_persists_summary(store):
    store.plan = _plan()
    store.symptoms = _symptoms()
    store.risks = [RiskScore(patient_id=PID, timestamp=NOW, severity="escalate",
                             rationale="BP 142/91 and 140/90 — above threshold on two readings.",
                             recommended_action="Contact patient; consider advancing appointment.",
                             triggered_flags=["BP >= 140/90 on two readings"])]
    esc = tools.escalate_to_clinician(PID)

    assert esc.patient_id == PID
    assert esc.patient_name == "Maria Chen"          # derived from patient_id
    assert esc.severity == "escalate"                 # from latest risk
    assert "above threshold" in esc.summary
    assert esc.triggering_readings == ["142/91", "140/90"]
    assert esc.recommended_action.startswith("Contact patient")
    assert isinstance(esc.pattern_context, list)
    assert esc.escalation_id.startswith(f"esc-{PID}-")
    # written to escalations:{id}
    assert store.escalations and store.escalations[-1] is esc


def test_escalate_without_risk_defaults_gracefully(store):
    store.plan = _plan()
    store.symptoms = []
    store.risks = []
    esc = tools.escalate_to_clinician(PID)
    assert esc.severity == "escalate"  # safe default
    assert store.escalations


def test_escalate_push_and_judge_are_safe_noops(store):
    """Web Push + Arize judge aren't built yet — escalation must still succeed."""
    store.plan = _plan()
    store.symptoms = _symptoms()
    store.risks = []
    esc = tools.escalate_to_clinician(PID)  # must not raise even though push/eval modules absent
    assert esc.escalation_id


def test_schedule_followup_persists(monkeypatch):
    """CAD-34: schedule_followup writes followup:{id} and returns True (no longer a stub)."""
    saved = {}
    monkeypatch.setattr(redis_client, "set_followup",
                        lambda pid, when: saved.update(pid=pid, when=when) or saved)
    assert tools.schedule_followup(PID, "tomorrow 9am") is True
    assert saved == {"pid": PID, "when": "tomorrow 9am"}


def test_schedule_followup_defaults_blank_when(monkeypatch):
    saved = {}
    monkeypatch.setattr(redis_client, "set_followup",
                        lambda pid, when: saved.update(when=when))
    tools.schedule_followup(PID, "")
    assert saved["when"] == "as soon as possible"


def test_registry_has_all_seven_tools():
    assert set(tools.TOOL_REGISTRY) == {
        "lookup_plan", "log_symptom", "assess_risk", "detect_pattern",
        "escalate_to_clinician", "generate_visit_summary", "schedule_followup",
    }
