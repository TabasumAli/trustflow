import os
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from backend import config


def init_tracing() -> None:
    """Set LangSmith env vars so CrewAI auto-reports traces."""
    if not config.LANGSMITH_TRACING:
        os.environ["LANGSMITH_TRACING"] = "false"
        return
    if not config.LANGSMITH_API_KEY:
        os.environ["LANGSMITH_TRACING"] = "false"
        return
    os.environ["LANGSMITH_TRACING"] = "true"
    os.environ["LANGSMITH_API_KEY"] = config.LANGSMITH_API_KEY
    os.environ["LANGSMITH_PROJECT"] = config.LANGSMITH_PROJECT
    os.environ.setdefault("LANGSMITH_ENDPOINT", "https://api.smith.langchain.com")


@contextmanager
def trace_audit(org_id: str, filename: str):
    """
    Opens a named, tagged LangSmith run around the crew execution.
    Yields the run object (or None if tracing disabled).
    """
    run = None
    try:
        from langsmith import Client, RunTree
    except ImportError:
        yield None
        return

    if not config.LANGSMITH_TRACING or not config.LANGSMITH_API_KEY:
        yield None
        return

    try:
        client = Client(
            api_url=os.environ.get("LANGSMITH_ENDPOINT", "https://api.smith.langchain.com"),
            api_key=config.LANGSMITH_API_KEY,
        )
        run = RunTree(
            name=f"audit: {filename}",
            run_type="chain",
            inputs={"filename": filename, "org_id": org_id},
            tags=["audit", f"org:{org_id}"],
            extra={
                "metadata": {
                    "org_id": org_id,
                    "filename": filename,
                    "started_at": datetime.now(timezone.utc).isoformat(),
                }
            },
            client=client,
            project_name=config.LANGSMITH_PROJECT,
        )
        run.post()
    except Exception:
        run = None

    try:
        yield run
    finally:
        if run is not None:
            try:
                run.end()
                run.patch()
            except Exception:
                pass


def log_audit_result(run, result: Dict[str, Any]) -> None:
    """Attach verdict, score, confidence, warnings as metadata + outputs."""
    if run is None:
        return
    try:
        gate = result.get("gate", {}) or {}
        run.end(
            outputs={
                "verdict": result.get("verdict"),
                "risk_score": result.get("risk_score"),
                "confidence": gate.get("confidence"),
                "summary": result.get("summary", "")[:300],
                "failed_rules": [
                    c.get("rule")
                    for c in result.get("checks", [])
                    if c.get("status") == "fail"
                ],
            }
        )
        run.extra = run.extra or {}
        run.extra["metadata"] = {
            **(run.extra.get("metadata", {})),
            "verdict": result.get("verdict"),
            "risk_score": result.get("risk_score"),
            "confidence": gate.get("confidence"),
            "gate_passed": gate.get("passed"),
            "gate_warnings": gate.get("warnings", []),
        }
        run.tags = list(set((run.tags or []) + [
            f"verdict:{result.get('verdict')}",
            f"risk:{result.get('risk_score')}",
        ]))
        run.patch()
    except Exception:
        pass


def log_audit_error(run, message: str) -> None:
    """Attach an error to the current run before it closes."""
    if run is None:
        return
    try:
        run.end(error=message)
        run.patch()
    except Exception:
        pass