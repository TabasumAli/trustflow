from crewai import Agent


def build_intake_agent(llm) -> Agent:
    return Agent(
        role="Invoice Intake Specialist",
        goal="Determine file type and basic quality of the invoice.",
        backstory="You inspect incoming invoices and report their format.",
        llm=llm,
        verbose=False,
        allow_delegation=False,
    )