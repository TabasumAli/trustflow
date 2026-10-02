import streamlit as st
from backend.api import run_audit

st.set_page_config(page_title="TrustFlow", page_icon="🧾", layout="wide")

st.title("🧾 TrustFlow — Invoice Audit")
st.caption("Upload an invoice and let the crew audit it.")

uploaded = st.file_uploader("Upload invoice", type=["pdf", "txt"])

run = st.button("Run audit", type="primary", disabled=uploaded is None)

if run and uploaded is not None:
    with st.spinner("Running audit crew..."):
        result = run_audit(uploaded.read(), uploaded.name)

    if "error" in result:
        st.error(f"Audit failed: {result['error']}")
        st.stop()

    verdict = result.get("verdict", "UNKNOWN")
    score = result.get("risk_score", 0)
    summary = result.get("summary", "")
    next_action = result.get("next_action", "")
    routing_reason = result.get("routing_reason", "")
    gate = result.get("gate", {})

    colors = {"APPROVE": "🟢", "REVIEW": "🟡", "REJECT": "🔴"}
    icon = colors.get(verdict, "⚪")

    col1, col2, col3 = st.columns(3)
    col1.metric("Verdict", f"{icon} {verdict}")
    col2.metric("Risk Score", f"{score}/100")
    col3.metric("Confidence", f"{gate.get('confidence', 0.0):.2f}")

    st.divider()

    st.subheader("Summary")
    st.write(summary or "_No summary produced._")
    if next_action:
        st.info(f"**Next action:** {next_action}")
    if routing_reason:
        st.caption(f"Routing reason: {routing_reason}")

    st.divider()

    st.subheader("Extracted Invoice")
    inv = result.get("invoice", {})
    if inv:
        st.table(inv)
    else:
        st.warning("No invoice fields extracted (Joti's agents may be stubbed).")

    st.divider()

    st.subheader("Rule Checks")
    checks = result.get("checks", [])
    if checks:
        for c in checks:
            status = c.get("status", "?")
            dot = "✅" if status == "pass" else "❌"
            sev = c.get("severity", "")
            rule = c.get("rule", "")
            desc = c.get("description", "")
            reason = c.get("reason", "")
            label = f"{dot} **{rule}** — {desc} _(severity: {sev})_"
            if status == "fail" and reason:
                st.markdown(f"{label}<br><span style='color:#c0392b;font-size:0.9em'>{reason}</span>", unsafe_allow_html=True)
            else:
                st.markdown(label)
    else:
        st.warning("No checks returned.")

    st.divider()

    with st.expander("Gate details"):
        st.json(gate)

    with st.expander("Full raw result"):
        st.json(result)