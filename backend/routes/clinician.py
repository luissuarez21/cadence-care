"""
Clinician dashboard routes (Diagram 2).

  - GET  /api/clinician/panel          CAD-24  risk-ranked patient list (50 → 3)
  - GET  /api/clinician/patient/{id}   CAD-26  timeline + patterns + current risk
  - GET  /api/clinician/escalations    CAD-29  escalation inbox (REST initial load)
  - WS   /ws/escalations               CAD-29  live stream — pushes on new escalation
  - POST /api/clinician/action                 message | book | flag | note

Every read goes through redis_client; every value is a frozen schema model.
Clinician role is enforced server-side via require_clinician.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect

from ..agent import tools
from ..auth import Identity, require_clinician
from ..ingestion.api_models import (
    ActionRequest,
    ActionResponse,
    EscalationsResponse,
    PanelResponse,
    PanelRow,
    PatientDetailResponse,
)
from ..ingestion.schema import ChatMessage
from ..memory import redis_client

logger = logging.getLogger("cadence.clinician")

router = APIRouter(prefix="/api/clinician", tags=["clinician"])

# Highest first when sorting the panel.
_SEVERITY_RANK = {"escalate_urgent": 3, "escalate": 2, "monitor": 1, "ok": 0}

# Sentinel so panel sorting never compares None to datetime.
_MIN_DT = datetime.min.replace(tzinfo=timezone.utc)


def _display_name(patient_id: str) -> str:
    """Synthetic full name from a patient_id, e.g. 'maria-chen' -> 'Maria Chen'."""
    return " ".join(p.capitalize() for p in patient_id.split("-")) if patient_id else patient_id


def _assigned_patient_ids(ident: Identity) -> list[str]:
    """
    Patients this clinician may see. The demo has a single clinician who owns
    every synthetic patient; a production roster would scope this by clinician_id.
    """
    return redis_client.scan_patient_ids()


# ── CAD-24: risk-ranked panel ────────────────────────────────────────────────

@router.get("/panel", response_model=PanelResponse)
async def panel(ident: Identity = Depends(require_clinician)) -> PanelResponse:
    rows: list[PanelRow] = []
    for pid in _assigned_patient_ids(ident):
        timeline = redis_client.get_risk_timeline(pid)
        latest = timeline[-1] if timeline else None
        symptoms = redis_client.get_symptom_history(pid)
        last_check_in = symptoms[-1].timestamp if symptoms else None

        if latest:
            severity = latest.severity
            headline = (latest.triggered_flags[0] if latest.triggered_flags else latest.rationale)[:80]
        else:
            severity = "ok"
            headline = "All readings in range"

        rows.append(PanelRow(
            patient_id=pid,
            patient_name=_display_name(pid),
            severity=severity,
            last_check_in=last_check_in,
            headline=headline,
        ))

    # Highest-risk first; within a severity, most recent check-in first.
    rows.sort(key=lambda r: (_SEVERITY_RANK.get(r.severity, 0),
                             r.last_check_in or _MIN_DT), reverse=True)
    return PanelResponse(patients=rows)


# ── CAD-26: full patient picture ─────────────────────────────────────────────

@router.get("/patient/{patient_id}", response_model=PatientDetailResponse)
async def patient_detail(
    patient_id: str,
    ident: Identity = Depends(require_clinician),
) -> PatientDetailResponse:
    timeline = redis_client.get_symptom_history(patient_id)            # chronological
    risk_timeline = redis_client.get_risk_timeline(patient_id)
    current_risk = risk_timeline[-1] if risk_timeline else None

    try:
        patterns = tools.detect_pattern(patient_id)                   # Luis's detect()
    except Exception:
        logger.exception("detect_pattern failed for %s", patient_id)
        patterns = []

    try:
        visit_summary = tools.generate_visit_summary(patient_id)      # best-effort (needs a plan)
    except Exception:
        visit_summary = None

    return PatientDetailResponse(
        patient_id=patient_id,
        patient_name=_display_name(patient_id),
        current_risk=current_risk,
        timeline=timeline,
        patterns=patterns,
        visit_summary=visit_summary,
    )


# ── CAD-29: escalation inbox (REST initial load) ─────────────────────────────

@router.get("/escalations", response_model=EscalationsResponse)
async def escalations(ident: Identity = Depends(require_clinician)) -> EscalationsResponse:
    all_escalations = []
    for pid in _assigned_patient_ids(ident):
        all_escalations.extend(redis_client.get_escalations(pid))
    all_escalations.sort(key=lambda e: e.timestamp, reverse=True)     # newest first
    return EscalationsResponse(escalations=all_escalations)


# ── Clinician one-click actions ──────────────────────────────────────────────

@router.post("/action", response_model=ActionResponse)
async def action(
    req: ActionRequest,
    ident: Identity = Depends(require_clinician),
) -> ActionResponse:
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    if req.action == "message":
        # Clinician → patient secure message (messages:{id}); patient app reads it.
        redis_client.get_client().rpush(
            redis_client.messages_key(req.patient_id),
            ChatMessage(sender="cadence", text=req.content, timestamp=now).model_dump_json(),
        )
        return ActionResponse(ok=True, message="Message sent to patient.")

    # note / flag / book → recorded to notes:{id}. (book→schedule_followup is its own story.)
    note = f"[{req.action}] {req.content}".strip()
    redis_client.get_client().rpush(redis_client.notes_key(req.patient_id), note)
    return ActionResponse(ok=True, message=f"Recorded '{req.action}' for {req.patient_id}.")


# ── WebSocket: live escalation stream (registered without the /api prefix) ────

ws_router = APIRouter(tags=["clinician"])


@ws_router.websocket("/ws/escalations")
async def ws_escalations(websocket: WebSocket) -> None:
    """Push each new EscalationSummary the instant it's written to escalations:{id}."""
    await websocket.accept()
    pubsub = redis_client.escalation_pubsub()
    try:
        while True:
            # Block off-thread so the event loop stays free; timeout lets us loop.
            msg = await asyncio.to_thread(
                pubsub.get_message, ignore_subscribe_messages=True, timeout=1.0
            )
            if msg and msg.get("type") == "message":
                await websocket.send_text(msg["data"])  # already an EscalationSummary JSON string
    except WebSocketDisconnect:
        return
    except Exception:
        logger.exception("escalation WebSocket error")
        return
    finally:
        try:
            pubsub.close()
        except Exception:
            pass
