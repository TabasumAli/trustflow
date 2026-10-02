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
# GLOBAL STYLES
# ============================================================
st.markdown(
    """
    <style>
        .stApp { background: #f7f8fc; }
        section[data-testid="stSidebar"] {
            background: linear-gradient(180deg, #0f172a 0%, #1e293b 100%);
            color: #e2e8f0;
        }
        section[data-testid="stSidebar"] * { color: #e2e8f0 !important; }
        section[data-testid="stSidebar"] input {
            background: #1e293b !important;
            color: #f1f5f9 !important;
        }

        .tf-header {
            background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%);
            padding: 28px 32px;
            border-radius: 16px;
            color: white;
            margin-bottom: 24px;
            box-shadow: 0 8px 24px rgba(79,70,229,0.25);
        }
        .tf-header h1 { margin: 0; font-size: 28px; font-weight: 700; letter-spacing: -0.5px; }
        .tf-header p { margin: 6px 0 0 0; opacity: 0.9; font-size: 14px; }

        .tf-card {
            background: white;
            border-radius: 14px;
            padding: 20px 22px;
            box-shadow: 0 2px 10px rgba(15,23,42,0.05);
            border: 1px solid #e5e7eb;
        }

        .tf-metric-label { color: #64748b; font-size: 12px; font-weight: 500; text-transform: uppercase; letter-spacing: 0.5px; }
        .tf-metric-value { color: #0f172a; font-size: 26px; font-weight: 700; margin-top: 4px; }

        .tf-verdict-card {
            border-radius: 16px;
            padding: 28px 32px;
            margin-bottom: 20px;
            color: white;
            box-shadow: 0 12px 32px rgba(0,0,0,0.12);
        }
        .tf-verdict-approve { background: linear-gradient(135deg, #10b981 0%, #059669 100%); }
        .tf-verdict-review  { background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%); }
        .tf-verdict-reject  { background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%); }
        .tf-verdict-unknown { background: linear-gradient(135deg, #6b7280 0%, #4b5563 100%); }

        .tf-verdict-label { font-size: 12px; opacity: 0.85; letter-spacing: 1.5px; text-transform: uppercase; }
        .tf-verdict-title { font-size: 42px; font-weight: 800; margin: 4px 0 8px 0; letter-spacing: -1px; }
        .tf-verdict-meta { font-size: 14px; opacity: 0.92; }

        .tf-rule-pass { padding: 10px 14px; border-radius: 10px; background: #f0fdf4; border-left: 4px solid #10b981; margin-bottom: 8px; }
        .tf-rule-fail { padding: 10px 14px; border-radius: 10px; background: #fef2f2; border-left: 4px solid #ef4444; margin-bottom: 8px; }
        .tf-rule-name { font-weight: 600; color: #0f172a; font-size: 14px; }
        .tf-rule-meta { font-size: 12px; color: #64748b; margin-left: 8px; }
        .tf-rule-reason { font-size: 13px; color: #b91c1c; margin-top: 4px; }

        .tf-section-title {
            font-size: 18px; font-weight: 700; color: #0f172a;
            margin: 28px 0 12px 0; display: flex; align-items: center; gap: 8px;
        }

        .stButton > button {
            border-radius: 10px;
            font-weight: 600;
            padding: 8px 18px;
            transition: all 0.2s ease;
            border: none;
        }
        .stButton > button[kind="primary"] {
            background: linear-gradient(135deg, #4f46e5, #7c3aed);
            color: white;
            box-shadow: 0 4px 12px rgba(79,70,229,0.3);
        }
        .stButton > button[kind="primary"]:hover {
            transform: translateY(-1px);
            box-shadow: 0 6px 16px rgba(79,70,229,0.4);
        }

        div[data-testid="stMetricValue"] { font-size: 26px; font-weight: 700; color: #0f172a; }
        div[data-testid="stMetricLabel"] { color: #64748b; font-size: 12px; text-transform: uppercase; }
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
            <div style="font-size: 22px; font-weight: 700;">🛡️ TrustFlow</div>
            <div style="font-size: 12px; opacity: 0.75;">AI Invoice Audit</div>
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
        <div style="font-size: 11px; opacity: 0.65; line-height: 1.6;">
            Get a key at <a href="https://console.groq.com/keys" target="_blank" style="color:#a5b4fc;">console.groq.com/keys</a>
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
    h1 = ParagraphStyle("h1", parent=styles["Heading1"], fontSize=20, spaceAfter=10, textColor=colors.HexColor("#4f46e5"))
    h2 = ParagraphStyle("h2", parent=styles["Heading2"], fontSize=13, spaceAfter=6, textColor=colors.HexColor("#1e293b"))
    body = ParagraphStyle("body", parent=styles["BodyText"], fontSize=10, leading=14)
    small = ParagraphStyle("small", parent=styles["BodyText"], fontSize=9, textColor=colors.HexColor("#64748b"))

    story = []
    verdict = result.get("verdict", "UNKNOWN")
    score = result.get("risk_score", 0)
    confidence = result.get("gate", {}).get("confidence", 0.0)
    invoice = result.get("invoice", {}) or {}
    checks = result.get("checks", [])

    # Header
    story.append(Paragraph("🛡️ TrustFlow — Audit Report", h1))
    story.append(Paragraph(f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}", small))
    story.append(Spacer(1, 12))

    # Verdict banner
    verdict_color = {
        "APPROVE": colors.HexColor("#10b981"),
        "REVIEW": colors.HexColor("#f59e0b"),
        "REJECT": colors.HexColor("#ef4444"),
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

    # Invoice details
    story.append(Paragraph("Invoice Details", h2))
    inv_rows = [[Paragraph(f"<b>{k.replace('_',' ').title()}</b>", body), Paragraph(str(v if v not in (None,'') else '—'), body)] for k, v in invoice.items()]
    if inv_rows:
        t = Table(inv_rows, colWidths=[50*mm, 120*mm])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (0,-1), colors.HexColor("#f1f5f9")),
            ("BOX", (0,0), (-1,-1), 0.5, colors.HexColor("#cbd5e1")),
            ("INNERGRID", (0,0), (-1,-1), 0.25, colors.HexColor("#e2e8f0")),
            ("LEFTPADDING", (0,0), (-1,-1), 8),
            ("RIGHTPADDING", (0,0), (-1,-1), 8),
            ("TOPPADDING", (0,0), (-1,-1), 6),
            ("BOTTOMPADDING", (0,0), (-1,-1), 6),
        ]))
        story.append(t)
    story.append(Spacer(1, 14))

    # Summary
    story.append(Paragraph("Summary", h2))
    story.append(Paragraph(result.get("summary", "—"), body))
    story.append(Spacer(1, 8))
    if result.get("next_action"):
        story.append(Paragraph(f"<b>Next action:</b> {result['next_action']}", body))
    if result.get("routing_reason"):
        story.append(Paragraph(f"<i>Routing reason:</i> {result['routing_reason']}", small))
    story.append(Spacer(1, 14))

    # Rule checks
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
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#4f46e5")),
        ("TEXTCOLOR", (0,0), (-1,0), colors.white),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("BOX", (0,0), (-1,-1), 0.5, colors.HexColor("#cbd5e1")),
        ("INNERGRID", (0,0), (-1,-1), 0.25, colors.HexColor("#e2e8f0")),
        ("LEFTPADDING", (0,0), (-1,-1), 6),
        ("RIGHTPADDING", (0,0), (-1,-1), 6),
        ("TOPPADDING", (0,0), (-1,-1), 5),
        ("BOTTOMPADDING", (0,0), (-1,-1), 5),
    ]))
    story.append(t)
    story.append(Spacer(1, 12))

    # Footer
    trace_url = result.get("trace_url")
    if trace_url:
        story.append(Paragraph(f"LangSmith trace: {trace_url}", small))

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()


# ============================================================
# SETUP TAB
# ============================================================
with tab_setup:
    st.markdown('<div class="tf-section-title">⚙️ Setup — Vendors & Rules</div>', unsafe_allow_html=True)
    st.caption("Upload your vendors and rules to Supabase. Manage what's currently stored below.")

    # ---- Danger Zone (top of tab) ----
    with st.expander("🗑️ Database Management", expanded=False):
        st.caption("Remove stored vendors or rules for this organization. Invoices and past audits are not affected.")
        col_d1, col_d2, col_d3 = st.columns(3)
        with col_d1:
            if st.button("🗑️ Delete All Vendors", use_container_width=True):
                try:
                    existing = db.get_vendors(DEMO_ORG_ID)
                    if not existing:
                        st.warning("No vendors found in the database — nothing to delete.")
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
                        st.warning("No rules found in the database — nothing to delete.")
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

    # ---- Upload ----
    col1, col2 = st.columns(2)
    with col1:
        vendors_file = st.file_uploader("📁 vendors.csv", type=["csv"], key="vendors_up")
    with col2:
        rules_file = st.file_uploader("📁 rules.json", type=["json"], key="rules_up")

    if st.button("⬆️ Save to Database", type="primary", use_container_width=False):
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

    # ---- Current Data ----
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

        icon = {"APPROVE": "✅", "REVIEW": "⚠️", "REJECT": "⛔"}.get(verdict, "❔")

        st.markdown(
            f"""
            <div class="tf-verdict-card {verdict_class}">
                <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:12px;">
                    <div>
                        <div class="tf-verdict-label">Audit Verdict</div>
                        <div class="tf-verdict-title">{icon} {verdict}</div>
                        <div class="tf-verdict-meta">
                            <b>{invoice.get('vendor', 'Unknown vendor')}</b> &nbsp;·&nbsp;
                            {invoice.get('invoice_number', '—')} &nbsp;·&nbsp;
                            ${invoice.get('amount', '0')}
                        </div>
                    </div>
                    <div style="text-align:right;">
                        <div class="tf-verdict-label">Risk Score</div>
                        <div class="tf-verdict-title">{score}<span style="font-size:20px;opacity:0.7;">/100</span></div>
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

        # Download PDF
        try:
            pdf_bytes = build_pdf_report(result)
            fname = f"trustflow_report_{invoice.get('invoice_number','audit')}.pdf".replace(" ", "_")
            st.download_button(
                "⬇️ Download PDF Report",
                data=pdf_bytes,
                file_name=fname,
                mime="application/pdf",
                type="primary",
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
                        f"<div style='font-size:16px;font-weight:600;margin-top:4px;color:#0f172a'>{v if v not in (None,'') else '—'}</div>"
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