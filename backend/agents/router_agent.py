import json

from crewai import Agent
from crewai.tools import tool

from backend.tools import score_risk
from backend.guardrails import expected_verdict_from_score


@tool("route_invoice")
def route_invoice_tool(checks_json: str) -> str:
    """Compute the risk score and verdict from a checks list.
    Input: JSON string with a 'checks' list.
    Output: JSON string with risk_score, verdict, and reason."""
    data = json.loads(checks_json)
    checks = data.get("checks", [])

    score = score_risk(checks)
    verdict = expected_verdict_from_score(score)

    failed = [c["rule"] for c in checks if c["status"] == "fail"]
    if failed:
        reason = f"Failed rules: {', '.join(failed)}"
    else:
        reason = "All rules passed"

    return json.dumps(
        {
            "risk_score": score,
            "verdict": verdict,
            "reason": reason,
        }
    )


def build_router_agent(llm) -> Agent:
    return Agent(
        role="Invoice Router",
        goal=(
            "You receive a checks list from the previous task. Compute a risk "
            "score (0-100) as the weighted percentage of failed rules, then "
            "pick a verdict: APPROVE if score <= 30, REVIEW if <= 70, "
            "REJECT otherwise. Return ONLY JSON with keys: risk_score, "
            "verdict, reason."
        ),
        backstory=(
            "You are a routing specialist. You apply the thresholds exactly "
            "and never guess."
        ),
        llm=llm,
        verbose=False,
        allow_delegation=False,
        max_iter=2,
    )
