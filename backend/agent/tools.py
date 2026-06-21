"""
Cadence — Agent Tool Signatures (FROZEN CONTRACT)

These are the 7 tools the Claude orchestrator can call. The SIGNATURES here are the
contract between Adit (who owns the registry + dispatch in this file and the
orchestrator) and Luis (who implements the clinical logic in backend/risk/,
backend/summaries/, etc.).

RULE: Luis implements the bodies in his own files and they get imported here.
Luis does NOT rewrite this file — only Adit edits the registry. This keeps the
tool layer collision-free.

Each function returns a Pydantic model from backend/ingestion/schema.py so the
shapes are guaranteed consistent across the whole app.
"""

from __future__ import annotations

from ..ingestion.schema import (
    EscalationSummary,
    PatternAlert,
    RiskScore,
    SymptomLog,
    VisitSummary,
)
from ..memory import redis_client

# Luis's pure clinical functions (data in -> schema model out). Imported here;
# Luis never edits this file.
from ..risk.classifier import classify as _classify
from ..risk.patterns import detect as _detect
from ..summaries.visit_summary import summarize as _summarize
from ..escalation.handler import escalate as _escalate


def lookup_plan(patient_id: str, query: str) -> list[str]:
    """RAG over the patient's care plan. Returns relevant plan chunks. (Adit — rag.py)"""
    # Implemented in the RAG story (CAD-?). Until then this is a recoverable stub;
    # the orchestrator turns NotImplementedError into a graceful tool error.
    raise NotImplementedError


def log_symptom(patient_id: str, data: SymptomLog) -> SymptomLog:
    """Persist a structured check-in to Redis symptoms:{patient_id}. (Adit — CAD-12)"""
    return redis_client.log_symptom(patient_id, data)


def assess_risk(patient_id: str) -> RiskScore:
    """
    Evaluate current symptoms vs. the care plan's red_flags (Luis's classify),
    persist the score to risk_timeline:{id}, and return it. (Luis — classifier.py)
    """
    plan = redis_client.get_plan(patient_id)
    if plan is None:
        raise RuntimeError(f"No care plan on file for patient '{patient_id}'.")
    symptoms = redis_client.get_symptom_history(patient_id)
    score = _classify(symptoms, plan)
    redis_client.append_risk(patient_id, score)
    return score


def detect_pattern(patient_id: str) -> list[PatternAlert]:
    """Trend logic over symptoms:{patient_id} time-series. (Luis — patterns.py)"""
    symptoms = redis_client.get_symptom_history(patient_id)
    return _detect(symptoms)


def escalate_to_clinician(patient_id: str) -> EscalationSummary:
    """
    Build the clinical summary, write escalations:{id}, fire Web Push, kick off
    the async Arize LLM-as-judge eval. (Adit — escalation/handler.py — CAD-15)
    """
    return _escalate(patient_id)


def generate_visit_summary(patient_id: str) -> VisitSummary:
    """Patient + clinician pre-appointment briefs from logs since last visit. (Luis — visit_summary.py)"""
    plan = redis_client.get_plan(patient_id)
    if plan is None:
        raise RuntimeError(f"No care plan on file for patient '{patient_id}'.")
    symptoms = redis_client.get_symptom_history(patient_id)
    risk_timeline = redis_client.get_risk_timeline(patient_id)
    return _summarize(symptoms, risk_timeline, plan)


def schedule_followup(patient_id: str, when: str) -> bool:
    """Adjust next check-in / appointment. Called by clinician 'book sooner'. (Adit)"""
    # Implemented with the clinician action loop (CAD-?). Recoverable stub for now.
    raise NotImplementedError


# Registry the orchestrator dispatches against. Adit wires Claude tool-use to this.
TOOL_REGISTRY = {
    "lookup_plan": lookup_plan,
    "log_symptom": log_symptom,
    "assess_risk": assess_risk,
    "detect_pattern": detect_pattern,
    "escalate_to_clinician": escalate_to_clinician,
    "generate_visit_summary": generate_visit_summary,
    "schedule_followup": schedule_followup,
}
