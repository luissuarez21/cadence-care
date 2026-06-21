"""
Cadence — Claude orchestrator loop (CAD-7).

The tool-use loop: message in -> Claude reasons -> dispatches tools -> response out.

Responsibilities (Adit):
  - Render the system prompt from Luis's `prompts/system.txt` (CAD-6 injection
    contract) using the patient's plan + condition pack. Falls back to a short
    placeholder if the file isn't present yet.
  - Expose the 7 frozen tools to Claude as tool schemas (patient_id is NEVER
    exposed to the model — the orchestrator injects it on dispatch so a patient
    can only ever touch their own data).
  - Drive the multi-round tool-use loop and stream the final reply.

Model: claude-sonnet-4-6 (do not hardcode older versions).
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator, Optional

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # pragma: no cover - dotenv optional
    pass

from ..ingestion.schema import ChatMessage, ProtocolJSON, RiskScore, SymptomLog
from ..memory import redis_client
from .tools import TOOL_REGISTRY

MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 1024
MAX_TOOL_ROUNDS = 6

_PROMPTS_DIR = Path(__file__).parent / "prompts"
_PACKS_DIR = Path(__file__).resolve().parents[2] / "packs"


# ─────────────────────────────────────────────────────────────────────────────
# Anthropic client (lazy — only needed when actually talking to Claude)
# ─────────────────────────────────────────────────────────────────────────────

def _client():
    key = os.getenv("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set (see .env / .env.example).")
    import anthropic

    return anthropic.Anthropic(api_key=key)


# ─────────────────────────────────────────────────────────────────────────────
# Condition pack loading (packs/*.json keyed by `condition`)
# ─────────────────────────────────────────────────────────────────────────────

def load_pack_for_condition(condition: Optional[str]) -> Optional[dict]:
    """Find the condition pack whose `condition` field matches. None if absent."""
    if not condition or not _PACKS_DIR.is_dir():
        return None
    for path in _PACKS_DIR.glob("*.json"):
        try:
            pack = json.loads(path.read_text())
        except Exception:
            continue
        if pack.get("condition") == condition:
            return pack
    return None


# ─────────────────────────────────────────────────────────────────────────────
# System prompt rendering (CAD-6 injection contract)
# ─────────────────────────────────────────────────────────────────────────────

_PLACEHOLDER_PROMPT = (
    "You are Cadence — a warm, proactive health companion checking in with a "
    "high-risk pregnant patient between prenatal appointments. Be warm, plain, and "
    "never clinical. You are not a doctor: you collect symptoms, triage against the "
    "care plan, and escalate to the OB — you NEVER diagnose. Use your tools to log "
    "symptoms, assess risk, detect patterns, and escalate when a care-plan threshold "
    "is crossed. When something is flagged, stay calm and tell the patient you've "
    "shared it with her OB and added it to her appointment summary."
)


def _display_name(patient_id: str) -> str:
    """Derive a human name from a synthetic patient_id, e.g. 'maria-chen' -> 'Maria'."""
    first = patient_id.split("-")[0] if patient_id else "there"
    return first.capitalize()


def _strip_directive(raw: str) -> str:
    """Drop the leading `[CADENCE ...]` directive line + the `#` INJECTION CONTRACT block."""
    lines = raw.splitlines()
    i = 0
    while i < len(lines):
        s = lines[i].strip()
        if s == "" or s.startswith("[CADENCE") or s.startswith("#"):
            i += 1
            continue
        break
    return "\n".join(lines[i:]).lstrip("\n")


def _render_red_flags(plan: Optional[ProtocolJSON], pack: Optional[dict]) -> str:
    flags = []
    if plan and plan.red_flags:
        flags = [(f.description, f.escalation_message) for f in plan.red_flags]
    elif pack and pack.get("red_flags"):
        flags = [(f.get("description", ""), f.get("escalation_message", "")) for f in pack["red_flags"]]
    if not flags:
        return "- (no specific red flags on file — escalate anything that worries her)"
    return "\n".join(f"- if {desc} → {msg}" for desc, msg in flags)


def _render_meds(plan: Optional[ProtocolJSON]) -> str:
    if not plan or not plan.medications:
        return "- (none on file)"
    return "\n".join(f"- {m.name} {m.dose}, {m.frequency}".strip() for m in plan.medications)


def _render_daily_questions(pack: Optional[dict]) -> str:
    qs = (pack or {}).get("daily_questions") or []
    if not qs:
        return "- Ask how she's feeling and about anything her OB is tracking."
    return "\n".join(f"- {q.get('prompt', '')}" for q in qs)


def _render_coaching(pack: Optional[dict]) -> str:
    topics = (pack or {}).get("coaching_topics") or []
    return "\n".join(f"- {t}" for t in topics) if topics else "- (none)"


def render_system_prompt(
    plan: Optional[ProtocolJSON],
    pack: Optional[dict],
    patient_name: Optional[str] = None,
) -> str:
    """
    Load `prompts/system.txt` and replace every {{token}} with rendered,
    human-readable text per CAD-6's injection contract. Placeholder if missing.
    """
    path = _PROMPTS_DIR / "system.txt"
    if not path.is_file():
        return _PLACEHOLDER_PROMPT

    raw = _strip_directive(path.read_text())

    condition_human = (pack or {}).get("display_name") or (
        plan.condition if plan else "high-risk pregnancy"
    )
    tokens = {
        "patient_name": patient_name or (plan.patient_id if plan else "there"),
        "gestational_age_weeks": str(plan.gestational_age_weeks) if (plan and plan.gestational_age_weeks is not None) else "unknown",
        "condition": condition_human,
        "patient_context": (plan.patient_context if plan else "") or "(no extra context provided)",
        "tone": (pack or {}).get("patient_tone", "warm, reassuring, plain-language, never clinical"),
        "daily_questions": _render_daily_questions(pack),
        "red_flags": _render_red_flags(plan, pack),
        "medications": _render_meds(plan),
        "coaching_topics": _render_coaching(pack),
    }
    for key, value in tokens.items():
        raw = raw.replace("{{" + key + "}}", value)
    # Any tokens we didn't supply: blank them out so none leak to the model.
    raw = re.sub(r"\{\{[a-z_]+\}\}", "", raw)
    return raw


# ─────────────────────────────────────────────────────────────────────────────
# Tool schemas exposed to Claude (patient_id deliberately NOT exposed)
# ─────────────────────────────────────────────────────────────────────────────

def anthropic_tool_schemas() -> list[dict]:
    return [
        {
            "name": "lookup_plan",
            "description": "Search the patient's own care plan to ground an answer. Use when she asks what her plan says.",
            "input_schema": {
                "type": "object",
                "properties": {"query": {"type": "string", "description": "What to look up in her care plan."}},
                "required": ["query"],
            },
        },
        {
            "name": "log_symptom",
            "description": "Record one structured check-in datapoint she just shared (a BP reading, a symptom, whether she took her meds).",
            "input_schema": {
                "type": "object",
                "properties": {
                    "bp_systolic": {"type": "integer"},
                    "bp_diastolic": {"type": "integer"},
                    "headache_severity": {"type": "integer", "description": "0-10 scale"},
                    "swelling_location": {"type": "string", "description": "e.g. face, hands, feet"},
                    "vision_changes": {"type": "boolean"},
                    "fetal_movement": {"type": "string", "description": "e.g. normal, decreased"},
                    "medication_taken": {"type": "boolean"},
                    "raw_text": {"type": "string", "description": "her original words"},
                    "notes": {"type": "string", "description": "your short structured note"},
                },
            },
        },
        {
            "name": "assess_risk",
            "description": "Evaluate her current readings/symptoms against her care plan's red flags. Returns severity + plain-English rationale. Call after she shares readings.",
            "input_schema": {"type": "object", "properties": {}},
        },
        {
            "name": "detect_pattern",
            "description": "Surface multi-day trends (e.g. BP trending up, recurring headaches) from her history.",
            "input_schema": {"type": "object", "properties": {}},
        },
        {
            "name": "escalate_to_clinician",
            "description": "Send a structured clinical summary to her OB. Call ONLY when assess_risk returns escalate or escalate_urgent.",
            "input_schema": {"type": "object", "properties": {}},
        },
        {
            "name": "generate_visit_summary",
            "description": "Build her pre-appointment brief (patient + clinician variants) from her history.",
            "input_schema": {"type": "object", "properties": {}},
        },
        {
            "name": "schedule_followup",
            "description": "Adjust her next check-in / appointment. Only when her care team directs it.",
            "input_schema": {
                "type": "object",
                "properties": {"when": {"type": "string", "description": "When to follow up, e.g. 'in 2 days'."}},
                "required": ["when"],
            },
        },
    ]


# ─────────────────────────────────────────────────────────────────────────────
# Dispatch — map a Claude tool call onto the frozen TOOL_REGISTRY
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class _DispatchOutcome:
    content: str
    is_error: bool = False
    flagged: bool = False
    risk: Optional[RiskScore] = None


def _to_content(result) -> str:
    """Serialize any tool return (Pydantic model / list / scalar) to a string for Claude."""
    if hasattr(result, "model_dump_json"):
        return result.model_dump_json()
    if isinstance(result, list):
        return json.dumps([r.model_dump() if hasattr(r, "model_dump") else r for r in result], default=str)
    return json.dumps(result, default=str)


def dispatch_tool(name: str, tool_input: dict, patient_id: str) -> _DispatchOutcome:
    """Inject patient_id, call the registered tool, and package the result for Claude."""
    fn = TOOL_REGISTRY.get(name)
    if fn is None:
        return _DispatchOutcome(content=f"Unknown tool: {name}", is_error=True)
    try:
        if name == "log_symptom":
            from datetime import datetime, timezone

            symptom = SymptomLog(patient_id=patient_id, timestamp=datetime.now(timezone.utc), **tool_input)
            result = fn(patient_id, symptom)
        elif name == "lookup_plan":
            result = fn(patient_id, tool_input.get("query", ""))
        elif name == "schedule_followup":
            result = fn(patient_id, tool_input.get("when", ""))
        else:  # assess_risk, detect_pattern, escalate_to_clinician, generate_visit_summary
            result = fn(patient_id)
    except NotImplementedError:
        return _DispatchOutcome(content=f"Tool '{name}' is not implemented yet.", is_error=True)
    except Exception as exc:  # surface the error to the model so the turn can recover
        return _DispatchOutcome(content=f"Tool '{name}' failed: {exc}", is_error=True)

    return _DispatchOutcome(
        content=_to_content(result),
        flagged=(name == "escalate_to_clinician"),
        risk=result if (name == "assess_risk" and isinstance(result, RiskScore)) else None,
    )


# ─────────────────────────────────────────────────────────────────────────────
# The loop
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class AgentResult:
    text: str = ""
    flagged: bool = False
    risk: Optional[RiskScore] = None
    tool_calls: list[str] = field(default_factory=list)


def stream_agent(
    patient_id: str,
    system_prompt: str,
    messages: list[dict],
    result: Optional[AgentResult] = None,
) -> Iterator[str]:
    """
    Run the multi-round tool-use loop, yielding the assistant's text as it streams.

    `messages` is the running Anthropic message list (mutated in place across rounds).
    Pass an AgentResult to capture flagged/risk/text/tool_calls for the JSON endpoint.
    """
    if result is None:
        result = AgentResult()
    client = _client()
    tools = anthropic_tool_schemas()

    for _ in range(MAX_TOOL_ROUNDS):
        with client.messages.stream(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=system_prompt,
            tools=tools,
            messages=messages,
        ) as stream:
            for chunk in stream.text_stream:
                result.text += chunk
                yield chunk
            final = stream.get_final_message()

        messages.append({"role": "assistant", "content": final.content})
        tool_uses = [b for b in final.content if getattr(b, "type", None) == "tool_use"]
        if final.stop_reason != "tool_use" or not tool_uses:
            return

        tool_results = []
        for tu in tool_uses:
            result.tool_calls.append(tu.name)
            outcome = dispatch_tool(tu.name, dict(tu.input or {}), patient_id)
            if outcome.flagged and not outcome.is_error:
                result.flagged = True
            if outcome.risk is not None:
                result.risk = outcome.risk
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tu.id,
                "content": outcome.content,
                "is_error": outcome.is_error,
            })
        messages.append({"role": "user", "content": tool_results})


def _chat_message_to_anthropic(m: ChatMessage) -> dict:
    return {"role": "assistant" if m.sender == "cadence" else "user", "content": m.text}


def respond(
    patient_id: str,
    session_id: Optional[str],
    user_message: str,
) -> AgentResult:
    """
    High-level entry: load the patient's plan + pack + session history from Redis,
    run the agent loop, and return the collected result. Persistence of the new
    turns is the chat route's job (CAD-?), so this stays side-effect-light.
    """
    plan = redis_client.get_plan(patient_id)
    pack = load_pack_for_condition(plan.condition if plan else None)
    history = redis_client.get_session(patient_id, session_id) if session_id else []

    system_prompt = render_system_prompt(plan, pack, _display_name(patient_id))
    messages = [_chat_message_to_anthropic(m) for m in history]
    messages.append({"role": "user", "content": user_message})

    result = AgentResult()
    for _ in stream_agent(patient_id, system_prompt, messages, result):
        pass
    return result
