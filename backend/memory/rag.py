"""
Cadence — RAG layer (CAD-11).

At ingest time: care plan → text chunks → stored in Redis list vector:{patient_id}.
At query time: lookup_plan(patient_id, query) asks Claude to pick the most
relevant chunks for the query and returns them as a list of strings.

Why Claude-as-retriever instead of cosine similarity?
  The Anthropic API has no embeddings endpoint. Third-party embedding APIs would
  add a dependency and complicate HIPAA compliance. Claude reading ~20 short
  chunks and selecting relevant ones is fast (< 1 s on a short plan), accurate,
  and uses infra we already have. Chunks are still stored in Redis so the RAG
  layer is architecturally correct and easy to swap for real vector search later.
"""

from __future__ import annotations

import json
import logging
import os

import anthropic

from ..ingestion.schema import ProtocolJSON
from . import redis_client

logger = logging.getLogger("cadence.rag")

MODEL = "claude-sonnet-4-6"
_MAX_CHUNKS_TO_RETURN = 5


# ── Chunking ─────────────────────────────────────────────────────────────────

def _plan_to_chunks(plan: ProtocolJSON) -> list[str]:
    """
    Convert a ProtocolJSON into a flat list of short text chunks.
    Each chunk carries enough context to be useful on its own.
    """
    chunks: list[str] = []

    if plan.goals:
        chunks.append("Goals: " + "; ".join(plan.goals))

    if plan.patient_context:
        chunks.append("Clinical context: " + plan.patient_context)

    for med in plan.medications:
        chunks.append(
            f"Medication: {med.name} {med.dose} {med.frequency}. {med.instructions}".strip()
        )

    for task in plan.tasks:
        chunks.append(
            f"Task: {task.task} ({task.frequency}). {task.instructions}".strip()
        )

    for rf in plan.red_flags:
        chunks.append(
            f"Red flag [{rf.severity}]: {rf.description}. "
            f"If triggered: {rf.escalation_message}"
        )

    if plan.condition:
        chunks.append(f"Condition: {plan.condition}")

    if plan.gestational_age_weeks is not None:
        chunks.append(f"Gestational age: {plan.gestational_age_weeks} weeks")

    chunks.append(f"Check-in cadence: every {plan.check_in_cadence_hours} hours")

    return [c for c in chunks if c.strip()]


# ── Storage ───────────────────────────────────────────────────────────────────

def embed_plan(patient_id: str, plan: ProtocolJSON) -> None:
    """
    Chunk the plan and store each chunk in Redis list vector:{patient_id}.
    Overwrites any previous chunks (delete then rpush).
    """
    chunks = _plan_to_chunks(plan)
    client = redis_client.get_client()
    key = redis_client.vector_key(patient_id)
    client.delete(key)
    if chunks:
        client.rpush(key, *chunks)
    logger.info("embed_plan: stored %d chunks for patient=%s", len(chunks), patient_id)


def get_chunks(patient_id: str) -> list[str]:
    """Retrieve stored plan chunks oldest-first."""
    client = redis_client.get_client()
    return client.lrange(redis_client.vector_key(patient_id), 0, -1)


# ── Retrieval ─────────────────────────────────────────────────────────────────

_RETRIEVAL_PROMPT = """\
You are a care-plan retrieval assistant. Given the care plan chunks and a query,
return ONLY a JSON array of the most relevant chunk strings (up to {max_chunks}).
Return only the chunks that directly address the query. If no chunk is relevant,
return an empty array [].

Return ONLY valid JSON — no explanation, no markdown.

Care plan chunks:
{chunks_json}

Query: {query}"""


def lookup_plan(patient_id: str, query: str) -> list[str]:
    """
    Semantic search over the patient's stored care plan chunks.
    Returns up to _MAX_CHUNKS_TO_RETURN relevant chunk strings.

    Falls back to returning all chunks if Claude retrieval fails.
    """
    chunks = get_chunks(patient_id)
    if not chunks:
        logger.warning("lookup_plan: no chunks for patient=%s", patient_id)
        return []

    # Short-circuit: if only a few chunks, return them all directly.
    if len(chunks) <= _MAX_CHUNKS_TO_RETURN:
        return chunks

    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        return chunks[:_MAX_CHUNKS_TO_RETURN]

    try:
        client = anthropic.Anthropic(api_key=api_key)
        prompt = _RETRIEVAL_PROMPT.format(
            max_chunks=_MAX_CHUNKS_TO_RETURN,
            chunks_json=json.dumps(chunks),
            query=query,
        )
        response = client.messages.create(
            model=MODEL,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.content[0].text.strip() if response.content else "[]"
        # Strip markdown fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1].lstrip("json").strip()
        selected: list[str] = json.loads(raw)
        if isinstance(selected, list):
            return selected[:_MAX_CHUNKS_TO_RETURN]
    except Exception as exc:
        logger.warning("lookup_plan retrieval error: %s — returning top chunks", exc)

    return chunks[:_MAX_CHUNKS_TO_RETURN]
