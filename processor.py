"""Core processing: build prompts, call the LLM per message, collect results."""

import json
import re
from typing import Any, Dict, List, Optional

from llm_client import LLMError, call_llm, llm_available
from utils import (
    get_logger,
    normalize_action,
    normalize_confidence,
    normalize_id_list,
)

LOGGER = get_logger("wa_router.processor")

# The exact routing prompt required by the specification.
ROUTER_PROMPT = """You are an AI Message Notification Router.

Analyze the input and return JSON with:
- action: notify, digest, or mute
- message_type
- reason
- confidence (0 to 1)
- evidence_message_ids

Rules:
- notify -> urgent, important, trusted
- digest -> useful but not urgent
- mute -> spam, scam, repetitive

Consider:
- user behavior
- sender trust
- message history
- forwarded count
- suspicious links
- urgency language

Return ONLY valid JSON."""

OUTPUT_COLUMNS = [
    "message_id",
    "action",
    "message_type",
    "reason",
    "confidence",
    "evidence_message_ids",
]

URGENCY_WORDS = (
    "urgent", "asap", "immediately", "emergency", "hospital", "accident",
    "deadline", "today", "now", "important", "critical", "call me",
)
SPAM_WORDS = (
    "congratulations", "you won", "lottery", "click here", "free gift",
    "verify your account", "otp", "crypto", "investment opportunity",
    "limited offer", "claim now", "prize", "kyc",
)
LINK_RE = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
SUSPICIOUS_TLDS = (".xyz", ".top", ".click", ".tk", ".ru", "bit.ly", "tinyurl")


# ---------------------------------------------------------------------------
# Input helpers
# ---------------------------------------------------------------------------


def extract_messages(payload: Any) -> List[Dict[str, Any]]:
    """Accept several plausible input shapes and return the list of messages."""
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ("messages", "data", "items", "inbox"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
        if "message_id" in payload:
            return [payload]
    raise ValueError(
        "Input JSON must be a list of messages or an object with a 'messages' list."
    )


def build_prompt(message: Dict[str, Any], user_profile: Optional[Dict[str, Any]] = None) -> str:
    """Combine the fixed router prompt with the message payload as JSON context."""
    context: Dict[str, Any] = dict(message)
    if user_profile and "user_profile" not in context:
        context["user_profile"] = user_profile
    payload = json.dumps(context, ensure_ascii=False, indent=2, default=str)
    return f"{ROUTER_PROMPT}\n\nINPUT:\n{payload}"


def _message_text(message: Dict[str, Any]) -> str:
    content = message.get("content") or message.get("message") or {}
    if isinstance(content, dict):
        parts = [
            content.get("text"),
            content.get("caption"),
            content.get("transcript"),
            content.get("filename"),
        ]
        return " ".join(str(part) for part in parts if part)
    return str(content or message.get("text") or "")


def _message_type(message: Dict[str, Any]) -> str:
    content = message.get("content") or {}
    if isinstance(content, dict) and content.get("type"):
        return str(content["type"])
    return str(message.get("message_type") or message.get("type") or "text")


# ---------------------------------------------------------------------------
# Offline heuristic fallback
# ---------------------------------------------------------------------------


def heuristic_decision(message: Dict[str, Any]) -> Dict[str, Any]:
    """Rule-based classifier used when the LLM is unavailable or fails.

    Keeps the pipeline runnable end-to-end without API credentials and mirrors
    the same decision schema the LLM is asked to produce.
    """
    text = _message_text(message).lower()
    sender = message.get("sender") or {}
    trust = str(sender.get("trust_level") or sender.get("trust") or "").lower()
    is_contact = bool(sender.get("is_contact", sender.get("in_contacts", False)))
    forwarded = int(message.get("forwarded_count") or sender.get("forwarded_count") or 0)
    history = message.get("history") or []
    evidence = [
        str(item.get("message_id"))
        for item in history
        if isinstance(item, dict) and item.get("message_id")
    ][:5]

    links = LINK_RE.findall(text)
    suspicious_link = any(tld in link.lower() for link in links for tld in SUSPICIOUS_TLDS)
    spam_hits = [word for word in SPAM_WORDS if word in text]
    urgent_hits = [word for word in URGENCY_WORDS if word in text]

    if spam_hits or suspicious_link or forwarded >= 5 or trust in ("spam", "blocked", "untrusted"):
        reasons = []
        if spam_hits:
            reasons.append(f"spam/scam wording ({', '.join(spam_hits[:3])})")
        if suspicious_link:
            reasons.append("suspicious link")
        if forwarded >= 5:
            reasons.append(f"forwarded {forwarded} times")
        if trust in ("spam", "blocked", "untrusted"):
            reasons.append(f"sender trust '{trust}'")
        return {
            "action": "mute",
            "message_type": _message_type(message),
            "reason": "Muted: " + "; ".join(reasons) + ".",
            "confidence": 0.85,
            "evidence_message_ids": evidence,
        }

    if urgent_hits and (is_contact or trust in ("high", "trusted", "verified")):
        return {
            "action": "notify",
            "message_type": _message_type(message),
            "reason": (
                f"Urgency language ({', '.join(urgent_hits[:3])}) from a trusted sender."
            ),
            "confidence": 0.8,
            "evidence_message_ids": evidence,
        }

    if urgent_hits:
        return {
            "action": "notify",
            "message_type": _message_type(message),
            "reason": f"Urgency language detected ({', '.join(urgent_hits[:3])}).",
            "confidence": 0.6,
            "evidence_message_ids": evidence,
        }

    return {
        "action": "digest",
        "message_type": _message_type(message),
        "reason": "Useful but not urgent; batched into the periodic digest.",
        "confidence": 0.65,
        "evidence_message_ids": evidence,
    }


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------


def process_message(
    message: Dict[str, Any],
    user_profile: Optional[Dict[str, Any]] = None,
    use_llm: bool = True,
) -> Dict[str, Any]:
    """Classify a single message and return one output row."""
    message_id = str(message.get("message_id") or message.get("id") or "unknown")

    decision: Optional[Dict[str, Any]] = None
    if use_llm and llm_available():
        try:
            decision = call_llm(build_prompt(message, user_profile))
        except LLMError as exc:
            LOGGER.error("LLM failed for %s, using heuristic fallback: %s", message_id, exc)

    if decision is None:
        decision = heuristic_decision(message)

    return {
        "message_id": message_id,
        "action": normalize_action(decision.get("action")),
        "message_type": str(decision.get("message_type") or _message_type(message)),
        "reason": str(decision.get("reason") or ""),
        "confidence": normalize_confidence(decision.get("confidence")),
        "evidence_message_ids": ",".join(normalize_id_list(decision.get("evidence_message_ids"))),
    }


def process_messages(payload: Any, use_llm: bool = True) -> List[Dict[str, Any]]:
    """Process every message in the input payload and return output rows."""
    messages = extract_messages(payload)
    user_profile = payload.get("user_profile") if isinstance(payload, dict) else None

    if use_llm and not llm_available():
        LOGGER.warning(
            "No API key found (OPENAI_API_KEY / GROQ_API_KEY / ANTHROPIC_API_KEY); "
            "using the built-in heuristic classifier."
        )

    rows: List[Dict[str, Any]] = []
    for index, message in enumerate(messages, start=1):
        LOGGER.info("Processing message %s/%s", index, len(messages))
        rows.append(process_message(message, user_profile, use_llm=use_llm))
    return rows
