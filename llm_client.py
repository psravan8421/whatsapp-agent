"""LLM client: OpenAI (preferred), Groq, or Anthropic Claude, with retries + JSON validation.

Exposes the required entry point:

    def call_llm(prompt: str) -> dict
"""

import json
import os
import time
from typing import Any, Dict, Optional

import requests

from utils import (
    extract_json,
    get_logger,
    normalize_action,
    normalize_confidence,
    normalize_id_list,
)

LOGGER = get_logger("wa_router.llm")

# Tunables (overridable through environment variables).
TEMPERATURE = 0.3
MAX_ATTEMPTS = int(os.getenv("LLM_MAX_ATTEMPTS", "3"))
RETRY_BACKOFF_SECONDS = float(os.getenv("LLM_RETRY_BACKOFF", "2"))
REQUEST_TIMEOUT = float(os.getenv("LLM_TIMEOUT", "60"))

OPENAI_URL = "https://api.openai.com/v1/chat/completions"
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# Groq exposes an OpenAI-compatible chat completions API.
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-latest")
ANTHROPIC_VERSION = "2023-06-01"

REQUIRED_KEYS = (
    "action",
    "message_type",
    "reason",
    "confidence",
    "evidence_message_ids",
)


class LLMError(RuntimeError):
    """Raised when the LLM cannot be reached or returns unusable output."""


# ---------------------------------------------------------------------------
# Provider selection
# ---------------------------------------------------------------------------


def _provider() -> Optional[str]:
    """Pick a provider based on the available API keys."""
    forced = os.getenv("LLM_PROVIDER", "").strip().lower()
    if forced in ("openai", "groq", "anthropic"):
        return forced
    if os.getenv("OPENAI_API_KEY"):
        return "openai"
    if os.getenv("GROQ_API_KEY"):
        return "groq"
    if os.getenv("ANTHROPIC_API_KEY"):
        return "anthropic"
    return None


def llm_available() -> bool:
    """True when an API key is configured, so the caller can fall back offline."""
    return _provider() is not None


# ---------------------------------------------------------------------------
# Raw provider calls
# ---------------------------------------------------------------------------


def _call_openai_compatible(prompt: str, url: str, api_key: str, model: str, provider: str) -> str:
    """Chat-completions call shared by OpenAI and Groq (same request schema)."""
    payload = {
        "model": model,
        "temperature": TEMPERATURE,
        # Ask the API itself to guarantee a JSON object back.
        "response_format": {"type": "json_object"},
        "messages": [
            {
                "role": "system",
                "content": "You are a strict JSON API. Return ONLY a valid JSON object.",
            },
            {"role": "user", "content": prompt},
        ],
    }
    response = requests.post(
        url,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=REQUEST_TIMEOUT,
    )
    if response.status_code >= 400:
        raise LLMError(f"{provider} HTTP {response.status_code}: {response.text[:400]}")
    data = response.json()
    return data["choices"][0]["message"]["content"]


def _call_openai(prompt: str) -> str:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise LLMError("OPENAI_API_KEY is not set")
    return _call_openai_compatible(prompt, OPENAI_URL, api_key, OPENAI_MODEL, "OpenAI")


def _call_groq(prompt: str) -> str:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise LLMError("GROQ_API_KEY is not set")
    return _call_openai_compatible(prompt, GROQ_URL, api_key, GROQ_MODEL, "Groq")


def _call_anthropic(prompt: str) -> str:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise LLMError("ANTHROPIC_API_KEY is not set")

    payload = {
        "model": ANTHROPIC_MODEL,
        "temperature": TEMPERATURE,
        "max_tokens": 1024,
        "system": "You are a strict JSON API. Return ONLY a valid JSON object.",
        "messages": [{"role": "user", "content": prompt}],
    }
    response = requests.post(
        ANTHROPIC_URL,
        headers={
            "x-api-key": api_key,
            "anthropic-version": ANTHROPIC_VERSION,
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=REQUEST_TIMEOUT,
    )
    if response.status_code >= 400:
        raise LLMError(f"Anthropic HTTP {response.status_code}: {response.text[:400]}")
    data = response.json()
    return "".join(block.get("text", "") for block in data.get("content", []))


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def validate_decision(data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate and normalise an LLM decision payload.

    Raises LLMError when the payload is missing every required field, so the
    retry loop can ask the model again.
    """
    if not isinstance(data, dict):
        raise LLMError("LLM response is not a JSON object")

    missing = [key for key in REQUIRED_KEYS if key not in data]
    if len(missing) == len(REQUIRED_KEYS):
        raise LLMError("LLM response contains none of the required fields")
    if "action" not in data:
        raise LLMError(f"LLM response missing required fields: {missing}")

    return {
        "action": normalize_action(data.get("action")),
        "message_type": str(data.get("message_type") or "unknown").strip(),
        "reason": str(data.get("reason") or "").strip(),
        "confidence": normalize_confidence(data.get("confidence")),
        "evidence_message_ids": normalize_id_list(data.get("evidence_message_ids")),
    }


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def call_llm(prompt: str) -> dict:
    """Send `prompt` to the configured LLM and return a validated decision dict.

    Retries up to MAX_ATTEMPTS times (network errors, HTTP errors, unparseable
    or invalid JSON) with linear backoff. Raises LLMError when all attempts fail.
    """
    provider = _provider()
    if provider is None:
        raise LLMError(
            "No LLM API key configured. Set OPENAI_API_KEY, GROQ_API_KEY "
            "or ANTHROPIC_API_KEY."
        )

    providers = {
        "openai": _call_openai,
        "groq": _call_groq,
        "anthropic": _call_anthropic,
    }

    last_error: Optional[Exception] = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            LOGGER.debug("LLM call attempt %s/%s via %s", attempt, MAX_ATTEMPTS, provider)
            raw = providers[provider](prompt)

            parsed = extract_json(raw)
            if parsed is None:
                raise LLMError(f"Could not parse JSON from LLM output: {raw[:300]!r}")

            return validate_decision(parsed)

        except (requests.RequestException, LLMError, KeyError, ValueError, json.JSONDecodeError) as exc:
            last_error = exc
            LOGGER.warning("LLM attempt %s/%s failed: %s", attempt, MAX_ATTEMPTS, exc)
            if attempt < MAX_ATTEMPTS:
                time.sleep(RETRY_BACKOFF_SECONDS * attempt)

    raise LLMError(f"LLM call failed after {MAX_ATTEMPTS} attempts: {last_error}")
