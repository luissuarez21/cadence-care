"""Patient read-only views: history, watchfor, summary (Story 1: mock data)."""

from __future__ import annotations

from fastapi import APIRouter

from ..ingestion.api_models import HistoryResponse, SummaryResponse, WatchForResponse
from . import mocks

router = APIRouter(prefix="/api/patient", tags=["patient"])


@router.get("/history", response_model=HistoryResponse)
async def get_history(patient_id: str) -> HistoryResponse:
    return mocks.history_response()


@router.get("/watchfor", response_model=WatchForResponse)
async def get_watchfor(patient_id: str) -> WatchForResponse:
    return mocks.watchfor_response()


@router.get("/summary", response_model=SummaryResponse)
async def get_summary(patient_id: str) -> SummaryResponse:
    return mocks.summary_response()
