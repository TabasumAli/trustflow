from crewai import LLM

from backend.config import GROQ_API_KEY, MODEL_NAME, TEMPERATURE


def get_llm() -> LLM:
    return LLM(
        model=MODEL_NAME,
        api_key=GROQ_API_KEY,
        temperature=TEMPERATURE,
    )


def get_small_llm() -> LLM:
    return LLM(
        model="groq/openai/gpt-oss-120b",
        api_key=GROQ_API_KEY,
        temperature=0.1,
    )