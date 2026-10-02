# TrustFlow — AI Invoice Audit

An AI-powered invoice auditing system built with CrewAI and Streamlit. Upload an invoice, get back a rule-by-rule audit, a risk score, and a verdict of APPROVE, REVIEW, or REJECT.

## What It Does

1. Reads an uploaded invoice (PDF or TXT)
2. Runs a 5-agent CrewAI pipeline:
   - **Intake** — inspects file structure
   - **Extractor** — pulls vendor, invoice number, amount, date, PO number, tax ID
   - **Validator** — checks the invoice against 9 business rules
   - **Router** — computes risk score and verdict
   - **Reporter** — writes a human-readable summary
3. Applies a confidence gate
4. Logs every step
5. Returns structured JSON to the UI

## Stack

- **CrewAI** — multi-agent orchestration
- **Groq** — LLM inference (`openai/gpt-oss-120b`)
- **Streamlit** — frontend
- **LangSmith** — tracing (optional)
- **pypdf** — PDF text extraction

## Install

```bash
python -m venv .venv
.venv\Scripts\Activate.ps1     # Windows
pip install -r requirements.txt