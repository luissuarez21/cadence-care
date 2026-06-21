"""Clinician dashboard routes (Story 1: mock; real Redis wiring in Story 7)."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..ingestion.api_models import (
    ActionRequest,
    ActionResponse,
    EscalationsResponse,
    PanelResponse,
    PatientDetailResponse,
)
from . import mocks

router = APIRouter(prefix="/api/clinician", tags=["clinician"])


@router.get("/panel", response_model=PanelResponse)
async def panel() -> PanelResponse:
    return mocks.panel_response()


@router.get("/patient/{patient_id}", response_model=PatientDetailResponse)
async def patient_detail(patient_id: str) -> PatientDetailResponse:
    return mocks.patient_detail(patient_id)


@router.get("/escalations", response_model=EscalationsResponse)
async def escalations() -> EscalationsResponse:
    return mocks.escalations_response()


@router.post("/action", response_model=ActionResponse)
async def action(req: ActionRequest) -> ActionResponse:
    # TODO(Story 7): persist to messages:/notes:{patient_id} or schedule_followup.
    return ActionResponse(ok=True, message=f"Action '{req.action}' recorded for {req.patient_id}.")


# WebSocket lives at /ws/escalations (registered on the app, not under the /api prefix).
ws_router = APIRouter(tags=["clinician"])


@ws_router.websocket("/ws/escalations")
async def ws_escalations(websocket: WebSocket) -> None:
    await websocket.accept()
    try:
        # Story 1: emit one sample escalation so the frontend can render the inbox,
        # then hold the connection open. Story 7 replaces this with a Redis pub/sub feed.
        await websocket.send_text(mocks.sample_escalation().model_dump_json())
        while True:
            await asyncio.sleep(30)
            await websocket.send_text('{"type":"ping"}')
    except WebSocketDisconnect:
        return
