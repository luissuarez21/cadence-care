"""
Cadence — Redis seeder for the Maria Chen demo (CAD-8)

Writes the synthetic hero patient into Redis using Adit's redis_client helpers:
  plan:{id}           ← Maria's ProtocolJSON
  symptoms:{id}       ← 9 days of SymptomLog check-ins
  risk_timeline:{id}  ← one RiskScore per day

All data is 100% synthetic (see maria_data.py). Importing this module has NO side
effects; run it as a script to seed:

    python -m backend.demo.seed_data
"""

from __future__ import annotations

from ..ingestion.schema import EscalationSummary, ProtocolJSON, RiskScore, SymptomLog
from ..memory import redis_client
from . import maria_data, panel_data


def _write_patient(
    patient_id: str,
    plan: ProtocolJSON,
    symptoms: list[SymptomLog],
    risk_timeline: list[RiskScore],
) -> None:
    redis_client.set_plan(patient_id, plan)
    for log in symptoms:
        redis_client.log_symptom(patient_id, log)
    for score in risk_timeline:
        redis_client.append_risk(patient_id, score)


def seed() -> dict[str, int]:
    """Seed Maria (the depth hero record). Returns counts."""
    plan = maria_data.build_plan()
    symptoms = maria_data.build_symptoms()
    risk_timeline = maria_data.build_risk_timeline(plan, symptoms)
    _write_patient(maria_data.PATIENT_ID, plan, symptoms, risk_timeline)
    return {"plan": 1, "symptoms": len(symptoms), "risk_timeline": len(risk_timeline)}


def seed_panel() -> dict[str, int]:
    """Seed the synthetic roster (CAD-38) so the panel ranks 50 -> 3. Returns counts."""
    patients = panel_data.build_panel_patients()
    symptoms_total = 0
    for plan, symptoms, risk_timeline in patients:
        _write_patient(plan.patient_id, plan, symptoms, risk_timeline)
        symptoms_total += len(symptoms)
    return {"patients": len(patients), "symptoms": symptoms_total}


# Standing escalations for two already-high-risk panel patients, so the inbox
# isn't empty next to the red panel rows at demo start. Each mirrors that patient's
# seeded timeline (see panel_data._NARRATIVES), so the clinical story is consistent
# and defensible. Maria's escalation is deliberately NOT seeded — it fires LIVE in
# the demo (BP check-in / safety message), which is the moment we want to show.
_EVENING = panel_data._TODAY.replace(hour=19, minute=30)


def _standing_escalations() -> list[tuple[str, EscalationSummary]]:
    return [
        ("priya-anand", EscalationSummary(
            escalation_id="esc-priya-001",
            patient_id="priya-anand",
            patient_name="Priya Anand",
            timestamp=_EVENING,
            severity="escalate_urgent",
            summary="BP 168/114 this evening — severe range — with a new headache and facial swelling.",
            triggering_readings=["168/114"],
            pattern_context=["BP in severe range (≥160/110)", "Headache with facial swelling"],
            recommended_action="Contact patient now; assess for preeclampsia with severe features.",
        )),
        ("rosa-martinez", EscalationSummary(
            escalation_id="esc-rosa-001",
            patient_id="rosa-martinez",
            patient_name="Rosa Martinez",
            timestamp=_EVENING.replace(minute=10),
            severity="escalate",
            summary="Two readings at/above 140/90 today (144/92, 141/90) with a mild headache.",
            triggering_readings=["144/92", "141/90"],
            pattern_context=["Two elevated BP readings same day"],
            recommended_action="Contact patient; confirm repeat readings and review for preeclampsia.",
        )),
    ]


def seed_escalations() -> int:
    """Write the standing escalations into escalations:{id}. Returns the count."""
    items = _standing_escalations()
    for patient_id, escalation in items:
        redis_client.write_escalation(patient_id, escalation)
    return len(items)


def seed_all() -> dict[str, int]:
    """Seed Maria + the panel roster + standing escalations — the full demo dataset."""
    maria = seed()
    panel = seed_panel()
    escalations = seed_escalations()
    return {
        "maria_symptoms": maria["symptoms"],
        "panel_patients": panel["patients"],
        "panel_symptoms": panel["symptoms"],
        "escalations": escalations,
    }


# All patient-scoped key families written during a demo. Wiped before a reseed so
# a "start fresh" leaves nothing behind — chat (sessions are keyed by UUID, hence
# the wildcard), escalations, the "book sooner" follow-up + clinician messages
# that surface in the patient app, etc. push_subscriptions is intentionally left
# alone so the clinician's Web Push stays registered across resets.
_WIPE_PREFIXES = (
    "plan", "session", "symptoms", "risk_timeline",
    "vector", "escalations", "messages", "notes", "followup",
)


def _wipe() -> int:
    """Delete every patient-data key. Returns the count removed."""
    client = redis_client.get_client()
    deleted = 0
    for prefix in _WIPE_PREFIXES:
        for key in client.scan_iter(match=f"{prefix}:*"):
            client.delete(key)
            deleted += 1
    return deleted


def reset_demo() -> dict[str, int]:
    """
    Wipe all patient data, then reseed the full demo dataset. Idempotent — safe to
    call repeatedly (right before each demo run) to guarantee a pristine state with
    no leftover crisis chat, escalations, or follow-up banners.
    """
    deleted = _wipe()
    counts = seed_all()
    counts["deleted_keys"] = deleted
    return counts


if __name__ == "__main__":
    import sys

    if "--reset" in sys.argv:
        counts = reset_demo()
        print(
            f"Reset: wiped {counts['deleted_keys']} keys, reseeded "
            f"{counts['panel_patients']} panel patients + {maria_data.PATIENT_NAME}."
        )
    else:
        counts = seed_all()
        print(
            f"Seeded {maria_data.PATIENT_NAME} (hero) + {counts['panel_patients']} panel "
            f"patients. Maria symptoms={counts['maria_symptoms']}, "
            f"panel symptoms={counts['panel_symptoms']}."
        )
