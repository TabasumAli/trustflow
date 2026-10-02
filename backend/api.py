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
from backend.tracing import init_tracing, trace_audit, log_audit_result, log_audit_error
from backend import db


init_tracing()


def run_audit(
    file_bytes: bytes,
    filename: str,
    org_id: str,
    api_key: str | None = None,
) -> dict:
    log_event(org_id, "audit_start", {"filename": filename})

    with trace_audit(org_id, filename) as run:
        try:
            validate_input(file_bytes, filename)
        except ValueError as e:
            log_event(org_id, "audit_rejected", {"reason": str(e)})
            log_audit_error(run, str(e))
            return _error_result(str(e))

        try:
            invoice_text = read_invoice(file_bytes, filename)
        except Exception as e:
            log_event(org_id, "audit_failed", {"stage": "read", "error": str(e)})
            log_audit_error(run, f"read: {e}")
            return _error_result(f"Failed to read invoice: {e}")

        log_event(org_id, "invoice_read", {"chars": len(invoice_text)})

        try:
            invoice_id = db.save_invoice(
                org_id=org_id,
                filename=filename,
                file_url=None,
                raw_text=invoice_text,
            )
        except Exception as e:
            log_event(org_id, "audit_failed", {"stage": "save_invoice", "error": str(e)})
            log_audit_error(run, f"save_invoice: {e}")
            return _error_result(f"Failed to save invoice: {e}")

        from backend import tools
        tools.set_org_id(org_id)

        crew = build_crew(api_key)
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
                    log_event(org_id, "rate_limit_retry", {"attempt": attempt + 1, "wait": wait})
                    time.sleep(wait)
                    continue
                log_event(org_id, "audit_failed", {"stage": "crew", "error": msg})
                log_audit_error(run, f"crew: {e}")
                return _error_result(f"Crew execution failed: {e}")

        if last_err is not None:
            log_event(org_id, "audit_failed", {"stage": "crew", "error": str(last_err)})
            log_audit_error(run, f"crew_retries: {last_err}")
            return _error_result(f"Crew execution failed after retries: {last_err}")

        try:
            invoice = _parse_task_output(crew, 1)
            checks = _parse_task_output(crew, 2).get("checks", [])
            routing = _parse_task_output(crew, 3)
            report = _parse_task_output(crew, 4)
        except Exception as e:
            log_event(org_id, "audit_failed", {"stage": "parse", "error": str(e)})
            log_audit_error(run, f"parse: {e}")
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
            log_event(org_id, "audit_failed", {"stage": "output", "error": str(e)})
            log_audit_error(run, f"output: {e}")
            return _error_result(f"Output validation failed: {e}")

        try:
            audit_id = db.save_audit(invoice_id, org_id, result)
            db.save_audit_checks(audit_id, checks)
            result["audit_id"] = audit_id
        except Exception as e:
            log_event(org_id, "audit_failed", {"stage": "save_audit", "error": str(e)})

        log_event(org_id, "audit_complete", {
            "verdict": result["verdict"],
            "risk_score": result["risk_score"],
            "confidence": gate["confidence"],
        })

        log_audit_result(run, result)

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