"""
Patient chat route (CAD-17) — POST /api/chat/message wired to the orchestrator.

Flow (Diagram 1 ② → ③):
  auth (patient role) → orchestrator.respond (loads session + plan + pack, runs
  the tool-use loop) → return ChatResponse → persist both turns to session:{id}.

Demo-safe: if the live model call fails, the patient still gets a calm reply and
the turn is recorded, so the demo never hard-fails (per the project guardrails).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request

from ..agent import orchestrator
from ..auth import Identity, require_patient, resolve_patient_id
from ..ingestion.api_models import ChatHistoryResponse, ChatRequest, ChatResponse
from ..ingestion.schema import ChatMessage
from ..memory import redis_client

logger = logging.getLogger("cadence.chat")

router = APIRouter(prefix="/api/chat", tags=["chat"])

_FALLBACK_REPLY = (
    "I'm having a little trouble on my end right now — could you send that again in a "
    "moment? If anything feels urgent, please contact your OB or call 911."
)


def _today_session_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


@router.post("/message", response_model=ChatResponse)
async def post_message(
    req: ChatRequest,
    ident: Identity = Depends(require_patient),
) -> ChatResponse:
    patient_id = resolve_patient_id(ident, req.patient_id)
    session_id = req.session_id or _today_session_id()
    now = datetime.now(timezone.utc)

    # Run the agent first (it reads prior history from Redis; it does NOT persist),
    # so we don't double-count the current turn in the model context.
    try:
        result = orchestrator.respond(patient_id, session_id, req.message)
        reply, flagged, risk = result.text, result.flagged, result.risk
    except Exception:
        logger.exception("orchestrator.respond failed for patient=%s", patient_id)
        reply, flagged, risk = _FALLBACK_REPLY, False, None

    # Persist both turns to session:{id} (patient first, then Cadence).
    redis_client.append_message(
        patient_id, session_id,
        ChatMessage(sender="patient", text=req.message, timestamp=now),
    )
    redis_client.append_message(
        patient_id, session_id,
        ChatMessage(sender="cadence", text=reply, timestamp=now, flagged=flagged),
    )

    return ChatResponse(reply=reply, flagged=flagged, risk=risk)


@router.get("/history", response_model=ChatHistoryResponse)
async def get_history(
    patient_id: str,
    session_id: str | None = None,
    ident: Identity = Depends(require_patient),
) -> ChatHistoryResponse:
    pid = resolve_patient_id(ident, patient_id)
    sid = session_id or _today_session_id()
    return ChatHistoryResponse(
        patient_id=pid,
        session_id=sid,
        messages=redis_client.get_session(pid, sid),
    )
