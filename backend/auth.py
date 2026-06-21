"""
Cadence — request auth (thin, swappable).

The full login flow (issuing a signed JWT in an HttpOnly cookie) is its own story
— "Demo login / session: patient vs clinician role bootstrap". This module is the
server-side enforcement surface every protected route depends on. It already:

  - reads the session identity from cookies (`cadence_role`, `cadence_patient_id`,
    `cadence_clinician_id`) when a login session exists, and enforces the role, and
  - falls back to a demo identity (taken from the request) when no session cookie
    is present yet, so the frontend can integrate before login lands.

When the login story adds real JWT issuance, only `get_identity` changes — the
`require_patient` / `require_clinician` dependencies stay the same.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from fastapi import HTTPException, Request


@dataclass
class Identity:
    role: Optional[str] = None          # "patient" | "clinician" | None (demo)
    patient_id: Optional[str] = None
    clinician_id: Optional[str] = None
    authenticated: bool = False         # True when a real session cookie was present


def get_identity(request: Request) -> Identity:
    role = request.cookies.get("cadence_role")
    if role is None:
        return Identity(authenticated=False)  # demo: no login session yet
    return Identity(
        role=role,
        patient_id=request.cookies.get("cadence_patient_id"),
        clinician_id=request.cookies.get("cadence_clinician_id"),
        authenticated=True,
    )


def require_patient(request: Request) -> Identity:
    ident = get_identity(request)
    if ident.authenticated and ident.role != "patient":
        raise HTTPException(status_code=403, detail="Patient role required.")
    return ident


def require_clinician(request: Request) -> Identity:
    ident = get_identity(request)
    if ident.authenticated and ident.role != "clinician":
        raise HTTPException(status_code=403, detail="Clinician role required.")
    return ident


def resolve_patient_id(ident: Identity, requested_patient_id: str) -> str:
    """
    Decide which patient_id a request may act on, enforcing minimum-necessary access.

    - Authenticated patient: may only ever touch their own data.
    - Demo (no session yet): trust the requested id so the frontend can integrate.
    """
    if ident.authenticated:
        if ident.patient_id and requested_patient_id and requested_patient_id != ident.patient_id:
            raise HTTPException(status_code=403, detail="Cannot access another patient's data.")
        return ident.patient_id or requested_patient_id
    return requested_patient_id
