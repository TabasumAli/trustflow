# TrustFlow — AI Invoice Audit

An AI-powered invoice auditing system built with CrewAI and Streamlit. Upload an invoice, get back a rule-by-rule audit, a risk score, and a verdict of APPROVE, REVIEW, or REJECT.

![TrustFlow](docs/screenshots/dashboard.png)

## What It Does

1. Reads an uploaded invoice (PDF or TXT)
2. Runs a 5-agent CrewAI pipeline:
   - **Intake** — inspects file structure
   - **Extractor** — pulls vendor, invoice number, amount, date, PO number, tax ID
   - **Validator** — checks the invoice against 9 business rules
   - **Router** — computes risk score and verdict
   - **Reporter** — writes a human-readable summary
3. Applies a confidence gate
4. Traces every agent step in LangSmith (via OpenTelemetry)
5. Persists vendors, rules, invoices, and audit results in Supabase
6. Returns a styled dashboard with verdict card, rule checks, and a downloadable PDF report

## Stack

- **CrewAI** — multi-agent orchestration
- **Groq** — LLM inference (`openai/gpt-oss-120b`)
- **Streamlit** — frontend
- **Supabase** — Postgres database + storage for vendors, rules, invoices, audits
- **LangSmith** — observability (agent-level traces via OpenTelemetry)
- **pypdf** — PDF text extraction
- **ReportLab** — PDF report generation

## Features

- 🎨 Dark modern dashboard with gradient verdict cards
- 🔐 User-supplied Groq API key (session-only, never stored)
- 📊 Three tabs: Setup, Audit, History
- ⚙️ Upload your own `vendors.csv` and `rules.json` — stored in Supabase
- 🗑️ One-click database management (delete vendors, rules, or both)
- 🔍 Per-rule pass/fail rendering with severity indicators
- 📄 Downloadable PDF audit report
- 📜 Audit history with KPIs and filters
- 📡 Full agent-level tracing in LangSmith

## Install

```bash
python -m venv .venv
.venv\Scripts\Activate.ps1     # Windows
# source .venv/bin/activate    # macOS / Linux
pip install -r requirements.txt