"""
Cadence — Web Push notifications (CAD-18).

Zero-PHI escalation alert to the clinician's browser.

The push payload is deliberately minimal:
    { "title": "Cadence", "body": "A patient needs your attention — open dashboard." }
No patient name, no symptom text, no clinical detail. The clinician taps the
notification, lands on their authenticated dashboard, and reads the full summary there.

Key lifecycle:
  1. Generate a VAPID keypair once:
         python -m backend.notifications.push --generate-keys
     Paste the output into your .env as VAPID_PUBLIC_KEY / VAPID_PRIVATE_KEY.
  2. Frontend POSTs the browser PushSubscription JSON to POST /api/push/subscribe.
     redis_client.save_push_subscription(clinician_id, subscription) stores it.
  3. When escalate_to_clinician fires, handler.py calls notify_escalation(escalation),
     which fans out a webpush() to every stored subscription.

Dependencies: pywebpush (already in requirements.txt).
"""

from __future__ import annotations

import json
import logging
import os
from typing import Optional

logger = logging.getLogger("cadence.push")

# ── VAPID config (loaded once at import time) ────────────────────────────────

_VAPID_PRIVATE_KEY: Optional[str] = None
_VAPID_CLAIMS: Optional[dict] = None


def _vapid_ready() -> bool:
    """Return True if VAPID env vars are set and non-empty."""
    return bool(
        os.getenv("VAPID_PRIVATE_KEY") and os.getenv("VAPID_PUBLIC_KEY")
    )


def _get_claims() -> dict:
    global _VAPID_CLAIMS
    if _VAPID_CLAIMS is None:
        subject = os.getenv("VAPID_SUBJECT", "mailto:team@cadence.health")
        _VAPID_CLAIMS = {"sub": subject}
    return _VAPID_CLAIMS


# ── Core push function ───────────────────────────────────────────────────────

_ZERO_PHI_PAYLOAD = json.dumps({
    "title": "Cadence",
    "body": "A patient needs your attention — open dashboard.",
})


def send_push(subscription: dict) -> None:
    """
    Fire a single zero-PHI Web Push to one browser subscription.

    subscription: the raw PushSubscription JSON from the browser
        { "endpoint": "...", "keys": { "auth": "...", "p256dh": "..." } }
    """
    from pywebpush import webpush, WebPushException

    private_key = os.getenv("VAPID_PRIVATE_KEY", "")
    if not private_key:
        logger.warning("VAPID_PRIVATE_KEY not set — skipping push")
        return

    try:
        webpush(
            subscription_info=subscription,
            data=_ZERO_PHI_PAYLOAD,
            vapid_private_key=private_key,
            vapid_claims=_get_claims(),
        )
    except WebPushException as exc:
        # 410 Gone = subscription expired; caller should remove it.
        logger.warning("WebPush failed (status=%s): %s", exc.response and exc.response.status_code, exc)
        raise
    except Exception as exc:
        logger.warning("WebPush unexpected error: %s", exc)
        raise


def notify_escalation(escalation) -> None:  # EscalationSummary, avoid circular import
    """
    Fan out a zero-PHI push to every stored clinician subscription.

    Called by escalation/handler.py _notify_clinician() — any exception here
    is caught by that caller so the escalation always succeeds regardless.
    """
    if not _vapid_ready():
        logger.info("VAPID keys not configured — Web Push skipped")
        return

    from ..memory import redis_client

    # In the demo there's one clinician; in production scan all subscription keys.
    client = redis_client.get_client()
    pushed = 0
    for key in client.scan_iter(match="push_subscriptions:*"):
        raw = client.get(key)
        if not raw:
            continue
        try:
            subscription = json.loads(raw)
            send_push(subscription)
            pushed += 1
        except Exception:
            # Stale or expired subscription — log and continue to the next.
            logger.warning("Failed to push to %s — skipping", key)

    logger.info("notify_escalation: pushed to %d subscription(s)", pushed)


# ── CLI: generate a VAPID keypair ────────────────────────────────────────────

def _generate_keys() -> None:
    """Print a fresh VAPID keypair ready to paste into .env."""
    import base64
    from py_vapid import Vapid
    from cryptography.hazmat.primitives.serialization import (
        Encoding, PublicFormat, PrivateFormat, NoEncryption,
    )

    v = Vapid()
    v.generate_keys()

    pub_bytes = v.public_key.public_bytes(Encoding.X962, PublicFormat.UncompressedPoint)
    pub_b64 = base64.urlsafe_b64encode(pub_bytes).rstrip(b"=").decode()

    priv_pem_lines = (
        v.private_key.private_bytes(Encoding.PEM, PrivateFormat.TraditionalOpenSSL, NoEncryption())
        .decode()
        .splitlines()
    )
    # Strip PEM header/footer; store the raw base64 block as the env var.
    priv_b64 = "".join(priv_pem_lines[1:-1])

    print("# Paste these into your .env:")
    print(f"VAPID_PUBLIC_KEY={pub_b64}")
    print(f"VAPID_PRIVATE_KEY={priv_b64}")
    print("VAPID_SUBJECT=mailto:team@cadence.health")


if __name__ == "__main__":
    import sys
    if "--generate-keys" in sys.argv:
        _generate_keys()
    else:
        print("Usage: python -m backend.notifications.push --generate-keys")
