"""
Demo control route — GET/POST /api/demo/reset wipes + reseeds the demo data.

Purpose: a one-tap "start fresh" you trigger right before a live demo, so Maria
is back to her clean 9-day history with NO leftover crisis chat, self-harm
escalation, or "Dr wants to meet" follow-up banner from rehearsals/tests.

Guarded by DEMO_RESET_TOKEN so a stray request can't nuke the demo. GET is
allowed (not just POST) on purpose: it makes the reset a plain bookmarkable URL
you can tap from your phone/laptop on stage — no terminal, no curl. The data
lives in prod Redis on Railway, and this runs inside Railway, so it always hits
the right database.
"""

from __future__ import annotations

import os

from fastapi import APIRouter, HTTPException

from ..demo import seed_data

router = APIRouter(prefix="/api/demo", tags=["demo"])


def _check_token(token: str | None) -> None:
    expected = os.getenv("DEMO_RESET_TOKEN")
    if not expected or token != expected:
        raise HTTPException(status_code=403, detail="bad or missing demo token")


@router.get("/reset")
@router.post("/reset")
async def reset(token: str | None = None) -> dict:
    """Wipe all patient data and reseed the full demo dataset."""
    _check_token(token)
    counts = seed_data.reset_demo()
    return {"ok": True, "message": "Demo reset — Maria is pristine.", "reset": counts}
