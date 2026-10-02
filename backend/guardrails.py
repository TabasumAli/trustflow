import json
import re

from backend.config import (
    MAX_FILE_SIZE_MB,
    ALLOWED_EXTENSIONS,
    VERDICT_APPROVE,
    VERDICT_REVIEW,
    VERDICT_REJECT,
    RISK_APPROVE_MAX,
    RISK_REVIEW_MAX,
)

_VALID_VERDICTS = {VERDICT_APPROVE, VERDICT_REVIEW, VERDICT_REJECT}


def validate_input(file_bytes: bytes, filename: str) -> None:
    if not file_bytes:
        raise ValueError("Uploaded file is empty")

    size_mb = len(file_bytes) / (1024 * 1024)
    if size_mb > MAX_FILE_SIZE_MB:
        raise ValueError(f"File is {size_mb:.1f}MB, exceeds {MAX_FILE_SIZE_MB}MB limit")

    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(f"Unsupported file type '{ext}'. Allowed: {ALLOWED_EXTENSIONS}")


def parse_agent_json(raw: str) -> dict:
    if raw is None:
        raise ValueError("Agent returned None")

    text = raw.strip()

    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()

    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError(f"No JSON object found in agent output: {raw[:200]}")

    snippet = text[start : end + 1]

    try:
        return json.loads(snippet)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON from agent: {e}. Snippet: {snippet[:200]}")


def validate_output(result: dict) -> dict:
    if not isinstance(result, dict):
        raise ValueError("Result must be a dict")

    verdict = result.get("verdict")
    if verdict not in _VALID_VERDICTS:
        raise ValueError(f"Invalid verdict '{verdict}'. Must be one of {_VALID_VERDICTS}")

    score = result.get("risk_score")
    if not isinstance(score, int) or score < 0 or score > 100:
        raise ValueError(f"Invalid risk_score '{score}'. Must be int 0-100")

    if "checks" not in result or not isinstance(result["checks"], list):
        raise ValueError("Missing or invalid 'checks' list")

    return result


def mask_pii(text: str) -> str:
    if not text:
        return text
    masked = re.sub(r"\bTX-\d{6}\b", "TX-XXXXXX", text)
    masked = re.sub(r"\b\d{4}[ -]?\d{4}[ -]?\d{4}[ -]?\d{4}\b", "XXXX-XXXX-XXXX-XXXX", masked)
    return masked


def expected_verdict_from_score(score: int) -> str:
    if score <= RISK_APPROVE_MAX:
        return VERDICT_APPROVE
    if score <= RISK_REVIEW_MAX:
        return VERDICT_REVIEW
    return VERDICT_REJECT