import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

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