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

from ..ingestion.schema import ProtocolJSON, RiskScore, SymptomLog
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


def seed_all() -> dict[str, int]:
    """Seed Maria + the panel roster — the full demo dataset."""
    maria = seed()
    panel = seed_panel()
    return {
        "maria_symptoms": maria["symptoms"],
        "panel_patients": panel["patients"],
        "panel_symptoms": panel["symptoms"],
    }


if __name__ == "__main__":
    counts = seed_all()
    print(
        f"Seeded {maria_data.PATIENT_NAME} (hero) + {counts['panel_patients']} panel "
        f"patients. Maria symptoms={counts['maria_symptoms']}, "
        f"panel symptoms={counts['panel_symptoms']}."
    )
