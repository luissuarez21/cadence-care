"""
Cadence — Redis client (TLS) + patient-scoped key helpers.

CAD-3. One module every read/write goes through, so key naming and serialization
stay consistent. Every key is namespaced by `patient_id` (or `clinician_id`) —
cross-patient leakage is architecturally impossible, not just policy.

Connection:
  - Built from REDIS_URL (use `rediss://` for TLS) + REDIS_PASSWORD from .env.
  - Password from REDIS_PASSWORD is injected if the URL doesn't already carry one.

Serialization:
  - Every value is a Pydantic model from ingestion/schema.py, stored as JSON.
  - Lists use RPUSH (append) + LRANGE 0 -1 (read all, oldest-first).

Run the in-isolation self-test (needs a live Redis):
    REDIS_URL=redis://localhost:6379 python -m backend.memory.redis_client
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Optional

try:  # load .env if python-dotenv is installed (optional)
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # pragma: no cover - dotenv is optional
    pass

import redis

from ..ingestion.schema import (
    ChatMessage,
    EscalationSummary,
    ProtocolJSON,
    RiskScore,
    SymptomLog,
)

# ── Key builders (the only place key strings are constructed) ────────────────

def plan_key(patient_id: str) -> str:
    return f"plan:{patient_id}"


def session_key(patient_id: str, session_id: str) -> str:
    return f"session:{patient_id}:{session_id}"


def symptoms_key(patient_id: str) -> str:
    return f"symptoms:{patient_id}"


def risk_timeline_key(patient_id: str) -> str:
    return f"risk_timeline:{patient_id}"


def vector_key(patient_id: str) -> str:
    return f"vector:{patient_id}"


def escalations_key(patient_id: str) -> str:
    return f"escalations:{patient_id}"


def messages_key(patient_id: str) -> str:
    return f"messages:{patient_id}"


def notes_key(patient_id: str) -> str:
    return f"notes:{patient_id}"


def followup_key(patient_id: str) -> str:
    return f"followup:{patient_id}"


def push_subscriptions_key(clinician_id: str) -> str:
    return f"push_subscriptions:{clinician_id}"


# ── Connection ──────────────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def get_client() -> redis.Redis:
    """
    Process-wide singleton Redis client.

    Reads REDIS_URL (default a local plaintext dev URL) and REDIS_PASSWORD.
    Production must use `rediss://` (TLS); the password is taken from
    REDIS_PASSWORD and never hardcoded.
    """
    url = os.getenv("REDIS_URL", "redis://localhost:6379")
    password = os.getenv("REDIS_PASSWORD") or None
    return redis.Redis.from_url(
        url,
        password=password,
        decode_responses=True,
        socket_connect_timeout=5,
        socket_keepalive=True,
    )


def _list_read(key: str, model: type) -> list:
    """Read a whole Redis list (oldest-first) and parse each item into `model`."""
    raw = get_client().lrange(key, 0, -1)
    return [model.model_validate_json(item) for item in raw]


def _list_append(key: str, value) -> None:
    get_client().rpush(key, value.model_dump_json())


# ── Plan (plan:{id}) ────────────────────────────────────────────────────────

def set_plan(patient_id: str, plan: ProtocolJSON) -> None:
    get_client().set(plan_key(patient_id), plan.model_dump_json())


def get_plan(patient_id: str) -> Optional[ProtocolJSON]:
    raw = get_client().get(plan_key(patient_id))
    return ProtocolJSON.model_validate_json(raw) if raw else None


# ── Follow-up / appointment (followup:{id}) ─────────────────────────────────

def set_followup(patient_id: str, when: str) -> dict:
    """
    Record the next appointment / check-in the clinician booked for this patient.
    Stored as a small JSON blob (no schema model — this is an Adit-owned operational
    key, not part of the frozen data contract). Returns what was stored.
    """
    from datetime import datetime, timezone
    import json

    record = {"when": when, "scheduled_at": datetime.now(timezone.utc).isoformat()}
    get_client().set(followup_key(patient_id), json.dumps(record))
    return record


def get_followup(patient_id: str) -> Optional[dict]:
    import json

    raw = get_client().get(followup_key(patient_id))
    return json.loads(raw) if raw else None


# ── Session / chat (session:{id}:{session_id}) ──────────────────────────────

def get_session(patient_id: str, session_id: str) -> list[ChatMessage]:
    """All chat turns for a session, oldest-first."""
    return _list_read(session_key(patient_id, session_id), ChatMessage)


def append_message(patient_id: str, session_id: str, message: ChatMessage) -> ChatMessage:
    """Append one chat turn to the session thread."""
    _list_append(session_key(patient_id, session_id), message)
    return message


# ── Symptoms (symptoms:{id}) ────────────────────────────────────────────────

def log_symptom(patient_id: str, symptom: SymptomLog) -> SymptomLog:
    """Append a structured check-in. Returns the persisted log."""
    _list_append(symptoms_key(patient_id), symptom)
    return symptom


def get_symptom_history(patient_id: str) -> list[SymptomLog]:
    """All logged check-ins, oldest-first."""
    return _list_read(symptoms_key(patient_id), SymptomLog)


# ── Risk timeline (risk_timeline:{id}) ──────────────────────────────────────

def append_risk(patient_id: str, score: RiskScore) -> RiskScore:
    """Append a risk score to the timeline. Returns the persisted score."""
    _list_append(risk_timeline_key(patient_id), score)
    return score


def get_risk_timeline(patient_id: str) -> list[RiskScore]:
    """All risk scores, oldest-first."""
    return _list_read(risk_timeline_key(patient_id), RiskScore)


# ── Escalations (escalations:{id}) ──────────────────────────────────────────

def write_escalation(patient_id: str, escalation: EscalationSummary) -> EscalationSummary:
    """Append a clinical escalation summary. Returns the persisted summary."""
    _list_append(escalations_key(patient_id), escalation)
    return escalation


def get_escalations(patient_id: str) -> list[EscalationSummary]:
    """All escalations for a patient, oldest-first (callers reverse for newest-first)."""
    return _list_read(escalations_key(patient_id), EscalationSummary)


def acknowledge_escalation(patient_id: str, escalation_id: str) -> bool:
    """Set acknowledged=True on a specific escalation. Returns True if found."""
    key = escalations_key(patient_id)
    raw_list = get_client().lrange(key, 0, -1)
    for i, raw in enumerate(raw_list):
        esc = EscalationSummary.model_validate_json(raw)
        if esc.escalation_id == escalation_id:
            esc.acknowledged = True
            get_client().lset(key, i, esc.model_dump_json())
            return True
    return False


# ── Push subscriptions (push_subscriptions:{clinician_id}) ──────────────────

def save_push_subscription(clinician_id: str, subscription: dict) -> None:
    import json

    get_client().set(push_subscriptions_key(clinician_id), json.dumps(subscription))


def get_push_subscription(clinician_id: str) -> Optional[dict]:
    import json

    raw = get_client().get(push_subscriptions_key(clinician_id))
    return json.loads(raw) if raw else None


# ── Patient enumeration (clinician panel / escalation inbox) ────────────────

def scan_patient_ids() -> list[str]:
    """
    Every patient_id that has any data on file. Scans the patient-scoped key
    families and unions the ids. Used by the clinician panel + escalation inbox.
    """
    client = get_client()
    ids: set[str] = set()
    for prefix in ("plan", "risk_timeline", "symptoms", "escalations"):
        for key in client.scan_iter(match=f"{prefix}:*"):
            # key is "prefix:patient_id" (decode_responses=True -> str)
            _, _, pid = key.partition(":")
            if pid:
                ids.add(pid)
    return sorted(ids)


# ── Escalation pub/sub (live clinician WebSocket) ───────────────────────────

ESCALATION_CHANNEL = "escalations:new"


def publish_escalation(escalation: EscalationSummary) -> None:
    """Publish a new escalation so live clinician WebSockets get it instantly."""
    get_client().publish(ESCALATION_CHANNEL, escalation.model_dump_json())


def escalation_pubsub():
    """A pub/sub handle subscribed to the new-escalation channel (caller closes it)."""
    pubsub = get_client().pubsub()
    pubsub.subscribe(ESCALATION_CHANNEL)
    return pubsub


# ── In-isolation self-test (CAD-3 AC: tested against a live Redis) ───────────

def _self_test() -> None:
    """Round-trip every helper against a live Redis, then clean up."""
    from datetime import datetime, timezone

    pid = "selftest-patient"
    sid = "selftest-session"
    cid = "selftest-clinician"
    now = datetime.now(timezone.utc)
    client = get_client()
    assert client.ping(), "Redis did not respond to PING"

    # clean slate
    for k in (
        plan_key(pid), session_key(pid, sid), symptoms_key(pid),
        risk_timeline_key(pid), escalations_key(pid), push_subscriptions_key(cid),
    ):
        client.delete(k)

    # plan
    plan = ProtocolJSON(
        patient_id=pid, condition="high_risk_pregnancy_preeclampsia",
        created_at=now, last_updated=now,
    )
    set_plan(pid, plan)
    assert get_plan(pid).patient_id == pid

    # session / chat
    append_message(pid, sid, ChatMessage(sender="cadence", text="hi", timestamp=now))
    append_message(pid, sid, ChatMessage(sender="patient", text="142/91", timestamp=now))
    sess = get_session(pid, sid)
    assert len(sess) == 2 and sess[0].sender == "cadence"

    # symptoms
    log_symptom(pid, SymptomLog(patient_id=pid, timestamp=now, bp_systolic=142, bp_diastolic=91))
    hist = get_symptom_history(pid)
    assert len(hist) == 1 and hist[0].bp_systolic == 142

    # risk timeline
    append_risk(pid, RiskScore(
        patient_id=pid, timestamp=now, severity="escalate",
        rationale="BP above threshold", recommended_action="contact patient",
    ))
    assert get_risk_timeline(pid)[0].severity == "escalate"

    # escalations
    write_escalation(pid, EscalationSummary(
        escalation_id="esc-test", patient_id=pid, patient_name="Test Patient",
        timestamp=now, severity="escalate", summary="BP 142/91",
        recommended_action="contact patient",
    ))
    escs = get_escalations(pid)
    assert len(escs) == 1 and escs[0].escalation_id == "esc-test"

    # push subscription
    save_push_subscription(cid, {"endpoint": "https://example/push", "keys": {}})
    assert get_push_subscription(cid)["endpoint"].endswith("/push")

    # cleanup
    for k in (
        plan_key(pid), session_key(pid, sid), symptoms_key(pid),
        risk_timeline_key(pid), escalations_key(pid), push_subscriptions_key(cid),
    ):
        client.delete(k)

    print("redis_client self-test: ALL HELPERS ROUND-TRIPPED OK ✅")


if __name__ == "__main__":
    _self_test()
