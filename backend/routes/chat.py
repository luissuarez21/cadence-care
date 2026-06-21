"""Patient chat routes (Story 1: mock responses; wired to orchestrator in Story 6)."""

from __future__ import annotations

from fastapi import APIRouter

from ..ingestion.api_models import ChatHistoryResponse, ChatRequest, ChatResponse
from . import mocks

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("/message", response_model=ChatResponse)
async def post_message(req: ChatRequest) -> ChatResponse:
    # TODO(Story 6): wire to agent.orchestrator using req.patient_id / req.message.
    return mocks.chat_response()


@router.get("/history", response_model=ChatHistoryResponse)
async def get_history(patient_id: str, session_id: str | None = None) -> ChatHistoryResponse:
    return mocks.chat_history(session_id or "today")
