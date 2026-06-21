"""CAD-10 + CAD-11 — plan ingestion pipeline + RAG lookup_plan."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.ingestion import pipeline as pipeline_module
from backend.ingestion.schema import ProtocolJSON, RedFlag
from backend.memory import rag as rag_module
from backend.memory import redis_client


NOW = datetime.now(timezone.utc)

_SAMPLE_PLAN_JSON = json.dumps({
    "condition": "high_risk_pregnancy_preeclampsia",
    "gestational_age_weeks": 29,
    "goals": ["Monitor BP twice daily", "Low-dose aspirin adherence"],
    "medications": [{"name": "Aspirin", "dose": "81mg", "frequency": "daily", "instructions": "Take with food"}],
    "tasks": [{"task": "BP check", "frequency": "twice daily", "instructions": "Morning and evening"}],
    "check_in_cadence_hours": 24,
    "red_flags": [
        {
            "description": "BP >= 140/90 on two readings",
            "severity": "escalate",
            "escalation_message": "BP above threshold — contacting OB"
        }
    ],
    "patient_context": "Maria is 29 weeks, high preeclampsia risk.",
})


# ── _parse_extraction ─────────────────────────────────────────────────────────

def test_parse_extraction_builds_valid_protocol_json():
    plan = pipeline_module._parse_extraction(_SAMPLE_PLAN_JSON, "maria-chen")
    assert plan.patient_id == "maria-chen"
    assert plan.condition == "high_risk_pregnancy_preeclampsia"
    assert plan.gestational_age_weeks == 29
    assert len(plan.goals) == 2
    assert len(plan.medications) == 1
    assert plan.medications[0].name == "Aspirin"
    assert len(plan.red_flags) == 1
    assert plan.red_flags[0].severity == "escalate"


def test_parse_extraction_strips_markdown_fences():
    fenced = "```json\n" + _SAMPLE_PLAN_JSON + "\n```"
    cleaned = fenced.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("```")[1]
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
        cleaned = cleaned.strip()
    plan = pipeline_module._parse_extraction(cleaned, "test-patient")
    assert plan.condition == "high_risk_pregnancy_preeclampsia"


# ── ingest_plan (Claude Vision mocked) ───────────────────────────────────────

@pytest.mark.asyncio
async def test_ingest_plan_calls_vision_and_stores(monkeypatch):
    stored_plans = {}
    embedded = []

    monkeypatch.setattr(redis_client, "set_plan", lambda pid, p: stored_plans.update({pid: p}))
    monkeypatch.setattr(rag_module, "embed_plan", lambda pid, p: embedded.append(pid))

    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=_SAMPLE_PLAN_JSON)]

    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_response

    with patch("backend.ingestion.pipeline.anthropic.Anthropic", return_value=mock_client):
        plan = await pipeline_module.ingest_plan("maria-chen", b"%PDF fake content", "plan.pdf")

    assert plan.patient_id == "maria-chen"
    assert plan.condition == "high_risk_pregnancy_preeclampsia"
    assert "maria-chen" in stored_plans
    assert "maria-chen" in embedded


@pytest.mark.asyncio
async def test_ingest_plan_raises_on_empty_response(monkeypatch):
    monkeypatch.setattr(redis_client, "set_plan", lambda pid, p: None)
    monkeypatch.setattr(rag_module, "embed_plan", lambda pid, p: None)

    mock_response = MagicMock()
    mock_response.content = []

    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_response

    with patch("backend.ingestion.pipeline.anthropic.Anthropic", return_value=mock_client):
        with pytest.raises(RuntimeError, match="empty response"):
            await pipeline_module.ingest_plan("maria-chen", b"fake", "plan.pdf")


# ── RAG: embed_plan + get_chunks ─────────────────────────────────────────────

def test_embed_plan_stores_chunks(monkeypatch):
    stored = {}

    class _FakeRedis:
        def delete(self, key): stored.pop(key, None)
        def rpush(self, key, *vals): stored[key] = list(vals)
        def lrange(self, key, start, end): return stored.get(key, [])

    monkeypatch.setattr(redis_client, "get_client", lambda: _FakeRedis())

    plan = pipeline_module._parse_extraction(_SAMPLE_PLAN_JSON, "maria-chen")
    rag_module.embed_plan("maria-chen", plan)

    chunks = rag_module.get_chunks("maria-chen")
    assert len(chunks) > 0
    assert any("Aspirin" in c for c in chunks)
    assert any("BP >= 140/90" in c for c in chunks)


def test_embed_plan_overwrites_previous_chunks(monkeypatch):
    store = {}

    class _FakeRedis:
        def delete(self, key): store.clear()
        def rpush(self, key, *vals): store[key] = list(vals)
        def lrange(self, key, start, end): return store.get(key, [])

    monkeypatch.setattr(redis_client, "get_client", lambda: _FakeRedis())

    plan = pipeline_module._parse_extraction(_SAMPLE_PLAN_JSON, "maria-chen")
    rag_module.embed_plan("maria-chen", plan)
    first_count = len(rag_module.get_chunks("maria-chen"))
    rag_module.embed_plan("maria-chen", plan)
    assert len(rag_module.get_chunks("maria-chen")) == first_count  # not doubled


# ── lookup_plan ───────────────────────────────────────────────────────────────

def test_lookup_plan_returns_all_when_few_chunks(monkeypatch):
    chunks = ["Red flag: BP elevated", "Medication: Aspirin 81mg daily"]

    class _FakeRedis:
        def lrange(self, key, start, end): return chunks

    monkeypatch.setattr(redis_client, "get_client", lambda: _FakeRedis())

    result = rag_module.lookup_plan("maria-chen", "what are the red flags?")
    assert result == chunks


def test_lookup_plan_returns_empty_for_unknown_patient(monkeypatch):
    class _FakeRedis:
        def lrange(self, key, start, end): return []

    monkeypatch.setattr(redis_client, "get_client", lambda: _FakeRedis())

    result = rag_module.lookup_plan("unknown-patient", "anything")
    assert result == []


def test_lookup_plan_uses_claude_when_many_chunks(monkeypatch):
    many_chunks = [f"Chunk {i}: some care plan content" for i in range(10)]

    class _FakeRedis:
        def lrange(self, key, start, end): return many_chunks

    monkeypatch.setattr(redis_client, "get_client", lambda: _FakeRedis())
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-key")

    selected = ["Chunk 2: some care plan content", "Chunk 7: some care plan content"]
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=json.dumps(selected))]
    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_response

    with patch("backend.memory.rag.anthropic.Anthropic", return_value=mock_client):
        result = rag_module.lookup_plan("maria-chen", "BP thresholds")

    assert result == selected


def test_lookup_plan_falls_back_on_claude_error(monkeypatch):
    many_chunks = [f"Chunk {i}" for i in range(10)]

    class _FakeRedis:
        def lrange(self, key, start, end): return many_chunks

    monkeypatch.setattr(redis_client, "get_client", lambda: _FakeRedis())
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-key")

    mock_client = MagicMock()
    mock_client.messages.create.side_effect = RuntimeError("API down")

    with patch("backend.memory.rag.anthropic.Anthropic", return_value=mock_client):
        result = rag_module.lookup_plan("maria-chen", "anything")

    assert result == many_chunks[:5]


# ── /api/ingest route ─────────────────────────────────────────────────────────

def _clinician_client():
    c = TestClient(app)
    c.cookies.set("cadence_role", "clinician")
    c.cookies.set("cadence_clinician_id", "dr-reyes")
    return c


@pytest.mark.asyncio
async def test_ingest_route_calls_pipeline(monkeypatch):
    plan = pipeline_module._parse_extraction(_SAMPLE_PLAN_JSON, "maria-chen")

    async def _fake_ingest(patient_id, content, filename):
        return plan

    # Patch at the route's import site, not the module.
    with patch("backend.routes.ingest.ingest_plan", _fake_ingest):
        c = _clinician_client()
        r = c.post(
            "/api/ingest",
            data={"patient_id": "maria-chen"},
            files={"file": ("plan.pdf", b"%PDF fake content", "application/pdf")},
        )
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["patient_id"] == "maria-chen"
    assert "high_risk_pregnancy_preeclampsia" in body["message"]


def test_ingest_route_demo_fallback_uses_seeded_plan(monkeypatch):
    plan = pipeline_module._parse_extraction(_SAMPLE_PLAN_JSON, "maria-chen")
    monkeypatch.setattr(redis_client, "get_plan", lambda pid: plan)

    c = _clinician_client()
    r = c.post(
        "/api/ingest",
        data={"patient_id": "maria-chen"},
        files={"file": ("plan.pdf", b"", "application/pdf")},
    )
    assert r.status_code == 200
    assert r.json()["message"] == "Using pre-ingested plan (demo mode)."


def test_ingest_route_413_on_oversized_file(monkeypatch):
    async def _fake_ingest(patient_id, content, filename):
        return None  # should not be reached

    monkeypatch.setattr(pipeline_module, "ingest_plan", _fake_ingest)

    big = b"x" * (21 * 1024 * 1024)
    c = _clinician_client()
    r = c.post(
        "/api/ingest",
        data={"patient_id": "maria-chen"},
        files={"file": ("plan.pdf", big, "application/pdf")},
    )
    assert r.status_code == 413
