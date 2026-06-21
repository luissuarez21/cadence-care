"""Web Push subscription route (Story 1: mock; real storage in Story 8)."""

from __future__ import annotations

from fastapi import APIRouter

from ..ingestion.api_models import GenericOk, PushSubscribeRequest

router = APIRouter(prefix="/api/push", tags=["push"])


@router.post("/subscribe", response_model=GenericOk)
async def subscribe(req: PushSubscribeRequest) -> GenericOk:
    # TODO(Story 8): store in Redis push_subscriptions:{clinician_id}.
    return GenericOk(ok=True)
