"""
Cadence — semantic safety layer (CAD-?? / Adit).

A condition-agnostic guardrail that runs on EVERY free-text patient message,
in parallel to the deterministic care-plan risk engine. It catches the danger
the condition pack will never encode — suicidal ideation, abuse, an acute
emergency outside the plan — and forces an escalation regardless of what
`assess_risk` says.

Why a separate layer (not a tool the agent chooses to call):
  - The condition pack's red_flags only cover preeclampsia. "I want to kms" is
    `ok` to the risk engine — it has no rule for it. This layer is the universal
    floor underneath every condition pack (the platform story).
  - It is NOT a tool the agent may skip — a jailbreak of the main agent can't
    suppress it, because the orchestrator runs it unconditionally.

Design (mirrors eval/arize_judge.py):
  - PURE CORE, INJECTABLE EDGE: prompt build + response parse are pure and
    unit-testable offline; the Claude call is injected (or auto-wired to Haiku).
  - Cheap by construction: Haiku 4.5, no tools, no history, tiny output — about
    a seventh of a cent per message (~5–10% on top of the main Sonnet turn).
  - Every verdict is traced to Arize (de-identified) — including SAFE ones on
    turns that contained risk language — so the LLM-as-judge can audit
    under-escalation (missed crises), not just over-escalation.

Model: claude-haiku-4-5 (fast/cheap classifier; do not hardcode older versions).
"""

from __future__ import annotations

import json
import re
from typing import Awaitable, Callable, Optional

from ..eval.arize_judge import agent_span
from ..ingestion.schema import SafetyVerdict

MODEL = "claude-haiku-4-5"
MAX_TOKENS = 256

# Severities at/above which we route to the clinician. escalate_urgent additionally
# short-circuits the agent (the orchestrator returns CRISIS_RESPONSE instead of
# letting the model freelance during an acute crisis).
_ESCALATING = {"escalate", "escalate_urgent"}


# ─────────────────────────────────────────────────────────────────────────────
# Patient-facing crisis copy — PLACEHOLDER, Luis owns the final wording.
# Surfaced verbatim by the orchestrator on an escalate_urgent verdict instead of
# an LLM-generated reply. Calm, non-judgmental, with a concrete resource. The
# 988 Suicide & Crisis Lifeline is US-specific — Luis to localize / clinically
# validate. Keep it short and warm; never diagnose.
# ─────────────────────────────────────────────────────────────────────────────
CRISIS_RESPONSE = (
    "I'm really glad you told me, and I want to make sure you're supported right now. "
    "I've let your care team know so someone can reach out to you. "
    "If you're thinking about harming yourself or you're in danger, please reach out right "
    "now — call or text 988 (the Suicide & Crisis Lifeline) any time, or call 911 if you're "
    "in immediate danger. You don't have to go through this alone."
)


# ─────────────────────────────────────────────────────────────────────────────
# Pure: prompt build + parse
# ─────────────────────────────────────────────────────────────────────────────

_SYSTEM = (
    "You are a safety classifier for a maternal-health check-in app. You read ONE "
    "message from a pregnant patient and decide whether it signals danger that needs "
    "a human clinician's attention RIGHT AWAY — independent of any pregnancy care "
    "plan. You are NOT a doctor and you do NOT diagnose. You only classify.\n\n"
    "Categories:\n"
    "- none: ordinary check-in content (symptoms, readings, questions, small talk).\n"
    "- self_harm: any sign of suicidal thoughts, wanting to die, or self-injury.\n"
    "- abuse: domestic violence, being hurt by someone, feeling unsafe at home.\n"
    "- medical_emergency: an acute medical emergency NOT covered by routine pregnancy "
    "monitoring (e.g. chest pain, trouble breathing, fainting, severe bleeding, overdose).\n"
    "- acute_distress: severe psychological distress or a mental-health crisis short of "
    "stated self-harm.\n\n"
    "Severity: 'escalate_urgent' for self_harm, abuse, or medical_emergency, or any "
    "imminent danger; 'escalate' for acute_distress that needs prompt follow-up; "
    "'monitor' for mild distress worth noting; 'ok' for none.\n"
    "Err toward caution: if a message plausibly signals self-harm or danger, classify it "
    "as such even if phrased casually, in slang, or as an abbreviation (e.g. 'kms', 'end "
    "it', 'don't want to be here').\n\n"
    'Respond with ONLY a JSON object, no prose:\n'
    '{"category": "<one of the categories>", "severity": "<ok|monitor|escalate|escalate_urgent>", '
    '"confidence": <0.0-1.0>, "rationale": "<one short sentence>"}'
)


