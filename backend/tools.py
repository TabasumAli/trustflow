import csv
import json
import re
import io
from pathlib import Path

from pypdf import PdfReader

from backend.config import (
    VENDORS_CSV,
    RULES_JSON,
)

_CURRENT_ORG_ID = None


def set_org_id(org_id: str) -> None:
    global _CURRENT_ORG_ID
    _CURRENT_ORG_ID = org_id

    
def read_pdf(file_bytes: bytes) -> str:
    reader = PdfReader(io.BytesIO(file_bytes))
    pages = [page.extract_text() or "" for page in reader.pages]
    return "\n".join(pages).strip()


def read_txt(file_bytes: bytes) -> str:
    return file_bytes.decode("utf-8", errors="ignore").strip()


def read_invoice(file_bytes: bytes, filename: str) -> str:
    ext = Path(filename).suffix.lower()
    if ext == ".pdf":
        return read_pdf(file_bytes)
    if ext == ".txt":
        return read_txt(file_bytes)
    raise ValueError(f"Unsupported file type: {ext}")


def load_vendors(org_id: str = None) -> list[dict]:
    from backend import db

    return db.get_vendors(org_id or _CURRENT_ORG_ID)


def load_rules(org_id: str = None) -> list[dict]:
    from backend import db

    return db.get_rules(org_id or _CURRENT_ORG_ID)


def find_vendor(vendor_name: str, vendors: list[dict]) -> dict | None:
    if not vendor_name:
        return None
    target = vendor_name.strip().lower()
    for v in vendors:
        if v["vendor_name"].strip().lower() == target:
            return v
    return None


def _is_missing(value) -> bool:
    return value is None or (isinstance(value, str) and value.strip() == "")


def check_rule(rule: dict, invoice: dict, vendors: list[dict]) -> dict:
    rule_id = rule["id"]
    field = rule["field"]
    check = rule["check"]
    expected = rule.get("value")
    value = invoice.get(field)

    status = "pass"
    reason = ""

    if check == "exists":
        if _is_missing(value):
            status = "fail"
            reason = f"{field} is missing"

    elif check == "in_list":
        if field == "vendor":
            vendor = find_vendor(value, vendors) if not _is_missing(value) else None
            if vendor is None:
                status = "fail"
                reason = f"Vendor '{value}' not found in vendor list"
            elif vendor.get("status") != "approved":
                status = "fail"
                reason = (
                    f"Vendor '{value}' status is '{vendor.get('status')}', not approved"
                )

    elif check == "lte":
        if _is_missing(value):
            status = "fail"
            reason = f"{field} is missing"
        else:
            try:
                if float(value) > float(expected):
                    status = "fail"
                    reason = f"{field} {value} exceeds limit {expected}"
            except (TypeError, ValueError):
                status = "fail"
                reason = f"{field} is not numeric: {value}"

    elif check == "gte":
        if _is_missing(value):
            status = "fail"
            reason = f"{field} is missing"
        else:
            try:
                if float(value) < float(expected):
                    status = "fail"
                    reason = f"{field} {value} is below minimum {expected}"
            except (TypeError, ValueError):
                status = "fail"
                reason = f"{field} is not numeric: {value}"

    elif check == "matches":
        if _is_missing(value):
            status = "fail"
            reason = f"{field} is missing"
        elif rule_id == "tax_id_matches_vendor":
            vendor = find_vendor(invoice.get("vendor"), vendors)
            if vendor is None:
                status = "fail"
                reason = "Cannot verify tax_id: vendor not found"
            elif vendor.get("tax_id") != value:
                status = "fail"
                reason = f"tax_id '{value}' does not match vendor record '{vendor.get('tax_id')}'"
        elif expected:
            if not re.match(expected, str(value)):
                status = "fail"
                reason = f"{field} '{value}' does not match pattern {expected}"

    elif check == "not_in_list":
        if not _is_missing(value) and value in (expected or []):
            status = "fail"
            reason = f"{field} '{value}' is in the blocked list"

    return {
        "rule": rule_id,
        "description": rule["description"],
        "status": status,
        "reason": reason,
        "weight": rule.get("weight", 0),
        "severity": rule.get("severity", "low"),
    }


def check_all_rules(invoice: dict, vendors: list[dict]) -> list[dict]:
    return [check_rule(r, invoice, vendors) for r in load_rules()]


def score_risk(checks: list[dict]) -> int:
    total_weight = sum(c.get("weight", 0) for c in checks)
    if total_weight == 0:
        return 0
    failed_weight = sum(c.get("weight", 0) for c in checks if c["status"] == "fail")
    score = round((failed_weight / total_weight) * 100)
    return max(0, min(100, score))


def save_vendors_from_csv(org_id: str, csv_bytes: bytes) -> int:
    from backend import db

    content = csv_bytes.decode("utf-8")
    reader = csv.DictReader(io.StringIO(content))
    rows = list(reader)
    return db.upsert_vendors(org_id, rows)


def save_rules_from_json(org_id: str, json_bytes: bytes) -> int:
    from backend import db

    content = json_bytes.decode("utf-8")
    parsed = json.loads(content)
    rules_list = parsed.get("rules", parsed) if isinstance(parsed, dict) else parsed
    return db.upsert_rules(org_id, rules_list)
