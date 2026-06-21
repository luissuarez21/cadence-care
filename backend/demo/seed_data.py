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

from ..memory import redis_client
from . import maria_data


def seed() -> dict[str, int]:
    """Seed Maria's plan, symptoms, and risk timeline into Redis. Returns counts."""
    plan = maria_data.build_plan()
    symptoms = maria_data.build_symptoms()
    risk_timeline = maria_data.build_risk_timeline(plan, symptoms)

    redis_client.set_plan(maria_data.PATIENT_ID, plan)
    for log in symptoms:
        redis_client.log_symptom(maria_data.PATIENT_ID, log)
    for score in risk_timeline:
        redis_client.append_risk(maria_data.PATIENT_ID, score)

    return {
        "plan": 1,
        "symptoms": len(symptoms),
        "risk_timeline": len(risk_timeline),
    }


if __name__ == "__main__":
    counts = seed()
    print(
        f"Seeded {maria_data.PATIENT_NAME} ({maria_data.PATIENT_ID}): "
        f"plan=1, symptoms={counts['symptoms']}, risk_timeline={counts['risk_timeline']}."
    )