def build_prompt(message: str) -> str:
    """The user-turn content for the classifier (system instructions are separate)."""
    return f"Patient message:\n\"\"\"\n{message}\n\"\"\""


def parse_verdict(raw: str) -> SafetyVerdict:
    """
    Parse the classifier reply into a SafetyVerdict. Prefers a JSON object; on any
    failure returns a SAFE verdict (fail-open on PARSING only — never invent a crisis
    from a malformed reply). A genuine crisis still escalates whenever the model
    returns parseable JSON, which is the overwhelmingly common case.
    """
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        return SafetyVerdict()
    try:
        obj = json.loads(match.group(0))
    except (json.JSONDecodeError, ValueError):
        return SafetyVerdict()

    category = obj.get("category", "none")
    if category not in {"none", "self_harm", "abuse", "medical_emergency", "acute_distress"}:
        category = "none"
    severity = obj.get("severity", "ok")
    if severity not in {"ok", "monitor", "escalate", "escalate_urgent"}:
        severity = "ok"
    try:
        confidence = max(0.0, min(1.0, float(obj.get("confidence", 0.0))))
    except (TypeError, ValueError):
        confidence = 0.0

    # Safety invariant: a real category must carry at least 'escalate'. Never let a
    # crisis category slip through as 'ok'/'monitor' due to a model formatting slip.
    if category != "none" and severity in {"ok", "monitor"}:
        severity = "escalate"

    return SafetyVerdict(
        category=category,
        severity=severity,
        confidence=confidence,
        rationale=str(obj.get("rationale", "")).strip(),
    )


def is_escalating(verdict: SafetyVerdict) -> bool:
    return verdict.category != "none" and verdict.severity in _ESCALATING


def is_short_circuit(verdict: SafetyVerdict) -> bool:
    """True when we should bypass the agent entirely and return CRISIS_RESPONSE."""
    return verdict.category != "none" and verdict.severity == "escalate_urgent"


# ─────────────────────────────────────────────────────────────────────────────
# The classifier call (injectable; defaults to a Haiku Anthropic call)
# ─────────────────────────────────────────────────────────────────────────────

Completion = Callable[[str], "str | Awaitable[str]"]


def _anthropic_complete(prompt: str) -> str:  # pragma: no cover - needs SDK + key
    """Default classifier call via the Anthropic SDK (Haiku). Cheap, no tools."""
    import os

    import anthropic

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    resp = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )
    return "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")


def classify(
    message: str,
    *,
    complete: Optional[Completion] = None,
    patient_id: Optional[str] = None,
    tracer: Optional[object] = None,
) -> SafetyVerdict:
    """
    Classify one patient message. Synchronous: the result gates escalation, so it
    must complete before we reply. Traces a de-identified span for EVERY verdict
    (safe ones included) so under-escalation is auditable in Arize.

    On any model/parse error this returns a SAFE verdict — a transient classifier
    failure must never fabricate a crisis. (The deterministic care-plan engine is
    still the safety net for condition-specific red flags.)
    """
    runner = complete or _anthropic_complete
    try:
        raw = runner(build_prompt(message))
        # Tolerate an accidentally-async injected runner in this sync path.
        if hasattr(raw, "__await__"):  # pragma: no cover
            import asyncio

            raw = asyncio.get_event_loop().run_until_complete(raw)
        verdict = parse_verdict(raw)
    except Exception:
        verdict = SafetyVerdict()

    with agent_span(
        "safety.classify",
        tracer=tracer,
        patient_id=patient_id or "unknown",   # de_identify → patient_token
        safety_category=verdict.category,
        severity=verdict.severity,
        confidence=verdict.confidence,
        escalated=is_escalating(verdict),
    ):
        pass

    return verdict
