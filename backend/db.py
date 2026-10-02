import json
from typing import Any, Dict, List, Optional

from supabase import create_client, Client

from backend import config

_client_instance: Optional[Client] = None


def get_client() -> Client:
    global _client_instance
    if _client_instance is None:
        url = config.SUPABASE_URL
        key = config.SUPABASE_KEY
        if not url or not key:
            raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set in .env")
        try:
            _client_instance = create_client(url, key)
        except Exception as e:
            raise ValueError(f"Failed to init Supabase client: {e}")
    return _client_instance


def get_vendors(org_id: str) -> List[Dict[str, Any]]:
    try:
        client = get_client()
        response = client.table("vendors").select("*").eq("org_id", org_id).execute()
        rows = response.data or []
        return [
            {
                "vendor_name": r.get("vendor_name", ""),
                "tax_id": r.get("tax_id", ""),
                "status": r.get("status", "pending"),
                "country": r.get("country", ""),
                "category": r.get("category", ""),
            }
            for r in rows
        ]
    except Exception as e:
        raise ValueError(f"Error fetching vendors: {e}")


def upsert_vendors(org_id: str, rows: List[Dict[str, Any]]) -> int:
    if not rows:
        return 0
    try:
        client = get_client()

        seen = set()
        deduped = []
        for r in rows:
            key = r.get("vendor_name")
            if key and key not in seen:
                seen.add(key)
                deduped.append(r)

        payload = [
            {
                "org_id": org_id,
                "vendor_name": r.get("vendor_name"),
                "tax_id": r.get("tax_id"),
                "status": r.get("status", "pending"),
                "country": r.get("country"),
                "category": r.get("category"),
            }
            for r in deduped
        ]
        response = (
            client.table("vendors")
            .upsert(payload, on_conflict="org_id,vendor_name")
            .execute()
        )
        return len(response.data or [])
    except Exception as e:
        raise ValueError(f"Error upserting vendors: {e}")


def get_rules(org_id: str) -> List[Dict[str, Any]]:
    try:
        client = get_client()
        response = (
            client.table("rules")
            .select("*")
            .eq("org_id", org_id)
            .eq("enabled", True)
            .execute()
        )
        rows = response.data or []
        rules_list = []
        for r in rows:
            val = r.get("value")
            if isinstance(val, str):
                try:
                    val = json.loads(val)
                except Exception:
                    pass
            rules_list.append(
                {
                    "id": r.get("rule_id"),
                    "description": r.get("description", ""),
                    "field": r.get("field", ""),
                    "check": r.get("check_type", ""),
                    "value": val,
                    "weight": r.get("weight", 10),
                    "severity": r.get("severity", "medium"),
                }
            )
        return rules_list
    except Exception as e:
        raise ValueError(f"Error fetching rules: {e}")


def upsert_rules(org_id: str, rows: List[Dict[str, Any]]) -> int:
    if not rows:
        return 0
    try:
        client = get_client()

        seen = set()
        deduped = []
        for r in rows:
            key = r.get("id")
            if key and key not in seen:
                seen.add(key)
                deduped.append(r)

        payload = [
            {
                "org_id": org_id,
                "rule_id": r.get("id"),
                "description": r.get("description"),
                "field": r.get("field"),
                "check_type": r.get("check"),
                "value": r.get("value"),
                "weight": r.get("weight", 10),
                "severity": r.get("severity", "medium"),
                "enabled": True,
            }
            for r in deduped
        ]
        response = (
            client.table("rules")
            .upsert(payload, on_conflict="org_id,rule_id")
            .execute()
        )
        return len(response.data or [])
    except Exception as e:
        raise ValueError(f"Error upserting rules: {e}")


def save_invoice(
    org_id: str, filename: str, file_url: Optional[str], raw_text: str
) -> str:
    try:
        client = get_client()
        data = {
            "org_id": org_id,
            "filename": filename,
            "file_url": file_url,
            "raw_text": raw_text,
        }
        response = client.table("invoices").insert(data).execute()
        if not response.data:
            raise ValueError("No record returned after saving invoice")
        return response.data[0]["id"]
    except Exception as e:
        raise ValueError(f"Error saving invoice: {e}")


def save_audit(invoice_id: str, org_id: str, result: Dict[str, Any]) -> str:
    try:
        client = get_client()
        gate = result.get("gate", {}) or {}
        data = {
            "invoice_id": invoice_id,
            "org_id": org_id,
            "risk_score": int(result.get("risk_score", 0)),
            "verdict": result.get("verdict", "REVIEW"),
            "confidence": float(gate.get("confidence", 1.0)),
            "routing_reason": result.get("routing_reason", ""),
            "summary": result.get("summary", ""),
            "next_action": result.get("next_action", ""),
            "gate_passed": bool(gate.get("passed", False)),
            "gate_warnings": gate.get("warnings", []),
        }
        response = client.table("audits").insert(data).execute()
        if not response.data:
            raise ValueError("No record returned after saving audit")
        return response.data[0]["id"]
    except Exception as e:
        raise ValueError(f"Error saving audit: {e}")


def save_audit_checks(audit_id: str, checks: List[Dict[str, Any]]) -> int:
    if not checks:
        return 0
    try:
        client = get_client()
        payload = [
            {
                "audit_id": audit_id,
                "rule_id": c.get("rule_id", c.get("rule", "unknown")),
                "status": c.get("status", "fail"),
                "reason": c.get("reason", ""),
                "weight": c.get("weight", 0),
                "severity": c.get("severity", "medium"),
            }
            for c in checks
        ]
        response = client.table("audit_checks").insert(payload).execute()
        return len(response.data or [])
    except Exception as e:
        raise ValueError(f"Error saving audit checks: {e}")


def list_audits(org_id: str, limit: int = 50) -> List[Dict[str, Any]]:
    try:
        client = get_client()
        response = (
            client.table("audits")
            .select("*, invoices(filename, raw_text), audit_checks(*)")
            .eq("org_id", org_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return response.data or []
    except Exception as e:
        raise ValueError(f"Error listing audits: {e}")