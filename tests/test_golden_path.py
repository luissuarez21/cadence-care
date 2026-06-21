"""
CAD-37 — tests for the golden-path cache + DEMO_MODE policy.

Verifies the "no silent fallback" contract: live-first by default, cache only on
explicit DEMO_MODE or a logged live failure, with provenance always reported.
"""

from __future__ import annotations

import asyncio
import os
import time

import pytest

from backend.demo import golden_path as gp


@pytest.fixture(autouse=True)
def _clear_demo_mode():
    """Ensure DEMO_MODE is off unless a test sets it."""
    saved = os.environ.pop("DEMO_MODE", None)
    yield
    if saved is not None:
        os.environ["DEMO_MODE"] = saved
    else:
        os.environ.pop("DEMO_MODE", None)


def _run(coro):
    return asyncio.run(coro)


# ── live-first (default) ──

def test_live_first_uses_live_not_cache():
    called = {"n": 0}
    def live():
        called["n"] += 1
        return "LIVE ANSWER"
    served = _run(gp.chat_reply("142/91", live))
    assert served.response == "LIVE ANSWER"
    assert served.source == "live"
    assert called["n"] == 1            # the real model actually ran


def test_live_failure_falls_back_to_cache_labeled():
    def live():
        raise RuntimeError("model timeout")
    served = _run(gp.chat_reply("140/90", live))
    assert served.source == "fallback"        # explicitly labeled, not silent
    assert "Dr. Reyes" in served.response       # the cached scripted reply


def test_live_failure_without_cache_reraises():
    def live():
        raise RuntimeError("model timeout")
    with pytest.raises(RuntimeError):
        _run(gp.chat_reply("unscripted input", live))   # no cache → must propagate


# ── DEMO_MODE (explicit) ──

def test_demo_mode_serves_cache_without_calling_live():
    os.environ["DEMO_MODE"] = "true"
    called = {"n": 0}
    def live():
        called["n"] += 1
        return "LIVE"
    served = _run(gp.chat_reply("142/91", live))
    assert served.source == "demo_mode"
    assert served.response == gp.CHAT_GOLDEN["142/91"]
    assert called["n"] == 0            # live never called in demo mode for scripted turns


def test_demo_mode_miss_goes_live():
    os.environ["DEMO_MODE"] = "on"
    served = _run(gp.chat_reply("some unscripted thing", lambda: "LIVE"))
    assert served.source == "live"     # unknown input is not faked


def test_demo_mode_flag_parsing():
    for val, expected in [("true", True), ("1", True), ("on", True),
                          ("false", False), ("", False), ("0", False)]:
        os.environ["DEMO_MODE"] = val
        assert gp.demo_mode_enabled() is expected


# ── full scripted sequence runs fast, 3x in a row ──

def test_full_demo_sequence_under_90s_three_times():
    os.environ["DEMO_MODE"] = "true"
    def boom():
        raise AssertionError("should not call live in demo mode for scripted steps")
    for _ in range(3):
        start = time.perf_counter()
        for kind, key in gp.DEMO_SEQUENCE:
            served = _run(gp.chat_reply(key, boom)) if kind == "chat" \
                else _run(gp.step_output(key, boom))
            assert served.source == "demo_mode"
            assert served.response
        assert time.perf_counter() - start < 90    # comfortably; it's milliseconds


def test_every_scripted_turn_is_cached():
    # Every chat input + step in the sequence must have a pre-cached answer.
    for kind, key in gp.DEMO_SEQUENCE:
        cache = gp.CHAT_GOLDEN if kind == "chat" else gp.STEP_GOLDEN
        assert key in cache and cache[key]


def test_supports_async_live_call():
    async def live():
        return "ASYNC LIVE"
    served = _run(gp.chat_reply("142/91", live))
    assert served.response == "ASYNC LIVE" and served.source == "live"
