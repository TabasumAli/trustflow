from typing import Any, Dict, List

from backend import db


def log_event(org_id: str, event: str, data: Dict[str, Any]) -> None:
    try:
        client = db.get_client()
        client.table("audit_logs").insert({
            "org_id": org_id,
            "event": event,
            "data": data,
        }).execute()
    except Exception as e:
        print(f"Warning: failed to log event: {e}")


def read_log(org_id: str, limit: int = 100) -> List[Dict[str, Any]]:
    return db.list_audits(org_id, limit=limit)


def clear_log(org_id: str) -> bool:
    try:
        client = db.get_client()
        client.table("audit_logs").delete().eq("org_id", org_id).execute()
        return True
    except Exception:
        return False