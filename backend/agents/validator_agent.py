from crewai import Agent
from crewai.tools import tool

from backend.tools import check_all_rules, load_vendors


@tool("validate_invoice")
def validate_invoice_tool(invoice_json: str) -> str:
    """Validate an invoice against all business rules.
    Input: JSON string with keys vendor, invoice_number, amount, date, po_number, tax_id.
    Output: JSON string with a 'checks' list."""
    import json

    invoice = json.loads(invoice_json)
    vendors = load_vendors()
    checks = check_all_rules(invoice, vendors)
    return json.dumps({"checks": checks})


def build_validator_agent(llm) -> Agent:
    return Agent(
        role="Invoice Validator",
        goal=(
            "Validate each invoice field against the business rules by calling "
            "the validate_invoice tool. Return ONLY the tool's JSON output."
        ),
        backstory=(
            "You are a meticulous compliance auditor. You never invent rule results. "
            "You always call the validate_invoice tool and return its output verbatim."
        ),
        tools=[validate_invoice_tool],
        llm=llm,
        verbose=False,
        allow_delegation=False,
        max_iter=3,
    )