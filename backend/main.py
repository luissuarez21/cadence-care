"""
Cadence — FastAPI application entrypoint.

Wires CORS for the Vite frontend and registers every router.
All endpoints read from Redis; no mock data remains.

Run locally:  uvicorn backend.main:app --reload --port 8000
"""

from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routes import auth_routes, chat, clinician, ingest, patient, push

# ── App ──────────────────────────────────────────────────────────────────────
app = FastAPI(title="Cadence API", version="0.1.0")

# CORS for the Vite frontend (configurable via comma-separated CORS_ORIGINS).
_origins = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173,http://localhost:5174,http://127.0.0.1:5174,http://localhost:3000",
).split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _origins if o.strip()],
    allow_credentials=True,  # required: JWT travels in an HttpOnly cookie
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ──────────────────────────────────────────────────────────────────
app.include_router(auth_routes.router)
app.include_router(chat.router)
app.include_router(patient.router)
app.include_router(ingest.router)
app.include_router(clinician.router)
app.include_router(clinician.ws_router)  # WS /ws/escalations (no /api prefix)
app.include_router(push.router)


@app.get("/api/health", tags=["meta"])
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "cadence-api"}
