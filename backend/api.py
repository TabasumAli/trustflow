import time

from backend.config import UPLOADS_DIR
from backend.tools import read_invoice
from backend.guardrails import (
    validate_input,
    validate_output,
    parse_agent_json,
    expected_verdict_from_score,
)
from backend.audit import log_event
from backend.gate import evaluate
from backend.crew import build_crew


def run_audit(file_bytes: bytes, filename: str) -> dict:
    log_event("audit_start", {"filename": filename})

    try:
        validate_input(file_bytes, filename)
    except ValueError as e:
        log_event("audit_rejected", {"reason": str(e)})
        return _error_result(str(e))

    upload_path = UPLOADS_DIR / filename
    upload_path.write_bytes(file_bytes)

    try:
        invoice_text = read_invoice(file_bytes, filename)
    except Exception as e:
        log_event("audit_failed", {"stage": "read", "error": str(e)})
        return _error_result(f"Failed to read invoice: {e}")

    log_event("invoice_read", {"chars": len(invoice_text)})

    crew = build_crew()
    last_err = None
    for attempt in range(3):
        try:
            crew.kickoff(inputs={"invoice_text": invoice_text})
            last_err = None
            break
        except Exception as e:
            last_err = e
            msg = str(e)
            if "RateLimitError" in msg or "rate_limit" in msg or "429" in msg:
                wait = 20 * (attempt + 1)
                log_event("rate_limit_retry", {"attempt": attempt + 1, "wait": wait})
                time.sleep(wait)
                continue
            log_event("audit_failed", {"stage": "crew", "error": msg})
            return _error_result(f"Crew execution failed: {e}")

    if last_err is not None:
        log_event("audit_failed", {"stage": "crew", "error": str(last_err)})
        return _error_result(f"Crew execution failed after retries: {last_err}")

    try:
        invoice = _parse_task_output(crew, 1)
        checks = _parse_task_output(crew, 2).get("checks", [])
        routing = _parse_task_output(crew, 3)
        report = _parse_task_output(crew, 4)
    except Exception as e:
        log_event("audit_failed", {"stage": "parse", "error": str(e)})
        return _error_result(f"Failed to parse agent output: {e}")

    risk_score = routing.get("risk_score", 100)
    verdict = routing.get("verdict") or expected_verdict_from_score(risk_score)

    result = {
        "invoice": invoice,
        "checks": checks,
        "risk_score": risk_score,
        "verdict": verdict,
        "routing_reason": routing.get("reason", ""),
        "summary": report.get("summary", ""),
        "next_action": report.get("next_action", ""),
    }

    gate = evaluate(result)
    result["gate"] = gate

    if not gate["passed"] and verdict == "APPROVE":
        result["verdict"] = gate["final_verdict"]

    try:
        validate_output(result)
    except ValueError as e:
        log_event("audit_failed", {"stage": "output", "error": str(e)})
        return _error_result(f"Output validation failed: {e}")

    log_event("audit_complete", {
        "verdict": result["verdict"],
        "risk_score": result["risk_score"],
        "confidence": gate["confidence"],
    })

    return result


def _parse_task_output(crew, task_index: int) -> dict:
    raw = crew.tasks[task_index].output.raw
    return parse_agent_json(raw)


def _error_result(message: str) -> dict:
    return {
        "invoice": {},
        "checks": [],
        "risk_score": 100,
        "verdict": "REJECT",
        "routing_reason": "",
        "summary": "",
        "next_action": "",
        "gate": {"passed": False, "confidence": 0.0, "warnings": [message], "final_verdict": "REJECT"},
        "error": message,
    }