"""
Cadence — Plan ingestion pipeline (CAD-10).

OB uploads a care plan (PDF or image) → Claude Vision extracts the clinical
structure → validated as ProtocolJSON → stored in Redis → RAG chunks embedded.

Calling convention:
    plan = await ingest_plan(patient_id, file_bytes, filename)

The demo pre-seeds Maria Chen's plan via seed_data.py, so the live Vision call
only needs to run on a real upload. If Claude Vision fails or no API key is set,
callers can fall back to the pre-ingested plan already in Redis.
"""

from __future__ import annotations

import base64
import json
import logging
import os
from datetime import datetime, timezone

import anthropic

from ..ingestion.schema import (
    Medication,
    ProtocolJSON,
    RedFlag,
    Task,
)
from ..memory import redis_client, rag

logger = logging.getLogger("cadence.ingestion")

MODEL = "claude-sonnet-4-6"

# ── Extraction prompt ────────────────────────────────────────────────────────

_EXTRACTION_PROMPT = """You are a clinical data extraction assistant.

Extract the structured care plan from this document and return ONLY a valid JSON
object that matches the following schema exactly. Do not include any explanation,
markdown, or code blocks — only the raw JSON.

Schema:
{
  "condition": "string (e.g. high_risk_pregnancy_preeclampsia)",
  "gestational_age_weeks": integer or null,
  "goals": ["string", ...],
  "medications": [
    {"name": "string", "dose": "string", "frequency": "string", "instructions": "string"}
  ],
  "tasks": [
    {"task": "string", "frequency": "string", "instructions": "string"}
  ],
  "check_in_cadence_hours": integer (default 24),
  "red_flags": [
    {
      "description": "string",
      "severity": "ok" | "monitor" | "escalate" | "escalate_urgent",
      "escalation_message": "string"
    }
  ],
  "patient_context": "string (free-text summary the OB wants the AI to know)"
}

If a field is not found, use an empty list or null. Be thorough — extract every
red flag, medication, and goal you can find.
"""


def _media_type(filename: str) -> str:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return {
        "pdf": "application/pdf",
        "png": "image/png",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "gif": "image/gif",
        "webp": "image/webp",
    }.get(ext, "application/octet-stream")


def _parse_extraction(raw_json: str, patient_id: str) -> ProtocolJSON:
    """Parse Claude's JSON extraction into a validated ProtocolJSON."""
    data = json.loads(raw_json.strip())
    now = datetime.now(timezone.utc)

    medications = [
        Medication(**m) if isinstance(m, dict) else m
        for m in data.get("medications", [])
    ]
    tasks = [
        Task(**t) if isinstance(t, dict) else t
        for t in data.get("tasks", [])
    ]
    red_flags = [
        RedFlag(**rf) if isinstance(rf, dict) else rf
        for rf in data.get("red_flags", [])
    ]

    return ProtocolJSON(
        patient_id=patient_id,
        condition=data.get("condition", "unspecified"),
        gestational_age_weeks=data.get("gestational_age_weeks"),
        goals=data.get("goals", []),
        medications=medications,
        tasks=tasks,
        check_in_cadence_hours=int(data.get("check_in_cadence_hours", 24)),
        red_flags=red_flags,
        patient_context=data.get("patient_context", ""),
        created_at=now,
        last_updated=now,
    )


async def ingest_plan(
    patient_id: str,
    file_bytes: bytes,
    filename: str,
) -> ProtocolJSON:
    """
    Main entry point: extract ProtocolJSON from an uploaded file via Claude Vision,
    persist it to Redis, and trigger RAG chunk embedding.

    Raises RuntimeError on extraction or validation failure.
    """
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY", ""))
    media_type = _media_type(filename)
    b64 = base64.standard_b64encode(file_bytes).decode()

    # PDFs go as "document", images go as "image" blocks.
    if media_type == "application/pdf":
        source_block: dict = {
            "type": "document",
            "source": {"type": "base64", "media_type": media_type, "data": b64},
        }
    else:
        source_block = {
            "type": "image",
            "source": {"type": "base64", "media_type": media_type, "data": b64},
        }

    logger.info("Sending plan to Claude Vision for patient=%s file=%s", patient_id, filename)
    response = client.messages.create(
        model=MODEL,
        max_tokens=4096,
        messages=[
            {
                "role": "user",
                "content": [
                    source_block,
                    {"type": "text", "text": _EXTRACTION_PROMPT},
                ],
            }
        ],
    )

    raw = response.content[0].text if response.content else ""
    if not raw:
        raise RuntimeError("Claude Vision returned an empty response.")

    # Strip any accidental markdown code fences
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("```")[1]
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
        cleaned = cleaned.strip()

    try:
        plan = _parse_extraction(cleaned, patient_id)
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        raise RuntimeError(f"Failed to parse Vision extraction: {exc}\nRaw: {raw[:500]}") from exc

    # Persist plan + generate RAG chunks
    redis_client.set_plan(patient_id, plan)
    rag.embed_plan(patient_id, plan)
    logger.info("Ingested plan for patient=%s condition=%s", patient_id, plan.condition)
    return plan
