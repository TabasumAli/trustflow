from crewai import Agent


def build_reporter_agent(llm) -> Agent:
    return Agent(
        role="Audit Reporter",
        goal=(
            "Write a concise, professional audit summary in 2-3 sentences. "
            "Mention the vendor, amount, verdict, and any failed rules. "
            "Return ONLY valid JSON with keys 'summary' and 'next_action'."
        ),
        backstory=(
            "You are a senior audit writer. Your summaries are clear, factual, "
            "and free of jargon. You never invent facts that aren't in the input."
        ),
        llm=llm,
        verbose=False,
        allow_delegation=False,
        max_iter=3,
    )