import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

from langsmith.integrations.otel import OtelSpanProcessor
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.instrumentation.crewai import CrewAIInstrumentor
from opentelemetry.instrumentation.openai import OpenAIInstrumentor

# Get or create tracer provider
current_provider = trace.get_tracer_provider()
if isinstance(current_provider, TracerProvider):
    tracer_provider = current_provider
else:
    tracer_provider = TracerProvider()
    trace.set_tracer_provider(tracer_provider)

# Add LangSmith's span processor
tracer_provider.add_span_processor(OtelSpanProcessor())

# Instrument CrewAI and OpenAI
CrewAIInstrumentor().instrument(tracer_provider=tracer_provider)
OpenAIInstrumentor().instrument(tracer_provider=tracer_provider)

BASE_DIR = Path(__file__).resolve().parent.parent

DATA_DIR = BASE_DIR / "data"
INVOICES_DIR = DATA_DIR / "invoices"
UPLOADS_DIR = DATA_DIR / "uploads"
VENDORS_CSV = DATA_DIR / "vendors.csv"
RULES_JSON = DATA_DIR / "rules.json"
EXPECTED_JSON = DATA_DIR / "expected.json"
RESULTS_JSON = DATA_DIR / "results.json"
AUDIT_LOG = DATA_DIR / "audit_log.jsonl"

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
LANGSMITH_API_KEY = os.getenv("LANGSMITH_API_KEY", "")
LANGSMITH_TRACING = os.getenv("LANGSMITH_TRACING", "false").lower() == "true"
LANGSMITH_PROJECT = os.getenv("LANGSMITH_PROJECT", "trustflow")
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

os.environ["CREWAI_TRACING_ENABLED"] = "true"
os.environ["CREWAI_DISABLE_TELEMETRY"] = "false"

os.environ["LANGSMITH_PROJECT"] = LANGSMITH_PROJECT
os.environ["LANGSMITH_TRACING"] = "true" if LANGSMITH_TRACING else "false"
os.environ["LANGSMITH_API_KEY"] = LANGSMITH_API_KEY
os.environ.setdefault("LANGSMITH_ENDPOINT", "https://api.smith.langchain.com")

MODEL_NAME = "groq/openai/gpt-oss-120b"
TEMPERATURE = 0.2

MAX_FILE_SIZE_MB = 10
ALLOWED_EXTENSIONS = {".pdf", ".txt"}

VERDICT_APPROVE = "APPROVE"
VERDICT_REVIEW = "REVIEW"
VERDICT_REJECT = "REJECT"

RISK_APPROVE_MAX = 30
RISK_REVIEW_MAX = 70

UPLOADS_DIR.mkdir(parents=True, exist_ok=True)