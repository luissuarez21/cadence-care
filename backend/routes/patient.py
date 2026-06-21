"""Patient read-only views: watchfor, history, summary — wired to Redis."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..agent.tools import generate_visit_summary
from ..ingestion.api_models import HistoryResponse, SummaryResponse, WatchForResponse
from ..memory import redis_client

router = APIRouter(prefix="/api/patient", tags=["patient"])


@router.get("/watchfor", response_model=WatchForResponse)
async def get_watchfor(patient_id: str) -> WatchForResponse:
    plan = redis_client.get_plan(patient_id)
    red_flags = plan.red_flags if plan else []
    return WatchForResponse(patient_id=patient_id, red_flags=red_flags)


@router.get("/history", response_model=HistoryResponse)
async def get_history(patient_id: str) -> HistoryResponse:
    entries = list(reversed(redis_client.get_symptom_history(patient_id)))
    flags_count = sum(1 for e in entries if (e.bp_systolic or 0) >= 140)
    return HistoryResponse(
        patient_id=patient_id,
        entries=entries,
        check_in_count=len(entries),
        flags_count=flags_count,
    )


@router.get("/summary", response_model=SummaryResponse)
async def get_summary(patient_id: str) -> SummaryResponse:
    try:
        visit_summary = generate_visit_summary(patient_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return SummaryResponse(patient_id=patient_id, visit_summary=visit_summary)
