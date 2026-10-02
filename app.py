import io
from datetime import datetime

import streamlit as st
import pandas as pd

from backend.api import run_audit
from backend import db, tools

DEMO_ORG_ID = "00000000-0000-0000-0000-000000000001"

st.set_page_config(
    page_title="TrustFlow",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ============================================================
# GLOBAL STYLES — dark theme, yellow/orange accents
# ============================================================
st.markdown(
    """
    <style>
        .stApp { background: #0a0a0a; color: #f5f5f5; }
        .main, .block-container { background: #0a0a0a; }
        html, body, [class*="css"] { color: #f5f5f5; }

        section[data-testid="stSidebar"] {
            background: #111111;
            border-right: 1px solid #222;
        }
        section[data-testid="stSidebar"] * { color: #f5f5f5 !important; }
        section[data-testid="stSidebar"] input {
            background: #1c1c1c !important;
            color: #f5f5f5 !important;
            border: 1px solid #333 !important;
            border-radius: 8px;
        }

        h1, h2, h3, h4, h5, h6, p, span, label, div { color: #f5f5f5; }

        .tf-header {
            background: linear-gradient(135deg, #f59e0b 0%, #ea580c 100%);
            padding: 28px 32px;
            border-radius: 16px;
            color: #0a0a0a;
            margin-bottom: 24px;
            box-shadow: 0 8px 32px rgba(245,158,11,0.25);
        }
        .tf-header h1 {
            margin: 0; font-size: 28px; font-weight: 800;
            letter-spacing: -0.5px; color: #0a0a0a;
        }
        .tf-header p {
            margin: 6px 0 0 0; opacity: 0.85; font-size: 14px;
            color: #0a0a0a; font-weight: 500;
        }

        .tf-card {
            background: #141414;
            border-radius: 14px;
            padding: 18px 20px;
            box-shadow: 0 2px 12px rgba(0,0,0,0.5);
            border: 1px solid #262626;
        }

        .tf-metric-label {
            color: #a3a3a3; font-size: 11px; font-weight: 600;
            text-transform: uppercase; letter-spacing: 1px;
        }
        .tf-metric-value {
            color: #f5f5f5; font-size: 24px; font-weight: 700;
            margin-top: 6px;
        }

        .tf-verdict-card {
            border-radius: 16px;
            padding: 28px 32px;
            margin-bottom: 20px;
            box-shadow: 0 12px 40px rgba(0,0,0,0.6);
            border: 1px solid #262626;
            background: #141414;
        }
        .tf-verdict-approve { border-left: 8px solid #22c55e; }
        .tf-verdict-review  { border-left: 8px solid #f59e0b; }
        .tf-verdict-reject  { border-left: 8px solid #ef4444; }
        .tf-verdict-unknown { border-left: 8px solid #6b7280; }

        .tf-verdict-label {
            font-size: 12px; color: #a3a3a3; letter-spacing: 1.5px;
            text-transform: uppercase; font-weight: 600;
        }
        .tf-verdict-title {
            font-size: 42px; font-weight: 800; margin: 4px 0 8px 0;
            letter-spacing: -1px; color: #f5f5f5;
        }
        .tf-verdict-title.approve { color: #22c55e; }
        .tf-verdict-title.review  { color: #f59e0b; }
        .tf-verdict-title.reject  { color: #ef4444; }
        .tf-verdict-meta { font-size: 14px; color: #d4d4d4; }

        .tf-rule-pass {
            padding: 12px 16px; border-radius: 10px;
            background: #0f1a12; border-left: 4px solid #22c55e;
            margin-bottom: 8px;
        }
        .tf-rule-fail {
            padding: 12px 16px; border-radius: 10px;
            background: #1a0f0f; border-left: 4px solid #ef4444;
            margin-bottom: 8px;
        }
        .tf-rule-name { font-weight: 600; color: #f5f5f5; font-size: 14px; }
        .tf-rule-meta { font-size: 12px; color: #a3a3a3; margin-left: 8px; }
        .tf-rule-reason { font-size: 13px; color: #fca5a5; margin-top: 4px; }

        .tf-section-title {
            font-size: 18px; font-weight: 700; color: #f5f5f5;
            margin: 28px 0 12px 0;
            border-bottom: 2px solid #f59e0b;
            padding-bottom: 8px;
            display: inline-block;
        }

        .stButton > button {
            border-radius: 10px;
            font-weight: 700;
            padding: 10px 22px;
            transition: all 0.2s ease;
            background: linear-gradient(135deg, #f59e0b, #ea580c);
            color: #0a0a0a;
            border: none;
            box-shadow: 0 4px 14px rgba(245,158,11,0.35);
        }
        .stButton > button:hover {
            transform: translateY(-1px);
            box-shadow: 0 6px 20px rgba(245,158,11,0.55);
            color: #0a0a0a;
        }
        .stButton > button:disabled {
            background: #262626 !important;
            color: #6b7280 !important;
            box-shadow: none;
            opacity: 0.6;
        }

        .stDownloadButton > button {
            border-radius: 10px;
            font-weight: 700;
            padding: 10px 22px;
            background: linear-gradient(135deg, #f59e0b, #ea580c);
            color: #0a0a0a;
            border: none;
            box-shadow: 0 4px 14px rgba(245,158,11,0.35);
        }
        .stDownloadButton > button:hover {
            transform: translateY(-1px);
            box-shadow: 0 6px 20px rgba(245,158,11,0.55);
            color: #0a0a0a;
        }

        div[data-testid="stMetricValue"] {
            font-size: 26px; font-weight: 700; color: #f59e0b;
        }
        div[data-testid="stMetricLabel"] {
            color: #a3a3a3; font-size: 11px; text-transform: uppercase;
            letter-spacing: 1px;
        }
        div[data-testid="stMetric"] {
            background: #141414;
            border: 1px solid #262626;
            border-radius: 12px;
            padding: 14px 16px;
        }

        .stTabs [data-baseweb="tab-list"] {
            gap: 8px;
            background: #0a0a0a;
            border-bottom: 1px solid #262626;
        }
        .stTabs [data-baseweb="tab"] {
            background: #141414;
            color: #a3a3a3;
            border-radius: 10px 10px 0 0;
            padding: 10px 20px;
            font-weight: 600;
            border: 1px solid #262626;
            border-bottom: none;
        }
        .stTabs [aria-selected="true"] {
            background: linear-gradient(135deg, #f59e0b, #ea580c);
            color: #0a0a0a !important;
        }

        .stDataFrame, div[data-testid="stDataFrame"] {
            background: #141414;
            border-radius: 10px;
            border: 1px solid #262626;
        }

        details {
            background: #141414 !important;
            border: 1px solid #262626 !important;
            border-radius: 10px !important;
        }
        details summary {
            color: #f5f5f5 !important;
            font-weight: 600;
        }

        .stAlert {
            border-radius: 10px;
            border: 1px solid #262626;
            background: #141414;
        }

        .stTextInput input, .stSelectbox div[data-baseweb="select"] {
            background: #1c1c1c !important;
            color: #f5f5f5 !important;
            border: 1px solid #333 !important;
            border-radius: 8px;
        }

        section[data-testid="stFileUploaderDropzone"] {
            background: #141414;
            border: 2px dashed #333;
            border-radius: 12px;
        }
        section[data-testid="stFileUploaderDropzone"]:hover {
            border-color: #f59e0b;
        }

        hr { border-color: #262626; }

        ::-webkit-scrollbar { width: 8px; height: 8px; }
        ::-webkit-scrollbar-track { background: #0a0a0a; }
        ::-webkit-scrollbar-thumb { background: #333; border-radius: 4px; }
        ::-webkit-scrollbar-thumb:hover { background: #f59e0b; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ============================================================
# SIDEBAR
# ============================================================
if "groq_api_key" not in st.session_state:
    st.session_state.groq_api_key = ""

with st.sidebar:
    st.markdown(
        """
        <div style="padding: 10px 0 20px 0;">
            <div style="font-size: 22px; font-weight: 800; color: #f59e0b;">🛡️ TrustFlow</div>
            <div style="font-size: 12px; opacity: 0.7;">AI Invoice Audit</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown("---")
    st.markdown("**🔑 Groq API Key**")
    key_input = st.text_input(
        "Groq API Key",
        type="password",
        value=st.session_state.groq_api_key,
        label_visibility="collapsed",
        placeholder="gsk_...",
    )
    if key_input != st.session_state.groq_api_key:
        st.session_state.groq_api_key = key_input

    if st.session_state.groq_api_key:
        st.success("Key loaded")
    else:
        st.warning("Enter your key to run audits")

    st.markdown("---")
    st.markdown(
        """
        <div style="font-size: 11px; opacity: 0.6; line-height: 1.6;">
            Get a key at <a href="https://console.groq.com/keys" target="_blank" style="color:#f59e0b;">console.groq.com/keys</a>
        </div>
        """,
        unsafe_allow_html=True,
    )

# ============================================================
# HEADER
# ============================================================
st.markdown(
    """
    <div class="tf-header">
        <h1>🛡️ TrustFlow — Invoice Audit Dashboard</h1>
        <p>Multi-agent AI audit · Real-time verdicts · Full observability</p>
    </div>
    """,
    unsafe_allow_html=True,
)

tab_setup, tab_audit, tab_history = st.tabs(["⚙️ Setup", "🔍 Audit", "📜 History"])


# ============================================================
# PDF REPORT GENERATOR
# ============================================================
def build_pdf_report(result: dict) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.lib import colors
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    )

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=18*mm, rightMargin=18*mm,
        topMargin=18*mm, bottomMargin=18*mm,
        title="TrustFlow Audit Report",
    )

    styles = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=styles["Heading1"], fontSize=20, spaceAfter=10, textColor=colors.HexColor("#ea580c"))
    h2 = ParagraphStyle("h2", parent=styles["Heading2"], fontSize=13, spaceAfter=6, textColor=colors.HexColor("#0a0a0a"))
    body = ParagraphStyle("body", parent=styles["BodyText"], fontSize=10, leading=14, textColor=colors.HexColor("#0a0a0a"))
    small = ParagraphStyle("small", parent=styles["BodyText"], fontSize=9, textColor=colors.HexColor("#525252"))

    story = []
    verdict = result.get("verdict", "UNKNOWN")
    score = result.get("risk_score", 0)
    confidence = result.get("gate", {}).get("confidence", 0.0)
    invoice = result.get("invoice", {}) or {}
    checks = result.get("checks", [])

    story.append(Paragraph("TrustFlow — Audit Report", h1))
    story.append(Paragraph(f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}", small))
    story.append(Spacer(1, 12))

    verdict_color = {
        "APPROVE": colors.HexColor("#16a34a"),
        "REVIEW": colors.HexColor("#ea580c"),
        "REJECT": colors.HexColor("#dc2626"),
    }.get(verdict, colors.HexColor("#6b7280"))

    banner = Table(
        [[Paragraph(f"<b>VERDICT:</b> {verdict}", ParagraphStyle("v", fontSize=16, textColor=colors.white)),
          Paragraph(f"<b>RISK:</b> {score}/100", ParagraphStyle("v2", fontSize=16, textColor=colors.white, alignment=2))]],
        colWidths=[110*mm, 60*mm],
    )
    banner.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), verdict_color),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("LEFTPADDING", (0,0), (-1,-1), 14),
        ("RIGHTPADDING", (0,0), (-1,-1), 14),
        ("TOPPADDING", (0,0), (-1,-1), 12),
        ("BOTTOMPADDING", (0,0), (-1,-1), 12),
    ]))
    story.append(banner)
    story.append(Spacer(1, 12))
    story.append(Paragraph(f"<b>Confidence:</b> {confidence*100:.0f}%", body))
    story.append(Spacer(1, 10))

    story.append(Paragraph("Invoice Details", h2))
    inv_rows = [[Paragraph(f"<b>{k.replace('_',' ').title()}</b>", body), Paragraph(str(v if v not in (None,'') else '—'), body)] for k, v in invoice.items()]
    if inv_rows:
        t = Table(inv_rows, colWidths=[50*mm, 120*mm])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (0,-1), colors.HexColor("#f5f5f5")),
            ("BOX", (0,0), (-1,-1), 0.5, colors.HexColor("#d4d4d4")),
            ("INNERGRID", (0,0), (-1,-1), 0.25, colors.HexColor("#e5e5e5")),
            ("LEFTPADDING", (0,0), (-1,-1), 8),
            ("RIGHTPADDING", (0,0), (-1,-1), 8),
            ("TOPPADDING", (0,0), (-1,-1), 6),
            ("BOTTOMPADDING", (0,0), (-1,-1), 6),
        ]))
        story.append(t)
    story.append(Spacer(1, 14))

    story.append(Paragraph("Summary", h2))
    story.append(Paragraph(result.get("summary", "—"), body))
    story.append(Spacer(1, 8))
    if result.get("next_action"):
        story.append(Paragraph(f"<b>Next action:</b> {result['next_action']}", body))
    if result.get("routing_reason"):
        story.append(Paragraph(f"<i>Routing reason:</i> {result['routing_reason']}", small))
    story.append(Spacer(1, 14))

    story.append(Paragraph("Rule Checks", h2))
    rule_rows = [["Rule", "Status", "Severity", "Reason"]]
    for c in checks:
        rule_rows.append([
            Paragraph(c.get("rule", ""), body),
            "PASS" if c.get("status") == "pass" else "FAIL",
            c.get("severity", ""),
            Paragraph(c.get("reason", "") or "—", small),
        ])
    t = Table(rule_rows, colWidths=[45*mm, 20*mm, 22*mm, 83*mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#ea580c")),
        ("TEXTCOLOR", (0,0), (-1,0), colors.white),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("BOX", (0,0), (-1,-1), 0.5, colors.HexColor("#d4d4d4")),
        ("INNERGRID", (0,0), (-1,-1), 0.25, colors.HexColor("#e5e5e5")),
        ("LEFTPADDING", (0,0), (-1,-1), 6),
        ("RIGHTPADDING", (0,0), (-1,-1), 6),
        ("TOPPADDING", (0,0), (-1,-1), 5),
        ("BOTTOMPADDING", (0,0), (-1,-1), 5),
    ]))
    story.append(t)

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()


