import json

from crewai import Agent

from backend.tools import check_all_rules, load_vendors


def build_validator_agent(llm) -> Agent:
    return Agent(
        role="Invoice Validator",
        goal=(
            "You receive a JSON invoice and a set of business rules. "
            "Evaluate each rule against the invoice and return ONLY a JSON "
            "object with key 'checks' — a list of objects with keys: "
            "rule, description, status ('pass' or 'fail'), reason, weight, severity."
        ),
        backstory=(
            "You are a meticulous compliance auditor. You compare invoice "
            "fields against rules exactly. You never invent results."
        ),
        llm=llm,
        verbose=False,
        allow_delegation=False,
        max_iter=2,
    )


def build_validator_agent(llm) -> Agent:
    return Agent(
        role="Invoice Validator",
        goal=(
            "You receive a JSON invoice and a set of business rules. "
            "Evaluate each rule against the invoice and return ONLY a JSON "
            "object with key 'checks' — a list of objects with keys: "
            "rule, description, status ('pass' or 'fail'), reason, weight, severity."
        ),
        backstory=(
            "You are a meticulous compliance auditor. You compare invoice "
            "fields against rules exactly. You never invent results."
        ),
        llm=llm,
        verbose=False,
        allow_delegation=False,
        max_iter=2,
    )
