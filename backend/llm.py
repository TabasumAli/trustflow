from crewai import LLM

from backend.config import GROQ_API_KEY, MODEL_NAME, TEMPERATURE


def get_llm(api_key: str | None = None) -> LLM:
    return LLM(
        model=MODEL_NAME,
        api_key=api_key or GROQ_API_KEY,
        temperature=TEMPERATURE,
        parallel_tool_calls=False,
    )


def get_small_llm(api_key: str | None = None) -> LLM:
    return LLM(
        model="groq/openai/gpt-oss-20b",
        api_key=api_key or GROQ_API_KEY,
        temperature=0.1,
        parallel_tool_calls=False,
    )