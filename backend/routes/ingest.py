"""Care-plan ingestion route (CAD-10)."""

from __future__ import annotations

import logging

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from ..ingestion.api_models import IngestResponse
from ..ingestion.pipeline import ingest_plan
from ..memory import redis_client

logger = logging.getLogger("cadence.ingest")
router = APIRouter(prefix="/api", tags=["ingest"])

_MAX_UPLOAD_BYTES = 20 * 1024 * 1024  # 20 MB


@router.post("/ingest", response_model=IngestResponse)
async def ingest(patient_id: str = Form(...), file: UploadFile = File(...)) -> IngestResponse:
    """
    Accept a PDF or image care plan, extract via Claude Vision, store in Redis.
    Falls back to an already-stored plan if the file is empty (demo pre-seed path).
    """
    content = await file.read()

    # Demo fallback: if no file bytes, check if a plan is already seeded.
    if not content:
        existing = redis_client.get_plan(patient_id)
        if existing:
            logger.info("ingest: no file bytes — returning pre-seeded plan for %s", patient_id)
            return IngestResponse(
                patient_id=patient_id,
                ok=True,
                red_flags=existing.red_flags,
                message="Using pre-ingested plan (demo mode).",
            )
        raise HTTPException(status_code=400, detail="No file content and no pre-seeded plan.")

    if len(content) > _MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File too large (max 20 MB).")

    try:
        plan = await ingest_plan(patient_id, content, file.filename or "upload")
    except RuntimeError as exc:
        logger.exception("Ingestion failed for patient=%s", patient_id)
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return IngestResponse(
        patient_id=patient_id,
        ok=True,
        red_flags=plan.red_flags,
        message=f"Extracted care plan ({plan.condition}) for {patient_id}.",
    )
