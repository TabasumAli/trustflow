from crewai import Crew, Task, Process

from backend.llm import get_llm, get_small_llm
from backend.agents.intake_agent import build_intake_agent
from backend.agents.extractor_agent import build_extractor_agent
from backend.agents.validator_agent import build_validator_agent
from backend.agents.router_agent import build_router_agent
from backend.agents.reporter_agent import build_reporter_agent


def build_crew(api_key: str | None = None) -> Crew:
    llm = get_llm(api_key)
    small = get_small_llm(api_key)

    intake = build_intake_agent(small)
    extractor = build_extractor_agent(llm)
    validator = build_validator_agent(small)
    router = build_router_agent(small)
    reporter = build_reporter_agent(llm)

    intake_task = Task(
        description=(
            "Classify the document below. Respond with ONLY one word: "
            "invoice, form, application, or unknown.\n\n"
            "Document:\n{invoice_text}"
        ),
        expected_output="A single word: invoice, form, application, or unknown.",
        agent=intake,
    )

    extractor_task = Task(
        description=(
            "Extract exactly these fields from the document: vendor, "
            "invoice_number, amount, date, po_number, tax_id. "
            "Return ONLY JSON. If a field is missing, set it to null.\n\n"
            "Document:\n{invoice_text}"
        ),
        expected_output="JSON with vendor, invoice_number, amount, date, po_number, tax_id.",
        agent=extractor,
        context=[intake_task],
    )

    validator_task = Task(
        description=(
            "Apply each business rule below to the extracted invoice JSON "
            "from the previous task. For each rule decide pass or fail and "
            "give a one-line reason.\n\n"
            "Rules:\n{rules_json}\n\n"
            "Approved vendors:\n{vendors_json}\n\n"
            "Return ONLY JSON with a single key 'checks' — a list of objects "
            "with keys: rule, description, status, reason, weight, severity."
        ),
        expected_output="JSON object with a 'checks' list.",
        agent=validator,
        context=[extractor_task],
    )

    router_task = Task(
        description=(
            "Using the checks from the previous task, compute a risk score "
            "(0-100) as the weighted percentage of failed rules, then pick "
            "a verdict: APPROVE if score <= 30, REVIEW if <= 70, REJECT "
            "otherwise. Return ONLY JSON with keys: risk_score, verdict, reason."
        ),
        expected_output="JSON object with risk_score, verdict, reason.",
        agent=router,
        context=[validator_task],
    )

    reporter_task = Task(
        description=(
            "Using the extracted invoice, the rule checks, and the routing "
            "result from the previous tasks, write a 2-3 sentence audit "
            "summary and a one-line next action. Return ONLY JSON with keys "
            "'summary' and 'next_action'."
        ),
        expected_output="JSON object with summary and next_action.",
        agent=reporter,
        context=[extractor_task, validator_task, router_task],
    )

    return Crew(
        agents=[intake, extractor, validator, router, reporter],
        tasks=[intake_task, extractor_task, validator_task, router_task, reporter_task],
        process=Process.sequential,
        verbose=False,
    )