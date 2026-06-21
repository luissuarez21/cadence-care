"""
Cadence — Multi-patient panel seed (CAD-38)

The "breadth" pass that pairs with the Maria "depth" record (CAD-8). Seeds a roster
of synthetic patients so the clinician panel actually ranks 50 → 3 instead of showing
a single row.

PURE: builds each patient as (plan, symptoms, risk_timeline) in memory. No Redis here
— seed_data.py writes them. The clinician panel route reads risk_timeline (latest
entry → severity + headline) and symptoms (last check-in), and derives the display
name from the patient_id ("rosa-martinez" → "Rosa Martinez").

NO HAND-FAKED RISK: every patient's risk_timeline is computed by the real classify()
from their symptoms, so the panel severities are genuine engine output, not literals.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ..ingestion.schema import Medication, ProtocolJSON, RedFlag, RiskScore, SymptomLog
from ..risk.classifier import classify

_PACK = json.loads(
    (Path(__file__).resolve().parents[2] / "packs" / "preeclampsia_risk.json").read_text()
)
_RED_FLAGS = [RedFlag(**rf) for rf in _PACK["red_flags"]]

# Roster is anchored a few days before "today" so check-ins look recent.
_TODAY = datetime(2026, 6, 21, tzinfo=timezone.utc)


def _plan(patient_id: str, ga_weeks: int) -> ProtocolJSON:
    return ProtocolJSON(
        patient_id=patient_id,
        condition=_PACK["condition"],
        gestational_age_weeks=ga_weeks,
        medications=[Medication(name="Low-dose aspirin", dose="81 mg", frequency="once daily")],
        check_in_cadence_hours=_PACK["check_in_cadence_hours"],
        red_flags=_RED_FLAGS,
        patient_context=f"Synthetic panel patient, {ga_weeks} weeks, preeclampsia surveillance.",
        created_at=_TODAY - timedelta(days=10),
        last_updated=_TODAY,
    )


# Each spec: id, gestational age, and the LATEST-day clinical picture that drives
# the (real, classify-computed) severity. `days_ago` staggers last check-in so the
# panel's tie-break (most recent first within a severity) is exercised.
# Target severity is documented for review; it is asserted in tests, not hardcoded.
_SPECS: list[dict] = [
    # ── escalate_urgent ──
    dict(id="priya-anand", ga=33, days_ago=0, target="escalate_urgent",
         latest=dict(bp_systolic=168, bp_diastolic=114)),                       # severe range
    # ── escalate ──
    dict(id="rosa-martinez", ga=31, days_ago=0, target="escalate",
         two_readings=[(144, 92), (141, 90)]),                                  # two >=140/90
    dict(id="ana-okafor", ga=29, days_ago=1, target="escalate",
         latest=dict(bp_systolic=122, bp_diastolic=78, fetal_movement="decreased")),
    # ── monitor ──
    dict(id="chloe-bennett", ga=27, days_ago=0, target="monitor",
         latest=dict(bp_systolic=142, bp_diastolic=90)),                        # single elevated
    dict(id="leah-kim", ga=28, days_ago=2, target="monitor",
         latest=dict(bp_systolic=126, bp_diastolic=82, headache_severity=5)),   # moderate headache
    dict(id="fatima-hassan", ga=26, days_ago=1, target="monitor",
         missed_aspirin=True,
         latest=dict(bp_systolic=124, bp_diastolic=80)),                        # 2-day nonadherence
    # ── ok ──
    dict(id="grace-nguyen", ga=24, days_ago=0, target="ok"),
    dict(id="sofia-rossi", ga=30, days_ago=1, target="ok"),
    dict(id="amara-diallo", ga=22, days_ago=2, target="ok"),
    dict(id="mei-tanaka", ga=35, days_ago=0, target="ok"),
    dict(id="hannah-cohen", ga=19, days_ago=3, target="ok"),
    dict(id="jade-thompson", ga=32, days_ago=1, target="ok"),
]


def _normal_evening(day: datetime) -> dict:
    return dict(bp_systolic=118, bp_diastolic=76, fetal_movement="normal", medication_taken=True)


# Per-patient narrative voices — 2 prior calm days + the key clinical day.
# Format: list of (raw_text, notes) tuples, one per check-in in chrono order.
_NARRATIVES: dict[str, list[tuple[str, str]]] = {
    "priya-anand": [
        ("Evening check-in. BP 118/76, feeling okay. Baby moving well, took aspirin.", "Calm baseline day."),
        ("BP 118/76 tonight. Baby active. Aspirin taken, no complaints.", "Second calm day."),
        ("BP 168/114 — much higher than usual. I have a bad headache and my face looks puffy. Took aspirin.", "Severe BP spike, facial swelling reported."),
    ],
    "rosa-martinez": [
        ("Feeling pretty normal tonight. BP 118/76, baby is kicking a lot. Took my aspirin.", "Calm baseline."),
        ("Evening reading 118/76. No headache. Baby moving normally. Aspirin taken.", "Second calm day."),
        ("Morning BP was 144/92, felt a little off. Evening re-check was 141/90. Still a bit of a headache.", "Two elevated readings same day."),
        ("Second evening reading tonight: 141/90. Headache is mild. Aspirin taken.", "Confirmed dual elevated reading."),
    ],
    "ana-okafor": [
        ("BP 118/76 last night, baby moving fine. Took aspirin with dinner.", "Calm baseline."),
        ("Normal evening. BP 118/76, baby active, aspirin done.", "Second calm day."),
        ("BP is okay at 122/78 but I haven't felt the baby move much today — less than usual.", "Decreased fetal movement reported."),
    ],
    "chloe-bennett": [
        ("Evening BP 118/76. Baby kicking lots. Aspirin taken, feeling good.", "Calm baseline."),
        ("118/76 again tonight. No swelling, no headache. Aspirin taken.", "Second calm day."),
        ("BP came up to 142/90 tonight, that's a bit higher than normal for me. Slight headache.", "Single elevated reading."),
    ],
    "leah-kim": [
        ("BP 118/76. Baby moving well. Aspirin taken. Head feels fine tonight.", "Calm baseline."),
        ("Normal evening, BP 118/76, aspirin taken. Mild pressure in my head but manageable.", "Slight headache noted day prior."),
        ("BP 126/82. Headache is about a 5/10 today, mostly at the back of my head. Baby moving okay.", "Moderate headache with mild BP elevation."),
    ],
    "fatima-hassan": [
        ("Forgot aspirin again. BP 118/76 though, feeling okay. Baby moving.", "Aspirin missed, day 1."),
        ("BP 118/76. Didn't take the aspirin — I keep forgetting in the morning rush. Baby active.", "Aspirin missed, day 2."),
        ("BP 124/80 this evening. Took aspirin today. Baby is moving, no headache.", "Aspirin taken today, BP slightly elevated."),
    ],
    "grace-nguyen": [
        ("Evening check-in. BP 116/74. Baby moving well. Took aspirin. Feeling great!", "Calm baseline."),
        ("BP 116/74, all good. Baby is very active tonight. Aspirin taken.", "Second calm day."),
        ("BP 118/76 tonight. No issues at all, baby moving normally. Aspirin done.", "Another calm day."),
    ],
    "sofia-rossi": [
        ("Evening BP 120/78. Baby kicking after dinner. Aspirin taken. Feeling well.", "Calm baseline."),
        ("BP 120/78. Slight ankle swelling but nothing bad. Aspirin taken. Baby active.", "Minor ankle swelling, not concerning."),
        ("BP 118/76 tonight. Swelling gone. Baby moving fine. Aspirin taken.", "Back to normal."),
    ],
    "amara-diallo": [
        ("BP 116/74, feeling really good today. Baby very active after lunch. Aspirin taken.", "Calm baseline."),
        ("Evening check-in done. BP 116/74. No headache, no swelling. Aspirin taken.", "Second calm day."),
        ("BP 118/76. Baby moving well. Aspirin taken. Had a good day overall.", "Stable and well."),
    ],
    "mei-tanaka": [
        ("BP 120/78 this evening. Baby is so active tonight! Aspirin taken with dinner.", "Calm baseline."),
        ("Evening BP 120/78. Baby moving normally. Aspirin taken. Feeling a little tired but okay.", "Mild fatigue, otherwise fine."),
        ("BP 122/80. Tired today but no headache or swelling. Baby moving fine. Aspirin taken.", "Mild fatigue, BP stable."),
    ],
    "hannah-cohen": [
        ("BP 114/72 — lowest reading yet! Baby kicking. Aspirin taken. Great day.", "Excellent baseline."),
        ("Evening BP 114/72. Baby is busy tonight. Aspirin taken. Feeling wonderful.", "Second calm day."),
        ("BP 116/74. Everything feels normal. Baby moving well. Aspirin taken.", "Stable and healthy."),
    ],
    "jade-thompson": [
        ("Evening BP 118/76. Baby moving after dinner. Aspirin taken. No concerns.", "Calm baseline."),
        ("BP 118/76. Baby active. Aspirin taken. Mild back ache but that's normal at this stage.", "Mild back ache, not clinical."),
        ("BP 120/78. Back ache is better. Baby moving well. Aspirin taken.", "Improved, stable."),
    ],
}


def _narrative(pid: str, idx: int) -> tuple[str, str]:
    """Return (raw_text, notes) for check-in index idx, with a safe fallback."""
    narrs = _NARRATIVES.get(pid, [])
    if idx < len(narrs):
        return narrs[idx]
    bp = "118/76"
    return (f"Evening check-in. BP {bp}, feeling okay. Aspirin taken.", "Routine check-in.")


def _build_symptoms(spec: dict) -> list[SymptomLog]:
    """A short, realistic history ending `days_ago` before today."""
    pid = spec["id"]
    end = _TODAY - timedelta(days=spec.get("days_ago", 0))
    logs: list[SymptomLog] = []
    narr_idx = 0

    # Two calm prior days so trends/last-check-in look real.
    for d in (2, 1):
        day = end - timedelta(days=d)
        raw_text, notes = _narrative(pid, narr_idx)
        narr_idx += 1
        logs.append(SymptomLog(patient_id=pid, timestamp=day.replace(hour=20),
                               raw_text=raw_text, notes=notes,
                               **_normal_evening(day)))

    if spec.get("missed_aspirin"):  # override adherence on the two prior days
        missed_raw0, missed_notes0 = _narrative(pid, 0)
        missed_raw1, missed_notes1 = _narrative(pid, 1)
        logs[0] = logs[0].model_copy(update={"medication_taken": False,
                                              "raw_text": missed_raw0, "notes": missed_notes0})
        logs[1] = logs[1].model_copy(update={"medication_taken": False,
                                              "raw_text": missed_raw1, "notes": missed_notes1})

    if "two_readings" in spec:
        (ms, md), (es, ed) = spec["two_readings"]
        raw_m, notes_m = _narrative(pid, narr_idx)
        narr_idx += 1
        logs.append(SymptomLog(patient_id=pid, timestamp=end.replace(hour=8),
                               bp_systolic=ms, bp_diastolic=md, medication_taken=True,
                               raw_text=raw_m, notes=notes_m))
        raw_e, notes_e = _narrative(pid, narr_idx)
        narr_idx += 1
        logs.append(SymptomLog(patient_id=pid, timestamp=end.replace(hour=20),
                               bp_systolic=es, bp_diastolic=ed, medication_taken=True,
                               raw_text=raw_e, notes=notes_e))
    else:
        latest = spec.get("latest") or _normal_evening(end)
        latest.setdefault("medication_taken", not spec.get("missed_aspirin", False))
        raw_l, notes_l = _narrative(pid, narr_idx)
        logs.append(SymptomLog(patient_id=pid, timestamp=end.replace(hour=20),
                               raw_text=raw_l, notes=notes_l, **latest))

    return logs


def _build_risk_timeline(plan: ProtocolJSON, symptoms: list[SymptomLog]) -> list[RiskScore]:
    """Current risk computed by the real classifier (not hardcoded)."""
    score = classify(symptoms, plan)
    return [score.model_copy(update={"timestamp": symptoms[-1].timestamp})]


def build_panel_patients() -> list[tuple[ProtocolJSON, list[SymptomLog], list[RiskScore]]]:
    """All synthetic panel patients as (plan, symptoms, risk_timeline) tuples."""
    out = []
    for spec in _SPECS:
        plan = _plan(spec["id"], spec["ga"])
        symptoms = _build_symptoms(spec)
        timeline = _build_risk_timeline(plan, symptoms)
        out.append((plan, symptoms, timeline))
    return out


PANEL_PATIENTS = build_panel_patients()
