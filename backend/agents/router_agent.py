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

    return json.dumps({
        "risk_score": score,
        "verdict": verdict,
        "reason": reason,
    })


def build_router_agent(llm) -> Agent:
    return Agent(
        role="Invoice Router",
        goal=(
            "Determine the final verdict (APPROVE, REVIEW, or REJECT) by calling "
            "the route_invoice tool. Return ONLY the tool's JSON output."
        ),
        backstory=(
            "You are a routing specialist. You never guess a verdict. "
            "You always call the route_invoice tool and return its output verbatim."
        ),
        tools=[route_invoice_tool],
        llm=llm,
        verbose=False,
        allow_delegation=False,
        max_iter=3,
    )