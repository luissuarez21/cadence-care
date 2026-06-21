"""
Cadence — Pattern Detection (CAD-14)

Pure, deterministic trend detection over a patient's symptom time-series.

    detect(symptoms: list[SymptomLog]) -> list[PatternAlert]

Surfaces trends a patient wouldn't notice day-to-day — "BP trending up 4 days",
"headaches 3 of the last 9 days" — for the agent and the clinician detail view.

PURE: takes the symptom logs in, returns alerts. No Redis, no network.
DETERMINISTIC: simple, auditable trend logic — unit-testable offline.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date

from ..ingestion.schema import PatternAlert, SymptomLog

# ── Tunables ─────────────────────────────────────────────────────────────────
BP_TREND_MIN_DAYS = 3          # need at least this many days of readings to call a trend
BP_TREND_MIN_RISE = 8          # mmHg systolic rise across the window to count as "up"
HEADACHE_LOOKBACK_DAYS = 9     # window for recurring-symptom counting
HEADACHE_MIN_DAYS = 3          # this many headache-days in the window → alert
HEADACHE_PRESENT = 1           # severity >= this counts as "a headache that day"
DECREASED_MOVEMENT_WORDS = ("decreas", "less", "reduc", "none", "no movement", "fewer")


def _daily_first(symptoms: list[SymptomLog], key) -> list[tuple[date, object]]:
    """
    Collapse logs to one value per day (the earliest reading that day) for the
    given accessor `key`, skipping days where key(...) is None. Sorted by date.
    """
    by_day: dict[date, tuple] = {}
    for s in sorted(symptoms, key=lambda x: x.timestamp):
        v = key(s)
        if v is None:
            continue
        d = s.timestamp.date()
        if d not in by_day:               # earliest log that day wins
            by_day[d] = (d, v)
    return [by_day[d] for d in sorted(by_day)]


def _bp_trend(symptoms: list[SymptomLog]) -> PatternAlert | None:
    series = _daily_first(symptoms, lambda s: s.bp_systolic)
    if len(series) < BP_TREND_MIN_DAYS:
        return None

    days = [d for d, _ in series]
    values = [v for _, v in series]

    rise = values[-1] - values[0]
    monotonic_up = all(values[i] <= values[i + 1] for i in range(len(values) - 1))

    if rise >= BP_TREND_MIN_RISE and monotonic_up:
        patient_id = symptoms[0].patient_id
        n_days = len(values)
        # severity nudges up if the latest reading is itself in/near elevated range
        sev = "monitor"
        if values[-1] >= 140:
            sev = "escalate"
        return PatternAlert(
            patient_id=patient_id,
            title=f"BP trending up {n_days} days",
            detail=(
                f"Systolic {values[0]} → {values[-1]} "
                f"({days[0].isoformat()} to {days[-1].isoformat()})."
            ),
            metric="bp_systolic",
            severity=sev,
        )
    return None


def _recurring_headaches(symptoms: list[SymptomLog]) -> PatternAlert | None:
    series = _daily_first(symptoms, lambda s: s.headache_severity)
    if not series:
        return None
    recent = series[-HEADACHE_LOOKBACK_DAYS:]
    headache_days = [(d, v) for d, v in recent if v is not None and v >= HEADACHE_PRESENT]
    if len(headache_days) >= HEADACHE_MIN_DAYS:
        patient_id = symptoms[0].patient_id
        worst = max(v for _, v in headache_days)
        return PatternAlert(
            patient_id=patient_id,
            title=f"Headaches {len(headache_days)} of last {len(recent)} days",
            detail=(
                f"Headache reported on {len(headache_days)} of the last "
                f"{len(recent)} check-in days (worst {worst}/10)."
            ),
            metric="headache_severity",
            severity="monitor",
        )
    return None


def _decreased_movement_recurs(symptoms: list[SymptomLog]) -> PatternAlert | None:
    series = _daily_first(symptoms, lambda s: s.fetal_movement)
    decreased = [
        (d, v) for d, v in series
        if isinstance(v, str) and any(w in v.lower() for w in DECREASED_MOVEMENT_WORDS)
    ]
    if len(decreased) >= 2:
        patient_id = symptoms[0].patient_id
        return PatternAlert(
            patient_id=patient_id,
            title=f"Reduced fetal movement on {len(decreased)} days",
            detail=(
                f"Decreased movement reported on {len(decreased)} separate days "
                f"(latest {decreased[-1][0].isoformat()})."
            ),
            metric="fetal_movement",
            severity="escalate",
        )
    return None


def _aspirin_nonadherence(symptoms: list[SymptomLog]) -> PatternAlert | None:
    series = _daily_first(symptoms, lambda s: s.medication_taken)
    missed = [(d, v) for d, v in series if v is False]
    if len(missed) >= 3:
        patient_id = symptoms[0].patient_id
        return PatternAlert(
            patient_id=patient_id,
            title=f"Aspirin missed {len(missed)} days",
            detail=(
                f"Low-dose aspirin not taken on {len(missed)} of the recorded days."
            ),
            metric="medication_taken",
            severity="monitor",
        )
    return None


def detect(symptoms: list[SymptomLog]) -> list[PatternAlert]:
    """Run all trend detectors; return the alerts that fired (most severe first)."""
    if not symptoms:
        return []

    candidates = [
        _bp_trend(symptoms),
        _recurring_headaches(symptoms),
        _decreased_movement_recurs(symptoms),
        _aspirin_nonadherence(symptoms),
    ]
    alerts = [a for a in candidates if a is not None]

    rank = {"escalate_urgent": 3, "escalate": 2, "monitor": 1, "ok": 0}
    alerts.sort(key=lambda a: rank[a.severity], reverse=True)
    return alerts