# ============================================================
# SETUP TAB
# ============================================================
with tab_setup:
    st.markdown('<div class="tf-section-title">⚙️ Setup — Vendors & Rules</div>', unsafe_allow_html=True)
    st.caption("Upload your vendors and rules to Supabase. Manage what's currently stored below.")

    st.markdown("### 🗑️ Database Management")
    st.caption("Remove stored vendors or rules for this organization. Invoices and past audits are not affected.")

    col_d1, col_d2, col_d3 = st.columns(3)
    with col_d1:
        if st.button("🗑️ Delete All Vendors", use_container_width=True):
            try:
                existing = db.get_vendors(DEMO_ORG_ID)
                if not existing:
                    st.warning("No vendors found — nothing to delete.")
                else:
                    deleted = db.delete_vendors(DEMO_ORG_ID)
                    st.success(f"Deleted {deleted or len(existing)} vendor(s).")
                    st.rerun()
            except Exception as e:
                st.error(f"Delete failed: {e}")
    with col_d2:
        if st.button("🗑️ Delete All Rules", use_container_width=True):
            try:
                existing = db.get_rules(DEMO_ORG_ID)
                if not existing:
                    st.warning("No rules found — nothing to delete.")
                else:
                    deleted = db.delete_rules(DEMO_ORG_ID)
                    st.success(f"Deleted {deleted or len(existing)} rule(s).")
                    st.rerun()
            except Exception as e:
                st.error(f"Delete failed: {e}")
    with col_d3:
        if st.button("🗑️ Delete Both", use_container_width=True):
            try:
                v = db.get_vendors(DEMO_ORG_ID)
                r = db.get_rules(DEMO_ORG_ID)
                if not v and not r:
                    st.warning("No vendors or rules found — nothing to delete.")
                else:
                    if v:
                        db.delete_vendors(DEMO_ORG_ID)
                    if r:
                        db.delete_rules(DEMO_ORG_ID)
                    st.success(f"Deleted {len(v)} vendor(s) and {len(r)} rule(s).")
                    st.rerun()
            except Exception as e:
                st.error(f"Delete failed: {e}")

    st.markdown("---")

    col1, col2 = st.columns(2)
    with col1:
        vendors_file = st.file_uploader("📁 vendors.csv", type=["csv"], key="vendors_up")
    with col2:
        rules_file = st.file_uploader("📁 rules.json", type=["json"], key="rules_up")

    if st.button("⬆️ Save to Database", type="primary"):
        if not vendors_file and not rules_file:
            st.warning("Upload at least one file.")
        else:
            try:
                if vendors_file:
                    v_count = tools.save_vendors_from_csv(DEMO_ORG_ID, vendors_file.getvalue())
                    st.success(f"Saved {v_count} vendors.")
                if rules_file:
                    r_count = tools.save_rules_from_json(DEMO_ORG_ID, rules_file.getvalue())
                    st.success(f"Saved {r_count} rules.")
            except Exception as e:
                st.error(f"Save failed: {e}")

    st.markdown("---")
    st.markdown('<div class="tf-section-title">📊 Current Data</div>', unsafe_allow_html=True)

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Vendors**")
        try:
            vendors = db.get_vendors(DEMO_ORG_ID)
            if vendors:
                st.dataframe(pd.DataFrame(vendors), use_container_width=True, height=320)
                st.caption(f"{len(vendors)} vendor(s) stored.")
            else:
                st.info("No vendors yet.")
        except Exception as e:
            st.error(f"Fetch failed: {e}")

    with c2:
        st.markdown("**Rules**")
        try:
            rules = db.get_rules(DEMO_ORG_ID)
            if rules:
                st.dataframe(pd.DataFrame(rules), use_container_width=True, height=320)
                st.caption(f"{len(rules)} rule(s) stored.")
            else:
                st.info("No rules yet.")
        except Exception as e:
            st.error(f"Fetch failed: {e}")


