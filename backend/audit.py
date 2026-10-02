import json
from datetime import datetime, timezone

from backend.config import AUDIT_LOG


def log_event(event: str, data: dict | None = None) -> None:
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event": event,
        "data": data or {},
    }
    with open(AUDIT_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def read_log() -> list[dict]:
    if not AUDIT_LOG.exists():
        return []
    entries = []
    with open(AUDIT_LOG, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return entries


def clear_log() -> None:
    if AUDIT_LOG.exists():
        AUDIT_LOG.unlink()