"""Care-plan ingestion route (Story 1: mock; real Claude Vision pipeline in Story 9)."""

from __future__ import annotations

from fastapi import APIRouter, File, Form, UploadFile

from ..ingestion.api_models import IngestResponse
from . import mocks

router = APIRouter(prefix="/api", tags=["ingest"])


@router.post("/ingest", response_model=IngestResponse)
async def ingest(patient_id: str = Form(...), file: UploadFile = File(...)) -> IngestResponse:
    # TODO(Story 9): Claude Vision -> ProtocolJSON -> Redis plan:{patient_id}.
    return IngestResponse(
        patient_id=patient_id,
        ok=True,
        red_flags=mocks.RED_FLAGS,
        message=f"Parsed care plan for {patient_id} ({file.filename}).",
    )
