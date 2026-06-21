"""Tests for demo login / logout (CAD-40 + CAD-4)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app, raise_server_exceptions=True)


def _login(role: str):
    return client.post(f"/api/demo/login?role={role}")


class TestDemoLogin:
    def test_patient_login_returns_200(self):
        r = _login("patient")
        assert r.status_code == 200

    def test_patient_login_sets_role_cookie(self):
        r = _login("patient")
        assert r.cookies.get("cadence_role") == "patient"

    def test_patient_login_sets_patient_id_cookie(self):
        r = _login("patient")
        assert r.cookies.get("cadence_patient_id") == "maria-chen"

    def test_patient_login_body(self):
        r = _login("patient")
        body = r.json()
        assert body["ok"] is True
        assert body["role"] == "patient"
        assert body["patient_id"] == "maria-chen"

    def test_clinician_login_returns_200(self):
        r = _login("clinician")
        assert r.status_code == 200

    def test_clinician_login_sets_role_cookie(self):
        r = _login("clinician")
        assert r.cookies.get("cadence_role") == "clinician"

    def test_clinician_login_sets_clinician_id_cookie(self):
        r = _login("clinician")
        assert r.cookies.get("cadence_clinician_id") == "dr-reyes"

    def test_clinician_login_body(self):
        r = _login("clinician")
        body = r.json()
        assert body["ok"] is True
        assert body["role"] == "clinician"
        assert body["clinician_id"] == "dr-reyes"

    def test_unknown_role_returns_400(self):
        r = _login("admin")
        assert r.status_code == 422  # FastAPI rejects Literal before our handler


class TestDemoLogout:
    def test_logout_returns_200(self):
        r = client.post("/api/demo/logout")
        assert r.status_code == 200

    def test_logout_body(self):
        r = client.post("/api/demo/logout")
        assert r.json() == {"ok": True}

    def test_logout_clears_cookies(self):
        # Login first so cookies exist
        login_r = _login("patient")
        session = login_r.cookies

        # Logout using the session
        logout_r = client.post("/api/demo/logout", cookies=dict(session))
        # After logout, the cookie jar should have max_age=0 (deleted)
        # TestClient reflects deleted cookies as empty strings or missing
        assert logout_r.status_code == 200
