"""
CAD-8 — offline tests for the Maria Chen synthetic demo data.

No Redis: validate the pure data module and that it produces the demo story
(rising BP, recurring headaches, escalate on the final day).
"""

from __future__ import annotations

from backend.demo import maria_data
from backend.risk.classifier import classify
from backend.risk.patterns import detect


def test_plan_is_synthetic_preeclampsia_29wk_on_aspirin():
    plan = maria_data.PLAN
    assert plan.patient_id == "maria-chen"
    assert plan.gestational_age_weeks == 29
    assert "preeclampsia" in plan.condition
    assert any("aspirin" in m.name.lower() for m in plan.medications)
    assert plan.red_flags  # carries the pack's red flags


def test_nine_days_of_check_ins():
    symptoms = maria_data.SYMPTOMS
    days = {s.timestamp.date() for s in symptoms}
    assert len(days) == 9
    assert len(symptoms) == 18  # morning + evening each day
    assert all(s.patient_id == "maria-chen" for s in symptoms)


def test_headaches_on_days_3_6_9():
    symptoms = sorted(maria_data.SYMPTOMS, key=lambda s: s.timestamp)
    headache_days = sorted({
        (s.timestamp.date() - symptoms[0].timestamp.date()).days + 1
        for s in symptoms if s.headache_severity
    })
    assert headache_days == [3, 6, 9]


def test_bp_rises_and_crosses_threshold_on_last_day():
    morning = sorted(
        [s for s in maria_data.SYMPTOMS if s.timestamp.hour == 8],
        key=lambda s: s.timestamp,
    )
    systolics = [s.bp_systolic for s in morning]
    assert systolics[0] < 120 and systolics[-1] >= 140       # climbs across the window
    assert systolics == sorted(systolics)                     # monotonic up


def test_classify_full_history_escalates():
    score = classify(maria_data.SYMPTOMS, maria_data.PLAN)
    assert score.severity == "escalate"
    assert "142/91" in score.rationale


def test_patterns_fire_bp_trend_and_recurring_headaches():
    alerts = detect(maria_data.SYMPTOMS)
    metrics = {a.metric for a in alerts}
    assert "bp_systolic" in metrics
    assert "headache_severity" in metrics


def test_risk_timeline_is_chronological_and_ends_escalate():
    tl = maria_data.RISK_TIMELINE
    assert len(tl) == 9
    times = [r.timestamp for r in tl]
    assert times == sorted(times)
    assert tl[0].severity == "ok"
    assert tl[-1].severity == "escalate"
