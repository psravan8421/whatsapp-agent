"""Small helpers shared across the project: safe JSON parsing and logging."""

import json
import logging
import os
import re
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

_LOG_FORMAT = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"


def get_logger(name: str = "wa_router") -> logging.Logger:
    """Return a configured logger.

    The log level can be controlled with the LOG_LEVEL environment variable
    (default: INFO).
    """
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(_LOG_FORMAT))
        logger.addHandler(handler)
        logger.setLevel(os.getenv("LOG_LEVEL", "INFO").upper())
        logger.propagate = False
    return logger


LOGGER = get_logger()


# ---------------------------------------------------------------------------
# JSON helpers
# ---------------------------------------------------------------------------


def load_json_file(path: str) -> Any:
    """Load a JSON file from disk, raising a clear error when it is invalid."""
    if not os.path.exists(path):
        raise FileNotFoundError(f"Input file not found: {path}")
    with open(path, "r", encoding="utf-8") as handle:
        try:
            return json.load(handle)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Input file {path} is not valid JSON: {exc}") from exc


def extract_json(text: str) -> Optional[Dict[str, Any]]:
    """Best-effort extraction of a JSON object from raw LLM text.

    Handles the common failure modes: markdown code fences, leading/trailing
    prose, and trailing commas. Returns None when nothing parseable is found.
    """
    if not text:
        return None

    candidate = text.strip()

    # Strip markdown code fences such as ```json ... ```
    fenced = re.search(r"```(?:json)?\s*(.*?)```", candidate, re.DOTALL | re.IGNORECASE)
    if fenced:
        candidate = fenced.group(1).strip()

    parsed = _try_loads(candidate)
    if parsed is not None:
        return parsed

    # Fall back to the outermost {...} block in the text.
    start = candidate.find("{")
    end = candidate.rfind("}")
    if start != -1 and end != -1 and end > start:
        block = candidate[start : end + 1]
        parsed = _try_loads(block)
        if parsed is not None:
            return parsed
        # Remove trailing commas, a frequent LLM mistake, and retry once.
        parsed = _try_loads(re.sub(r",\s*([}\]])", r"\1", block))
        if parsed is not None:
            return parsed

    return None


def _try_loads(text: str) -> Optional[Dict[str, Any]]:
    """json.loads that returns None instead of raising, dicts only."""
    try:
        value = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return None
    return value if isinstance(value, dict) else None


# ---------------------------------------------------------------------------
# Normalisation helpers
# ---------------------------------------------------------------------------

VALID_ACTIONS = ("notify", "digest", "mute")


def normalize_action(value: Any) -> str:
    """Coerce an arbitrary LLM value into one of the three allowed actions."""
    action = str(value or "").strip().lower()
    return action if action in VALID_ACTIONS else "digest"


def normalize_confidence(value: Any) -> float:
    """Coerce confidence into a float clamped to [0, 1]."""
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        return 0.0
    return round(min(max(confidence, 0.0), 1.0), 3)


def normalize_id_list(value: Any) -> List[str]:
    """Coerce evidence_message_ids into a list of strings."""
    if value is None:
        return []
    if isinstance(value, str):
        parts = [part.strip() for part in value.split(",")]
        return [part for part in parts if part]
    if isinstance(value, (list, tuple, set)):
        return [str(item).strip() for item in value if str(item).strip()]
    return [str(value)]
