"""
Cadence — FastAPI application entrypoint.

Story 1: wires CORS for the Vite frontend, initializes Sentry (PII-scrubbed) if a
DSN is configured, and registers every router. All endpoints currently return
synthetic mock data matching api_models.py so the frontend and Luis can hit a
running server immediately. Real Redis/agent wiring lands story-by-story.

Run locally:  uvicorn backend.main:app --reload --port 8000
"""

from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routes import chat, clinician, ingest, patient, push

# ── Sentry (PII scrubbing required — never let PHI leave the server) ──────────
_SENTRY_DSN = os.getenv("SENTRY_DSN")
if _SENTRY_DSN:
    import sentry_sdk

    # Health fields that must never appear in breadcrumbs / error payloads.
    _PHI_FIELDS = {
        "bp_systolic", "bp_diastolic", "headache_severity", "swelling_location",
        "vision_changes", "fetal_movement", "raw_text", "symptom", "patient_id",
    }

    def _scrub(event, _hint):
        try:
            req = event.get("request", {})
            if isinstance(req.get("data"), dict):
                for k in list(req["data"]):
                    if k in _PHI_FIELDS:
                        req["data"][k] = "[scrubbed]"
        except Exception:
            pass
        return event

    sentry_sdk.init(
        dsn=_SENTRY_DSN,
        send_default_pii=False,
        before_send=_scrub,
        traces_sample_rate=float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.0")),
    )

# ── App ──────────────────────────────────────────────────────────────────────
app = FastAPI(title="Cadence API", version="0.1.0")

# CORS for the Vite frontend (configurable via comma-separated CORS_ORIGINS).
_origins = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000",
).split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _origins if o.strip()],
    allow_credentials=True,  # required: JWT travels in an HttpOnly cookie
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ──────────────────────────────────────────────────────────────────
app.include_router(chat.router)
app.include_router(patient.router)
app.include_router(ingest.router)
app.include_router(clinician.router)
app.include_router(clinician.ws_router)  # WS /ws/escalations (no /api prefix)
app.include_router(push.router)


@app.get("/api/health", tags=["meta"])
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "cadence-api"}
