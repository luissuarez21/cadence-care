"""Web Push subscription route (CAD-18)."""

from __future__ import annotations

from fastapi import APIRouter

from ..ingestion.api_models import GenericOk, PushSubscribeRequest
from ..memory import redis_client

router = APIRouter(prefix="/api/push", tags=["push"])


@router.post("/subscribe", response_model=GenericOk)
async def subscribe(req: PushSubscribeRequest) -> GenericOk:
    """Store the browser PushSubscription so notify_escalation can fan it out."""
    redis_client.save_push_subscription(req.clinician_id, req.subscription)
    return GenericOk(ok=True)