# ============================================================
# AUDIT TAB
# ============================================================
with tab_audit:
    st.markdown('<div class="tf-section-title">🔍 Run Invoice Audit</div>', unsafe_allow_html=True)

    uploaded = st.file_uploader("Upload invoice (PDF or TXT)", type=["pdf", "txt"], key="invoice_up")

    can_run = uploaded is not None and bool(st.session_state.groq_api_key)

    if not st.session_state.groq_api_key:
        st.warning("Enter your Groq API key in the sidebar first.")

    if st.button("▶️ Run Audit", type="primary", disabled=not can_run):
        if uploaded:
            with st.spinner("Running audit crew — 5 agents working..."):
                try:
                    result = run_audit(
                        uploaded.getvalue(),
                        uploaded.name,
                        DEMO_ORG_ID,
                        api_key=st.session_state.groq_api_key,
                    )
                except Exception as e:
                    st.error(f"Audit failed: {e}")
                    result = None

            if result:
                if "error" in result:
                    st.error(f"Audit error: {result['error']}")
                else:
                    st.session_state.last_result = result

    result = st.session_state.get("last_result")

    if result:
        verdict = result.get("verdict", "UNKNOWN")
        score = result.get("risk_score", 0)
        confidence = result.get("gate", {}).get("confidence", 0.0)
        summary = result.get("summary", "")
        next_action = result.get("next_action", "")
        routing_reason = result.get("routing_reason", "")
        invoice = result.get("invoice", {}) or {}
        checks = result.get("checks", [])

        verdict_class = {
            "APPROVE": "tf-verdict-approve",
            "REVIEW": "tf-verdict-review",
            "REJECT": "tf-verdict-reject",
        }.get(verdict, "tf-verdict-unknown")

        title_class = {
            "APPROVE": "approve",
            "REVIEW": "review",
            "REJECT": "reject",
        }.get(verdict, "")

        icon = {"APPROVE": "✅", "REVIEW": "⚠️", "REJECT": "⛔"}.get(verdict, "❔")

        st.markdown(
            f"""
            <div class="tf-verdict-card {verdict_class}">
                <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:12px;">
                    <div>
                        <div class="tf-verdict-label">Audit Verdict</div>
                        <div class="tf-verdict-title {title_class}">{icon} {verdict}</div>
                        <div class="tf-verdict-meta">
                            <b>{invoice.get('vendor', 'Unknown vendor')}</b> &nbsp;·&nbsp;
                            {invoice.get('invoice_number', '—')} &nbsp;·&nbsp;
                            ${invoice.get('amount', '0')}
                        </div>
                    </div>
                    <div style="text-align:right;">
                        <div class="tf-verdict-label">Risk Score</div>
                        <div class="tf-verdict-title {title_class}">{score}<span style="font-size:20px;opacity:0.7;">/100</span></div>
                        <div class="tf-verdict-meta">Confidence: {confidence*100:.0f}%</div>
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Checks Passed", f"{sum(1 for c in checks if c.get('status')=='pass')}/{len(checks)}")
        c2.metric("Checks Failed", sum(1 for c in checks if c.get("status") == "fail"))
        c3.metric("High Severity Fails", sum(1 for c in checks if c.get("status") == "fail" and c.get("severity") == "high"))
        c4.metric("Gate Status", "✅ Passed" if result.get("gate", {}).get("passed") else "⚠️ Flagged")

        try:
            pdf_bytes = build_pdf_report(result)
            fname = f"trustflow_report_{invoice.get('invoice_number','audit')}.pdf".replace(" ", "_")
            st.download_button(
                "⬇️ Download PDF Report",
                data=pdf_bytes,
                file_name=fname,
                mime="application/pdf",
            )
        except Exception as e:
            st.warning(f"PDF report unavailable: {e}")

        st.markdown('<div class="tf-section-title">📋 Summary</div>', unsafe_allow_html=True)
        st.write(summary or "_No summary produced._")
        if next_action:
            st.info(f"**Recommended next action:** {next_action}")
        if routing_reason:
            st.caption(f"Routing reason: {routing_reason}")

        st.markdown('<div class="tf-section-title">📄 Invoice Details</div>', unsafe_allow_html=True)
        if invoice:
            inv_cols = st.columns(3)
            for i, (k, v) in enumerate(invoice.items()):
                with inv_cols[i % 3]:
                    st.markdown(
                        f"<div class='tf-card'>"
                        f"<div class='tf-metric-label'>{k.replace('_',' ')}</div>"
                        f"<div class='tf-metric-value'>{v if v not in (None,'') else '—'}</div>"
                        f"</div>",
                        unsafe_allow_html=True,
                    )
        else:
            st.warning("No invoice fields extracted.")

        st.markdown('<div class="tf-section-title">🔍 Rule Checks</div>', unsafe_allow_html=True)
        for c in checks:
            status = c.get("status")
            sev = c.get("severity", "low")
            sev_icon = {"high": "🔴", "medium": "🟠", "low": "🟡"}.get(sev, "⚪")
            if status == "pass":
                st.markdown(
                    f"<div class='tf-rule-pass'>"
                    f"<span class='tf-rule-name'>✅ {c.get('rule')}</span>"
                    f"<span class='tf-rule-meta'>{sev_icon} {sev}</span>"
                    f"</div>",
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    f"<div class='tf-rule-fail'>"
                    f"<span class='tf-rule-name'>❌ {c.get('rule')}</span>"
                    f"<span class='tf-rule-meta'>{sev_icon} {sev}</span>"
                    f"<div class='tf-rule-reason'>{c.get('reason','')}</div>"
                    f"</div>",
                    unsafe_allow_html=True,
                )

        with st.expander("🔧 Gate details"):
            st.json(result.get("gate", {}))
        with st.expander("📦 Full raw result"):
            st.json(result)


# ============================================================
# HISTORY TAB
# ============================================================
with tab_history:
    st.markdown('<div class="tf-section-title">📜 Audit History</div>', unsafe_allow_html=True)

    try:
        audits = db.list_audits(DEMO_ORG_ID, limit=100)
        if not audits:
            st.info("No audits yet.")
        else:
            rows = []
            for a in audits:
                inv = a.get("invoices") or {}
                rows.append({
                    "id": a.get("id"),
                    "date": a.get("created_at"),
                    "filename": inv.get("filename", "—"),
                    "verdict": a.get("verdict"),
                    "risk_score": a.get("risk_score"),
                    "summary": a.get("summary", ""),
                })
            df = pd.DataFrame(rows)

            total = len(df)
            approved = (df["verdict"] == "APPROVE").sum()
            review = (df["verdict"] == "REVIEW").sum()
            rejected = (df["verdict"] == "REJECT").sum()

            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Total Audits", total)
            m2.metric("✅ Approved", approved)
            m3.metric("⚠️ Review", review)
            m4.metric("⛔ Rejected", rejected)

            st.markdown("---")

            verdict_filter = st.selectbox("Filter by verdict", ["ALL", "APPROVE", "REVIEW", "REJECT"])
            view = df if verdict_filter == "ALL" else df[df["verdict"] == verdict_filter]

            st.dataframe(
                view[["date", "filename", "verdict", "risk_score", "summary"]],
                use_container_width=True,
                height=320,
            )

            if not view.empty:
                selected = st.selectbox("Inspect audit", options=view["id"].tolist())
                if selected:
                    record = next((a for a in audits if a["id"] == selected), None)
                    if record:
                        st.json(record)
    except Exception as e:
        st.error(f"History failed: {e}")