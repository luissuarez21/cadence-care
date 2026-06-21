"""
CAD-14 — unit tests for pure pattern detection.

No Redis/server: build hardcoded multi-day SymptomLog series and assert which
trend alerts fire. AC: a rising-BP series fires an alert; a flat series does not.
"""

from __future__ import annotations

from datetime import datetime, timezone

from backend.ingestion.schema import SymptomLog
from backend.risk.patterns import detect

PATIENT = "maria-chen"
BASE = datetime(2026, 6, 12, 8, 0, tzinfo=timezone.utc)


def _day(n: int, **fields) -> SymptomLog:
    return SymptomLog(patient_id=PATIENT, timestamp=BASE.replace(day=12 + n), **fields)


def test_rising_bp_series_fires_alert():
    logs = [_day(i, bp_systolic=124 + i * 4, bp_diastolic=80 + i) for i in range(5)]
    alerts = detect(logs)
    bp = [a for a in alerts if a.metric == "bp_systolic"]
    assert bp, "expected a BP trend alert"
    assert "trending up" in bp[0].title
    assert "124" in bp[0].detail and "140" in bp[0].detail


def test_flat_bp_series_no_alert():
    logs = [_day(i, bp_systolic=120, bp_diastolic=78) for i in range(5)]
    alerts = detect(logs)
    assert [a for a in alerts if a.metric == "bp_systolic"] == []


def test_noisy_nonmonotonic_bp_no_alert():
    # up-down-up never sustains a clean rise
    vals = [120, 132, 119, 128, 121]
    logs = [_day(i, bp_systolic=v, bp_diastolic=78) for i, v in enumerate(vals)]
    assert [a for a in detect(logs) if a.metric == "bp_systolic"] == []


def test_too_few_days_no_bp_alert():
    logs = [_day(0, bp_systolic=120), _day(1, bp_systolic=150)]
    assert [a for a in detect(logs) if a.metric == "bp_systolic"] == []


def test_recurring_headaches_fire():
    logs = [
        _day(0, headache_severity=0),
        _day(1, headache_severity=4),
        _day(2, headache_severity=0),
        _day(3, headache_severity=5),
        _day(4, headache_severity=6),
    ]
    alerts = detect(logs)
    ha = [a for a in alerts if a.metric == "headache_severity"]
    assert ha, "expected a recurring-headache alert"
    assert "3" in ha[0].title


def test_isolated_headache_no_alert():
    logs = [_day(i, headache_severity=(5 if i == 2 else 0)) for i in range(5)]
    assert [a for a in detect(logs) if a.metric == "headache_severity"] == []


def test_repeated_decreased_movement_escalates():
    logs = [
        _day(0, fetal_movement="normal"),
        _day(1, fetal_movement="decreased"),
        _day(2, fetal_movement="normal"),
        _day(3, fetal_movement="less than usual"),
    ]
    alerts = detect(logs)
    fm = [a for a in alerts if a.metric == "fetal_movement"]
    assert fm and fm[0].severity == "escalate"


def test_empty_series_no_alerts():
    assert detect([]) == []


def test_alerts_sorted_most_severe_first():
    logs = [
        _day(0, bp_systolic=124, headache_severity=4, fetal_movement="decreased"),
        _day(1, bp_systolic=128, headache_severity=5, fetal_movement="normal"),
        _day(2, bp_systolic=132, headache_severity=6, fetal_movement="reduced"),
        _day(3, bp_systolic=136, headache_severity=5, fetal_movement="normal"),
    ]
    alerts = detect(logs)
    assert len(alerts) >= 2
    ranks = {"escalate_urgent": 3, "escalate": 2, "monitor": 1, "ok": 0}
    severities = [ranks[a.severity] for a in alerts]
    assert severities == sorted(severities, reverse=True)
