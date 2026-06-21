"""
CAD-38 — offline tests for the multi-patient panel seed.

No Redis: build the roster and replicate the clinician panel's sort contract to
prove the 50 -> 3 ranking actually works (>= 3 patients outrank the rest).
"""

from __future__ import annotations

from datetime import datetime, timezone

from backend.demo import panel_data
from backend.risk.classifier import classify

# Mirror of the panel route's ranking contract (backend/routes/clinician.py).
_SEVERITY_RANK = {"escalate_urgent": 3, "escalate": 2, "monitor": 1, "ok": 0}
_MIN_DT = datetime.min.replace(tzinfo=timezone.utc)


def _display_name(pid: str) -> str:
    return " ".join(p.capitalize() for p in pid.split("-"))


def _panel_rows():
    """Reproduce what GET /api/clinician/panel would build + sort, offline."""
    rows = []
    for plan, symptoms, timeline in panel_data.PANEL_PATIENTS:
        latest = timeline[-1]
        rows.append({
            "patient_id": plan.patient_id,
            "name": _display_name(plan.patient_id),
            "severity": latest.severity,
            "last_check_in": symptoms[-1].timestamp,
            "headline": (latest.triggered_flags[0] if latest.triggered_flags
                         else latest.rationale)[:80],
        })
    rows.sort(key=lambda r: (_SEVERITY_RANK[r["severity"]], r["last_check_in"]), reverse=True)
    return rows


def test_roster_size_is_a_real_panel():
    assert 10 <= len(panel_data.PANEL_PATIENTS) <= 15


def test_severity_is_real_classifier_output_matching_targets():
    # Every patient's seeded severity must equal classify() on their symptoms,
    # and match the intended target — no hand-faked severities.
    for spec, (plan, symptoms, timeline) in zip(panel_data._SPECS, panel_data.PANEL_PATIENTS):
        computed = classify(symptoms, plan).severity
        assert timeline[-1].severity == computed
        assert computed == spec["target"], f"{spec['id']}: {computed} != {spec['target']}"


def test_at_least_three_outrank_the_rest():
    rows = _panel_rows()
    high = [r for r in rows if r["severity"] in ("escalate", "escalate_urgent")]
    assert len(high) >= 3
    # The high-risk rows are exactly the top of the sorted list.
    assert all(r["severity"] in ("escalate", "escalate_urgent") for r in rows[:len(high)])


def test_panel_is_sorted_highest_first():
    rows = _panel_rows()
    ranks = [_SEVERITY_RANK[r["severity"]] for r in rows]
    assert ranks == sorted(ranks, reverse=True)
    assert rows[0]["severity"] == "escalate_urgent"   # someone is top priority


def test_mix_includes_monitor_and_ok():
    sevs = {t[-1].severity for _, _, t in panel_data.PANEL_PATIENTS}
    assert {"monitor", "ok"} <= sevs


def test_headlines_and_names_are_populated_and_synthetic():
    rows = _panel_rows()
    for r in rows:
        assert r["name"] and " " in r["name"]      # realistic display name
        assert r["headline"]                        # one-line status present
    ids = [r["patient_id"] for r in rows]
    assert len(ids) == len(set(ids))                # unique
    assert "maria-chen" not in ids                  # Maria is the separate hero record


def test_each_patient_has_plan_symptoms_and_risk():
    for plan, symptoms, timeline in panel_data.PANEL_PATIENTS:
        assert plan.red_flags and symptoms and timeline
        assert all(s.patient_id == plan.patient_id for s in symptoms)
