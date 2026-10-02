import json
import re

from crewai import Agent
from crewai.tools import tool


def _extract_fields(text: str) -> dict:
    def find(pattern: str, flags=0):
        m = re.search(pattern, text, flags)
        return m.group(1).strip() if m else None

    vendor = find(r"Vendor:\s*(.+)")
    invoice_number = find(r"Invoice\s*Number:\s*([^\s]+)")
    date = find(r"Date:\s*([\d\-/]+)")
    po_number = find(r"PO\s*Number:\s*([^\s]+)")
    tax_id = find(r"Tax\s*ID:\s*([A-Za-z\-0-9 ]+)")
    amount_raw = find(r"Amount\s*Due:\s*\$?([\d,\.]+)")

    amount = None
    if amount_raw:
        try:
            amount = float(amount_raw.replace(",", ""))
        except ValueError:
            amount = None

    if tax_id:
        tax_id = tax_id.replace(" ", "").upper()

    return {
        "vendor": vendor,
        "invoice_number": invoice_number,
        "amount": amount,
        "date": date,
        "po_number": po_number,
        "tax_id": tax_id,
    }


@tool("extract_invoice_fields")
def extract_invoice_fields_tool(invoice_text: str) -> str:
    """Extract invoice fields from raw invoice text. Returns JSON string."""
    return json.dumps(_extract_fields(invoice_text))


def build_extractor_agent(llm) -> Agent:
    return Agent(
        role="Invoice Extractor",
        goal=(
            "Extract invoice fields by calling the extract_invoice_fields tool. "
            "Return ONLY the tool's JSON output."
        ),
        backstory=(
            "You extract structured fields from invoices. You always call the "
            "extract_invoice_fields tool and return its output verbatim."
        ),
        tools=[extract_invoice_fields_tool],
        llm=llm,
        verbose=False,
        allow_delegation=False,
        max_iter=3,
    )