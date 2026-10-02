import streamlit as st
import pandas as pd

from backend.api import run_audit
from backend import db, tools

DEMO_ORG_ID = "00000000-0000-0000-0000-000000000001"

st.set_page_config(page_title="TrustFlow", page_icon="🛡️", layout="wide")
st.title("🛡️ TrustFlow — Invoice Audit")

tab_setup, tab_audit, tab_history = st.tabs(["⚙️ Setup", "🔍 Audit", "📜 History"])

with tab_setup:
    st.header("Setup — Vendors & Rules")
    st.caption("Upload your vendors and rules. They will be saved to Supabase.")

    col1, col2 = st.columns(2)
    with col1:
        vendors_file = st.file_uploader("vendors.csv", type=["csv"], key="vendors_up")
    with col2:
        rules_file = st.file_uploader("rules.json", type=["json"], key="rules_up")

    if st.button("Save to Database", type="primary"):
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

    st.divider()
    st.subheader("Current Data")

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Vendors**")
        try:
            vendors = db.get_vendors(DEMO_ORG_ID)
            if vendors:
                st.dataframe(pd.DataFrame(vendors), use_container_width=True)
            else:
                st.info("No vendors yet.")
        except Exception as e:
            st.error(f"Fetch failed: {e}")

    with c2:
        st.markdown("**Rules**")
        try:
            rules = db.get_rules(DEMO_ORG_ID)
            if rules:
                st.dataframe(pd.DataFrame(rules), use_container_width=True)
            else:
                st.info("No rules yet.")
        except Exception as e:
            st.error(f"Fetch failed: {e}")


with tab_audit:
    st.header("Run Audit")
    uploaded = st.file_uploader("Invoice (PDF or TXT)", type=["pdf", "txt"], key="invoice_up")

    if st.button("Run Audit", type="primary", disabled=uploaded is None):
        if uploaded:
            with st.spinner("Running audit crew..."):
                try:
                    result = run_audit(uploaded.getvalue(), uploaded.name, DEMO_ORG_ID)
                except Exception as e:
                    st.error(f"Audit failed: {e}")
                    result = None

            if result:
                if "error" in result:
                    st.error(f"Audit error: {result['error']}")
                else:
                    verdict = result.get("verdict", "UNKNOWN")
                    score = result.get("risk_score", 0)
                    confidence = result.get("gate", {}).get("confidence", 0.0)

                    color = {"APPROVE": "green", "REVIEW": "orange", "REJECT": "red"}.get(verdict, "gray")
                    st.markdown(
                        f"""
                        <div style="padding:20px; border-radius:10px; border:2px solid {color};">
                            <h2 style="color:{color}; margin:0;">Verdict: {verdict}</h2>
                            <p style="margin:5px 0 0 0;">
                                <strong>Risk:</strong> {score}/100 |
                                <strong>Confidence:</strong> {confidence*100:.0f}%
                            </p>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

                    st.subheader("Summary")
                    st.write(result.get("summary") or "_No summary._")
                    if result.get("next_action"):
                        st.info(f"**Next action:** {result['next_action']}")

                    c1, c2 = st.columns(2)
                    with c1:
                        st.subheader("Extracted Fields")
                        inv = result.get("invoice", {})
                        if inv:
                            st.dataframe(
                                pd.DataFrame([{"Field": k, "Value": str(v)} for k, v in inv.items()]),
                                use_container_width=True,
                            )
                        else:
                            st.warning("No fields extracted.")
                    with c2:
                        st.subheader("Rule Checks")
                        checks = result.get("checks", [])
                        if checks:
                            st.dataframe(pd.DataFrame(checks), use_container_width=True)
                        else:
                            st.warning("No checks returned.")

                    with st.expander("Full Result"):
                        st.json(result)


with tab_history:
    st.header("Audit History")

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

            verdict_filter = st.selectbox("Filter by verdict", ["ALL", "APPROVE", "REVIEW", "REJECT"])
            view = df if verdict_filter == "ALL" else df[df["verdict"] == verdict_filter]

            st.dataframe(
                view[["date", "filename", "verdict", "risk_score", "summary"]],
                use_container_width=True,
            )

            selected = st.selectbox("Inspect audit", options=view["id"].tolist())
            if selected:
                record = next((a for a in audits if a["id"] == selected), None)
                if record:
                    st.json(record)
    except Exception as e:
        st.error(f"History failed: {e}")