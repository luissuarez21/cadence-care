"""
Cadence — Arize tracing + LLM-as-judge safety eval (CAD-36)

The trust layer. Two responsibilities:

1. De-identified tracing helpers the orchestrator wraps around every agent call and
   tool dispatch, so each decision shows up as an Arize span — with PHI stripped.
2. A post-escalation LLM-as-judge: after an escalation, an independent Claude call
   judges "was this escalation appropriate given the readings and the care plan?"
   The score is logged to Arize for the demo's safety beat.

Design
------
- PURE CORE, INJECTABLE EDGES: de-identification, prompt building, and response
  parsing are pure and unit-tested offline. The Claude call and the Arize exporter
  are injected (or auto-wired), so the pure logic needs no network/API key to test.
- NO SILENT FALLBACKS: production paths fail loudly. `setup_tracing()` RAISES if the
  Arize key/SDK is missing — it never silently returns a no-op tracer. A no-op is only
  available as an EXPLICIT opt-out (`setup_tracing(required=False)`) or by injecting a
  fake `complete`/`tracer` in tests. The trust layer must actually be live, not a stub.
- DE-IDENTIFIED: span attributes never carry a raw patient_id or symptom text — only
  a hashed patient_token and structured fields (severity, tool, appropriate, ...).

The orchestrator owns its own file; it imports `setup_tracing()` + `agent_span()`
from here to instrument its calls (see the CAD-36 wiring story for Adit).
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
from contextlib import contextmanager
from pathlib import Path
from typing import Awaitable, Callable, Optional

from pydantic import BaseModel

from ..ingestion.schema import EscalationSummary, ProtocolJSON, SymptomLog

MODEL = "claude-sonnet-4-6"
_PROMPT_PATH = Path(__file__).resolve().parents[1] / "agent" / "prompts" / "lmj_eval.txt"

# Span attribute keys that may carry raw PHI / free text — never send these to Arize.
_PHI_KEYS = {
    "patient_id", "raw_text", "notes", "symptom", "symptom_text", "message",
    "text", "summary", "patient_name",
}


# ─────────────────────────────────────────────────────────────────────────────
# De-identification (pure)
# ─────────────────────────────────────────────────────────────────────────────

def patient_token(patient_id: str) -> str:
    """Stable, non-reversible token for a patient_id. Never log the raw id to Arize."""
    digest = hashlib.sha256(patient_id.encode("utf-8")).hexdigest()[:12]
    return f"pt_{digest}"


def de_identify(attributes: dict) -> dict:
    """
    Strip PHI from span attributes: hash patient_id → patient_token and drop any
    free-text/PHI-bearing keys. Returns a new dict safe to send to Arize.
    """
    safe: dict = {}
    for key, value in attributes.items():
        if key == "patient_id":
            safe["patient_token"] = patient_token(str(value))
            continue
        if key in _PHI_KEYS:
            continue
        safe[key] = value
    return safe


# ─────────────────────────────────────────────────────────────────────────────
# Tracing (graceful — no-ops without the SDK / config)
# ─────────────────────────────────────────────────────────────────────────────

def setup_tracing(project_name: str = "cadence", required: bool = True) -> Optional[object]:
    """
    Initialize the Arize tracer. STRICT BY DEFAULT — raises if the API key/SDK is
    missing so production never silently runs without tracing. Pass `required=False`
    only as an explicit opt-out (returns None) when you knowingly want tracing off.

    Requires ARIZE_API_KEY + ARIZE_SPACE_ID in the environment and the `arize-otel`
    package installed.
    """
    if not (os.getenv("ARIZE_API_KEY") and os.getenv("ARIZE_SPACE_ID")):
        if required:
            raise RuntimeError(
                "Arize tracing is required but ARIZE_API_KEY / ARIZE_SPACE_ID are not set. "
                "Set them in .env, or call setup_tracing(required=False) to explicitly disable."
            )
        return None
    try:
        from arize.otel import register
    except ImportError as exc:  # loud — do not degrade to a no-op
        if required:
            raise RuntimeError(
                "Arize tracing is required but the 'arize-otel' package is not installed. "
                "Run: pip install arize-otel"
            ) from exc
        return None

    tracer_provider = register(  # pragma: no cover - needs live SDK + key
        space_id=os.environ["ARIZE_SPACE_ID"],
        api_key=os.environ["ARIZE_API_KEY"],
        project_name=project_name,
    )

    # Auto-instrument the Anthropic SDK: every Claude call (safety.classify,
    # orchestrator.turn, llm_as_judge) becomes a real LLM span with the full
    # prompt, completion, model, and token counts — the rich traces the judges
    # want to see, not just our thin custom attribute spans. Best-effort: if the
    # instrumentor isn't installed, we still get the manual spans.
    try:  # pragma: no cover - needs live SDK
        from openinference.instrumentation.anthropic import AnthropicInstrumentor

        AnthropicInstrumentor().instrument(tracer_provider=tracer_provider)
    except Exception:
        pass

    return tracer_provider.get_tracer(__name__)


@contextmanager
def agent_span(name: str, tracer: Optional[object] = None, **attributes):
    """
    Context manager the orchestrator wraps around an agent call / tool dispatch.
    De-identifies attributes before they hit Arize. No-ops cleanly without a tracer.
    """
    safe = de_identify(attributes)
    if tracer is None:
        yield None
        return
    with tracer.start_as_current_span(name) as span:  # pragma: no cover - needs SDK
        for k, v in safe.items():
            span.set_attribute(k, v)
        yield span


# ─────────────────────────────────────────────────────────────────────────────
# LLM-as-judge (pure prompt build + parse; injectable model call)
# ─────────────────────────────────────────────────────────────────────────────

class JudgeResult(BaseModel):
    """Independent safety verdict on one escalation."""
    appropriate: bool
    confidence: float
    rationale: str
    patient_token: str


def _render_red_flags(plan: ProtocolJSON) -> str:
    return "\n".join(f"- {rf.description} ({rf.severity})" for rf in plan.red_flags) or "- (none)"


def _render_recent_readings(symptoms: list[SymptomLog], limit: int = 6) -> str:
    """Compact, numbers-only view of the latest readings — no names, no raw text."""
    rows: list[str] = []
    for s in sorted(symptoms, key=lambda x: x.timestamp)[-limit:]:
        parts = [s.timestamp.date().isoformat()]
        if s.bp_systolic is not None and s.bp_diastolic is not None:
            parts.append(f"BP {s.bp_systolic}/{s.bp_diastolic}")
        if s.headache_severity is not None:
            parts.append(f"headache {s.headache_severity}/10")
        if s.swelling_location:
            parts.append(f"swelling {s.swelling_location}")
        if s.vision_changes:
            parts.append("vision changes")
        if s.fetal_movement:
            parts.append(f"movement {s.fetal_movement}")
        rows.append("- " + ", ".join(parts))
    return "\n".join(rows) or "- (no readings)"


def build_judge_prompt(
    escalation: EscalationSummary,
    symptoms: list[SymptomLog],
    plan: ProtocolJSON,
) -> str:
    """Fill the LLM-as-judge template. De-identified — numbers and thresholds only."""
    raw = _PROMPT_PATH.read_text()
    tokens = {
        "red_flags": _render_red_flags(plan),
        "severity": escalation.severity,
        "escalation_summary": escalation.summary,
        "triggering_readings": ", ".join(escalation.triggering_readings) or "(none cited)",
        "recent_readings": _render_recent_readings(symptoms),
    }
    for key, value in tokens.items():
        raw = raw.replace("{{" + key + "}}", value)
    return raw


def parse_judge(raw: str) -> tuple[bool, float, str]:
    """
    Parse the judge's reply into (appropriate, confidence, rationale). Prefers JSON;
    falls back to a YES/NO + number heuristic so a chatty model still parses.
    """
    text = raw.strip()
    # Try to find a JSON object anywhere in the reply.
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            obj = json.loads(match.group(0))
            appropriate = bool(obj["appropriate"])
            confidence = float(obj.get("confidence", 0.5))
            rationale = str(obj.get("rationale", "")).strip()
            return appropriate, max(0.0, min(1.0, confidence)), rationale
        except (json.JSONDecodeError, KeyError, ValueError, TypeError):
            pass
    # Fallback: look for YES/NO and a 0-1 number.
    appropriate = bool(re.search(r"\b(yes|appropriate|true)\b", text, re.IGNORECASE)) and not \
        re.search(r"\b(no|inappropriate|false)\b", text, re.IGNORECASE)
    num = re.search(r"\b(0?\.\d+|1\.0|1|0)\b", text)
    confidence = max(0.0, min(1.0, float(num.group(1)))) if num else 0.5
    return appropriate, confidence, text[:300]


# A model-call is `(prompt) -> str`; may be sync or async. Injectable for testing.
Completion = Callable[[str], "str | Awaitable[str]"]


async def _maybe_await(value):
    return await value if asyncio.iscoroutine(value) else value


def _anthropic_complete(prompt: str) -> str:  # pragma: no cover - needs SDK + key
    """Default judge model call via the Anthropic SDK. Used only when no `complete` injected."""
    import anthropic

    client = anthropic.Anthropic()
    resp = client.messages.create(
        model=MODEL,
        max_tokens=400,
        messages=[{"role": "user", "content": prompt}],
    )
    return "".join(block.text for block in resp.content if getattr(block, "type", "") == "text")


async def judge_escalation(
    escalation: EscalationSummary,
    symptoms: list[SymptomLog],
    plan: ProtocolJSON,
    *,
    complete: Optional[Completion] = None,
    tracer: Optional[object] = None,
) -> JudgeResult:
    """
    Independently judge whether `escalation` was appropriate. Builds the prompt,
    calls the (injected or default) model, parses the verdict, and logs a
    de-identified span to Arize. Pure except for the model call + span.
    """
    prompt = build_judge_prompt(escalation, symptoms, plan)
    runner = complete or _anthropic_complete
    raw = await _maybe_await(runner(prompt))
    appropriate, confidence, rationale = parse_judge(raw)

    result = JudgeResult(
        appropriate=appropriate,
        confidence=confidence,
        rationale=rationale,
        patient_token=patient_token(escalation.patient_id),
    )

    with agent_span(
        "llm_as_judge.escalation",
        tracer=tracer,
        patient_id=escalation.patient_id,        # de_identify → patient_token
        severity=escalation.severity,
        escalation_appropriate=result.appropriate,
        judge_confidence=result.confidence,
    ):
        pass

    return result
