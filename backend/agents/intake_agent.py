"""
intake_agent.py — Part 1 (Intake & Extraction)
Owner: Joti

Real CrewAI agent for document-type classification (replaces the
temporary regex stub). Classifies each document as exactly one of:
invoice, form, application, or unknown.
"""

from crewai import Agent, Task


def build_intake_agent(llm) -> Agent:
    """
    Builds the Intake Agent. `llm` is passed in by crew.py (e.g. from
    backend.llm.get_llm()) — this file does no LLM setup of its own.
    """
    return Agent(
        role="Document Intake Specialist",
        goal=(
            "Classify incoming business documents into exactly one of: "
            "invoice, form, application, or unknown. Be decisive — only "
            "use 'unknown' when the document genuinely matches none of "
            "the others."
        ),
        backstory=(
            "You work at the front desk of TrustFlow. Every document that "
            "arrives passes through you first. Downstream agents "
            "(Extractor, Validator, Router) depend entirely on your "
            "classification being correct, so you read carefully before "
            "deciding."
        ),
        llm=llm,
        allow_delegation=False,
        verbose=True,
    )


def build_intake_task(agent: Agent, document_text: str) -> Task:
    """
    Task factory paired with build_intake_agent(). Added so crew.py has
    a ready-made Task to assign to this agent — remove/ignore if your
    crew.py already builds its own Task objects.
    """
    return Task(
        description=(
            "Read the document text below and classify it.\n\n"
            f"--- DOCUMENT TEXT ---\n{document_text[:3000]}\n--- END ---\n\n"
            "Respond with ONLY one word: invoice, form, application, or unknown."
        ),
        expected_output="A single word: invoice, form, application, or unknown.",
        agent=agent,
    )
