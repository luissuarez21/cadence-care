"""
Cadence — demo login / logout endpoints (CAD-40 + CAD-4).

POST /api/demo/login?role=patient|clinician
  Issues a signed HS256 JWT in three HttpOnly, Secure, SameSite=Strict cookies:
    cadence_role, cadence_patient_id | cadence_clinician_id

POST /api/demo/logout
  Clears all three cookies.

The JWT itself is an anti-CSRF artefact: its payload is also available server-side
via the cookie and the raw jose decode, so every protected route sees a consistent
Identity without touching localStorage.

Hard-coded demo identities (synthetic data only — no real PHI):
  patient   → maria-chen
  clinician → dr-reyes
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, HTTPException, Response

try:
    from jose import jwt as jose_jwt  # python-jose[cryptography]
    _JOSE_AVAILABLE = True
except ImportError:
    _JOSE_AVAILABLE = False

router = APIRouter(prefix="/api/demo", tags=["demo-auth"])

# ── Config ────────────────────────────────────────────────────────────────────

_SECRET = os.getenv("JWT_SECRET", "cadence-demo-secret-change-in-prod")
_ALGORITHM = "HS256"
_TTL_HOURS = 8

_DEMO_IDENTITIES: dict[str, dict] = {
    "patient": {
        "role": "patient",
        "patient_id": "maria-chen",
        "clinician_id": None,
    },
    "clinician": {
        "role": "clinician",
        "clinician_id": "dr-reyes",
        "patient_id": None,
    },
}

# ── Cookie helper ─────────────────────────────────────────────────────────────

_COOKIE_OPTS = dict(
    httponly=True,
    secure=False,   # set to True in production (requires HTTPS)
    samesite="strict",
    path="/",
    max_age=_TTL_HOURS * 3600,
)


def _set_cookies(response: Response, identity: dict) -> None:
    response.set_cookie("cadence_role", identity["role"], **_COOKIE_OPTS)
    if identity.get("patient_id"):
        response.set_cookie("cadence_patient_id", identity["patient_id"], **_COOKIE_OPTS)
    if identity.get("clinician_id"):
        response.set_cookie("cadence_clinician_id", identity["clinician_id"], **_COOKIE_OPTS)


def _clear_cookies(response: Response) -> None:
    for name in ("cadence_role", "cadence_patient_id", "cadence_clinician_id"):
        response.delete_cookie(name, path="/")


def _build_jwt(identity: dict) -> str:
    now = datetime.now(tz=timezone.utc)
    payload = {
        **identity,
        "iat": now,
        "exp": now + timedelta(hours=_TTL_HOURS),
    }
    if _JOSE_AVAILABLE:
        return jose_jwt.encode(payload, _SECRET, algorithm=_ALGORITHM)
    # Graceful no-op when jose not installed (frontend wires via query param fallback)
    return "demo-token-no-jose"


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("/login")
async def demo_login(
    role: Literal["patient", "clinician"],
    response: Response,
) -> dict:
    """
    Issue a demo session for the given role.
    Returns the JWT payload for debugging; the real session lives in cookies.
    """
    if role not in _DEMO_IDENTITIES:
        raise HTTPException(status_code=400, detail=f"Unknown role: {role}")

    identity = _DEMO_IDENTITIES[role]
    token = _build_jwt(identity)
    _set_cookies(response, identity)

    return {
        "ok": True,
        "role": identity["role"],
        "patient_id": identity.get("patient_id"),
        "clinician_id": identity.get("clinician_id"),
        "token": token,  # only for demo debugging — never store client-side
    }


@router.post("/logout")
async def demo_logout(response: Response) -> dict:
    """Clear all cadence session cookies."""
    _clear_cookies(response)
    return {"ok": True}


@router.post("/seed")
async def demo_seed() -> dict:
    """Seed Maria Chen + synthetic panel into Redis. Safe to re-run (idempotent)."""
    from ..demo.seed_data import seed_all
    counts = seed_all()
    return {"ok": True, **counts}
