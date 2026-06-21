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

# NOTE: bodies are stubs that raise NotImplementedError. Replace with real impls
# (or imports of Luis's impls) story-by-story. Signatures are frozen.


def lookup_plan(patient_id: str, query: str) -> list[str]:
    """RAG over the patient's care plan. Returns relevant plan chunks. (Adit — rag.py)"""
    raise NotImplementedError


def log_symptom(patient_id: str, data: SymptomLog) -> SymptomLog:
    """Persist a structured check-in to Redis symptoms:{patient_id}. (Adit)"""
    raise NotImplementedError


def assess_risk(patient_id: str) -> RiskScore:
    """
    Evaluate current session vs. the condition pack's red_flags.
    Returns severity + plain-English rationale. Writes risk_timeline:{id}. (Luis — classifier.py)
    """
    raise NotImplementedError


def detect_pattern(patient_id: str) -> list[PatternAlert]:
    """Trend logic over symptoms:{patient_id} time-series. (Luis — patterns.py)"""
    raise NotImplementedError


def escalate_to_clinician(patient_id: str) -> EscalationSummary:
    """
    Build the clinical summary, write escalations:{id}, fire Web Push, kick off
    the async Arize LLM-as-judge eval. (Adit — escalation/handler.py)
    """
    raise NotImplementedError


def generate_visit_summary(patient_id: str) -> VisitSummary:
    """Patient + clinician pre-appointment briefs from logs since last visit. (Luis — visit_summary.py)"""
    raise NotImplementedError


def schedule_followup(patient_id: str, when: str) -> bool:
    """Adjust next check-in / appointment. Called by clinician 'book sooner'. (Adit)"""
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
