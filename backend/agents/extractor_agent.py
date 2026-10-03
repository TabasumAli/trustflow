"""
extractor_agent.py — Part 1 (Intake & Extraction)
Owner: Joti

Real CrewAI agent for field extraction (replaces the temporary regex
stub). Always returns strict JSON with exactly these keys: vendor,
invoice_number, amount, date, po_number, tax_id. Any field not present
in the document comes back as null — the agent must never invent one.
"""

from typing import Optional

from crewai import Agent, Task
from pydantic import BaseModel


class ExtractedFields(BaseModel):
    vendor: Optional[str] = None
    invoice_number: Optional[str] = None
    amount: Optional[float] = None
    date: Optional[str] = None
    po_number: Optional[str] = None
    tax_id: Optional[str] = None


def build_extractor_agent(llm) -> Agent:
    """
    Builds the Extractor Agent. `llm` is passed in by crew.py (e.g. from
    backend.llm.get_llm()) — this file does no LLM setup of its own.
    """
    return Agent(
        role="Field Extraction Specialist",
        goal=(
            "Extract exactly these six fields from a business document: "
            "vendor, invoice_number, amount, date, po_number, tax_id. "
            "Never invent a value — if a field genuinely isn't in the "
            "text, return null for it."
        ),
        backstory=(
            "You are a meticulous data-entry expert for TrustFlow. Every "
            "field you extract is logged in the audit trail with your "
            "reasoning, so guessing is not acceptable — accuracy matters "
            "more than completeness."
        ),
        llm=llm,
        allow_delegation=False,
        verbose=True,
    )


def build_extraction_task(agent: Agent, document_text: str) -> Task:
    """
    Task factory paired with build_extractor_agent(). Uses
    output_pydantic so CrewAI enforces the schema at the framework
    level — the result is guaranteed to be valid JSON with exactly
    these six keys, nothing extra, nothing missing.
    """
    return Task(
        description=(
            "Extract the following fields from the document text below: "
            "vendor, invoice_number, amount, date, po_number, tax_id.\n\n"
            f"--- DOCUMENT TEXT ---\n{document_text[:3000]}\n--- END ---\n\n"
            "Rules:\n"
            "- amount must be a plain number (no currency symbols, no commas)\n"
            "- if a field is not present in the text, set it to null\n"
            "- do not invent, guess, or infer a value that isn't written in the text"
        ),
        expected_output=(
            "A JSON object with exactly these keys: vendor, invoice_number, "
            "amount, date, po_number, tax_id."
        ),
        agent=agent,
        output_pydantic=ExtractedFields,
    )
