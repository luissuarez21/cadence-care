"""
Cadence — Golden path cache + DEMO_MODE fallback (CAD-37)

The demo cannot fail live. This module pre-caches every AI response in the 90-second
demo script so the pitch is deterministic and fast — WITHOUT silently faking the
product.

Provenance is explicit (per the "no silent mocks/no-ops" rule):

  - DEMO_MODE off (default)  → LIVE-FIRST. Always call the real model. Only if the
    live call RAISES do we fall back to the cached answer (source="fallback",
    logged as a warning). If there's no cached answer, the error propagates.
  - DEMO_MODE=true (explicit)→ serve the cached answer for scripted turns
    (source="demo_mode"). Unknown/unscripted inputs still go live (source="live").

Every served response reports where it came from ("live" | "demo_mode" | "fallback"),
so a cache hit is never invisible. The cache lives in backend/demo/ and is only used
by demo wiring — never the real patient path.
"""

from __future__ import annotations

import logging
import os
from typing import Awaitable, Callable, NamedTuple, Optional

logger = logging.getLogger("cadence.golden_path")


class Served(NamedTuple):
    """A served response plus where it came from (never hidden)."""
    response: str
    source: str  # "live" | "demo_mode" | "fallback"


def demo_mode_enabled() -> bool:
    """True only when DEMO_MODE is explicitly turned on. Off by default."""
    return os.getenv("DEMO_MODE", "").strip().lower() in ("1", "true", "yes", "on")


# ─────────────────────────────────────────────────────────────────────────────
# The pre-cached 90-second demo script (Maria Chen golden path).
# Chat turns are keyed by the patient's exact message; structured AI outputs by a
# step name. These strings are reviewed copy — what the audience should see.
# ─────────────────────────────────────────────────────────────────────────────

CHAT_GOLDEN: dict[str, str] = {
    "__opening__": (
        "Hi Maria! Evening check-in time. How are you feeling? Let's start with your "
        "blood pressure — what did you get tonight?"
    ),
    "142/91": "Thanks. Can you take a second reading in about 5 minutes and share it with me?",
    "140/90": (
        "Got it. Both readings are above the threshold from your care plan. I've flagged "
        "this for Dr. Reyes and added it to your appointment summary — she'll be in touch. "
        "How's your head feeling tonight?"
    ),
}

# Structured AI outputs in the script (already deterministic in our engine, cached
# here so the whole sequence can run with zero live calls in DEMO_MODE).
STEP_GOLDEN: dict[str, str] = {
    "risk_score": (
        "escalate — Two blood pressure readings today were at or above 140/90 "
        "(142/91, 140/90), which meets the care plan's threshold for notifying the OB."
    ),
    "escalation_summary": (
        "Maria Chen — BP 142/91 and 140/90 this evening. She also reported headaches on "
        "Day 3, 6, and 9 of this monitoring period — frequency increasing. No visual "
        "changes reported tonight. Recommended action: contact patient, consider "
        "advancing appointment."
    ),
    "judge": "appropriate: YES (confidence 0.97)",
}

# The exact ordered sequence the 90-second demo plays (for the end-to-end test).
DEMO_SEQUENCE: list[tuple[str, str]] = [
    ("chat", "__opening__"),
    ("chat", "142/91"),
    ("chat", "140/90"),
    ("step", "risk_score"),
    ("step", "escalation_summary"),
    ("step", "judge"),
]


# A live model call is `() -> str`, sync or async. Injected so this stays testable.
LiveCall = Callable[[], "str | Awaitable[str]"]


async def _maybe_await(value):
    import asyncio
    return await value if asyncio.iscoroutine(value) else value


async def serve(key: str, live: LiveCall, *, cache: dict[str, str]) -> Served:
    """
    Core policy. Live-first by default; DEMO_MODE serves the cache for known keys.
    The cache is also a labeled last-resort if a live call fails.
    """
    cached = cache.get(key)

    if demo_mode_enabled():
        if cached is not None:
            logger.info("golden_path: DEMO_MODE cache hit for %r", key)
            return Served(cached, "demo_mode")
        # Unknown input even in demo mode → go live rather than invent an answer.
        logger.warning("golden_path: DEMO_MODE miss for %r — running live", key)
        return Served(await _maybe_await(live()), "live")

    # Live-first.
    try:
        return Served(await _maybe_await(live()), "live")
    except Exception as exc:  # explicit, logged fallback — never silent
        if cached is not None:
            logger.warning(
                "golden_path: live call failed for %r (%s) — serving cached fallback",
                key, type(exc).__name__,
            )
            return Served(cached, "fallback")
        raise


async def chat_reply(patient_text: str, live: LiveCall) -> Served:
    """Demo wrapper for a patient chat turn."""
    return await serve(patient_text.strip(), live, cache=CHAT_GOLDEN)


async def step_output(step: str, live: LiveCall) -> Served:
    """Demo wrapper for a scripted structured AI output (risk/escalation/judge)."""
    return await serve(step, live, cache=STEP_GOLDEN)
