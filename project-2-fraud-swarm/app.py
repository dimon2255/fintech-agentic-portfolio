"""Streamlit demo for the Fraud Detection Swarm.

Run with: streamlit run project-2-fraud-swarm/app.py
"""

from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path

# Ensure project is importable
sys.path.insert(0, str(Path(__file__).parent))

import streamlit as st

from src.graph import analyze_transaction
from src.data_generator import (
    generate_disagreement_trigger,
    generate_edge_case_transaction,
    generate_normal_transaction,
    generate_suspicious_transaction,
)
from src.models import RiskLevel, Transaction

# --- Page Config ---
st.set_page_config(
    page_title="Fraud Detection Swarm",
    page_icon="🐝",
    layout="wide",
)

# --- Styling ---
RISK_COLORS = {
    RiskLevel.LOW: "#51cf66",
    RiskLevel.MEDIUM: "#ffd43b",
    RiskLevel.HIGH: "#ff6b6b",
    RiskLevel.CRITICAL: "#c92a2a",
}

RISK_ICONS = {
    RiskLevel.LOW: "✅",
    RiskLevel.MEDIUM: "⚠️",
    RiskLevel.HIGH: "🚨",
    RiskLevel.CRITICAL: "🔴",
}

ACTION_ICONS = {
    "approve": "✅ Approve",
    "review": "👁️ Review",
    "decline": "🚫 Decline",
}


def run_async(coro):
    """Run async function from sync Streamlit context."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# --- Header ---
st.title("🐝 Fraud Detection Swarm")
st.markdown(
    "Multi-agent fraud detection with **adjudicator debate**. "
    "Three specialist agents independently analyze each transaction, then an "
    "adjudicator identifies disagreement and synthesizes a final verdict — "
    "surfacing blind spots that any single model would miss."
)

# --- Sidebar ---
with st.sidebar:
    st.header("Generate Transaction")
    txn_type = st.radio(
        "Transaction type:",
        ["Normal", "Suspicious", "Edge Case", "Disagreement Trigger", "Custom"],
        help="Generate synthetic transactions of different risk profiles. "
             "'Disagreement Trigger' forces agents to disagree — the star scenario.",
    )

    if txn_type == "Custom":
        st.subheader("Custom Transaction")
        amount = st.number_input("Amount ($)", min_value=1.0, max_value=50000.0, value=500.0)
        merchant = st.selectbox(
            "Merchant Category",
            ["grocery", "restaurant", "electronics", "jewelry", "gift_cards",
             "travel", "hotel", "airline", "cryptocurrency", "luxury_goods"],
        )
        email_domain = st.selectbox(
            "Email Domain (identity signal)",
            ["example.com (neutral)", "company.com (trusted)", "tempmail.com (disposable)"],
        )
        billing_country = st.selectbox("Billing Country", ["US", "GB", "DE", "BR", "NG", "RU", "CN"])
        shipping_country = st.selectbox("Shipping Country", ["US", "GB", "DE", "BR", "NG", "RU", "CN", "JP"])
        ip_prefix = st.selectbox(
            "IP Range (risk signal)",
            ["73.x.x.x (residential US)", "185.x.x.x (hosting/VPN range)", "104.x.x.x (CDN/cloud)"],
        )

    st.markdown("---")
    st.markdown(
        "**Mode:** Mock LLM (deterministic)  \n"
        "Add an API key in `.env` to use real LLM reasoning."
    )

# --- Generate Transaction ---
if st.button("🐝 Analyze with Swarm", type="primary", use_container_width=True):
    if txn_type == "Normal":
        txn = generate_normal_transaction()
    elif txn_type == "Suspicious":
        txn = generate_suspicious_transaction()
    elif txn_type == "Edge Case":
        txn = generate_edge_case_transaction()
    elif txn_type == "Disagreement Trigger":
        txn = generate_disagreement_trigger()
    else:
        import random
        import uuid
        from datetime import datetime

        ip_map = {
            "73.x.x.x (residential US)": f"73.{random.randint(1,254)}.{random.randint(1,254)}.{random.randint(1,254)}",
            "185.x.x.x (hosting/VPN range)": f"185.{random.randint(1,254)}.{random.randint(1,254)}.{random.randint(1,254)}",
            "104.x.x.x (CDN/cloud)": f"104.{random.randint(1,254)}.{random.randint(1,254)}.{random.randint(1,254)}",
        }
        domain_map = {
            "example.com (neutral)": "example.com",
            "company.com (trusted)": "company.com",
            "tempmail.com (disposable)": "tempmail.com",
        }
        txn = Transaction(
            transaction_id=f"txn_{uuid.uuid4().hex[:12]}",
            amount=amount,
            merchant_category=merchant,
            customer_id=f"cust_{random.randint(1000, 9999)}",
            customer_email=f"user{random.randint(100,999)}@{domain_map[email_domain]}",
            ip_address=ip_map[ip_prefix],
            device_id=f"dev_{uuid.uuid4().hex[:8]}",
            timestamp=datetime.utcnow(),
            card_last_four=f"{random.randint(1000, 9999)}",
            billing_country=billing_country,
            shipping_country=shipping_country,
        )

    # --- Run Swarm ---
    with st.spinner("Running 3-agent swarm analysis..."):
        start = time.monotonic()
        result = run_async(analyze_transaction(txn))
        elapsed = time.monotonic() - start

    # --- Extract Results ---
    assessment = result["final_assessment"]
    velocity_v = result["velocity_verdict"]
    identity_v = result["identity_verdict"]
    behavioral_v = result["behavioral_verdict"]
    debate = result["debate_analysis"]

    risk_color = RISK_COLORS[assessment.risk_level]
    risk_icon = RISK_ICONS[assessment.risk_level]

    # --- Top-Level Metrics ---
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Risk Level", f"{risk_icon} {assessment.risk_level.value.upper()}")
    with col2:
        st.metric("Action", ACTION_ICONS.get(assessment.recommended_action, assessment.recommended_action))
    with col3:
        st.metric("Agreement", f"{debate.agreement_score:.0%}")
    with col4:
        st.metric("Analysis Time", f"{elapsed:.2f}s")

    st.markdown(f"**Summary:** {assessment.summary}")

    # --- Specialist Verdicts (Side-by-Side) ---
    st.subheader("Specialist Agent Verdicts")
    st.markdown("*Each agent independently analyzes the transaction from its area of expertise*")

    verdicts = [
        ("🏎️ Velocity", velocity_v),
        ("🪪 Identity", identity_v),
        ("🧠 Behavioral", behavioral_v),
    ]

    vcol1, vcol2, vcol3 = st.columns(3)
    for col, (label, verdict) in zip([vcol1, vcol2, vcol3], verdicts):
        v_icon = RISK_ICONS[verdict.risk_level]
        v_color = RISK_COLORS[verdict.risk_level]

        with col:
            st.markdown(
                f"### {label}\n"
                f"**{v_icon} {verdict.risk_level.value.upper()}** &nbsp; "
                f"Score: `{verdict.risk_score:.3f}` &nbsp; "
                f"Confidence: `{verdict.confidence:.0%}`"
            )
            st.markdown(f"Action: **{verdict.recommended_action}**")

            if verdict.key_findings:
                st.markdown("**Key Findings:**")
                for finding in verdict.key_findings:
                    st.markdown(f"- {finding}")

            with st.expander("Reasoning Chain"):
                for i, step in enumerate(verdict.reasoning_chain, 1):
                    impact_icons = {"increases": "🔴", "decreases": "🟢", "neutral": "⚪"}
                    icon = impact_icons.get(step.risk_impact, "⚪")
                    st.markdown(
                        f"**{icon} {i}. {step.signal}** — risk {step.risk_impact}\n\n"
                        f"*Observed:* {step.observation}\n\n"
                        f"*Assessment:* {step.assessment}"
                    )
                    if i < len(verdict.reasoning_chain):
                        st.markdown("---")

    # --- Adjudicator Debate ---
    st.subheader("Adjudicator Debate Analysis")

    if debate.agreement_score >= 0.8:
        st.success(f"**High agreement** ({debate.agreement_score:.0%}) — specialists largely concur.")
    elif debate.agreement_score >= 0.5:
        st.warning(f"**Partial agreement** ({debate.agreement_score:.0%}) — some disagreement detected.")
    else:
        st.error(f"**Low agreement** ({debate.agreement_score:.0%}) — significant specialist disagreement.")

    dcol1, dcol2 = st.columns(2)
    with dcol1:
        st.markdown(f"**Agreeing agents:** {', '.join(debate.agreeing_agents) or 'none'}")
        st.markdown(f"**Dissenting agents:** {', '.join(debate.dissenting_agents) or 'none'}")
        st.markdown(f"**Confidence adjustment:** `{debate.confidence_adjustment:+.2f}`")
    with dcol2:
        if debate.points_of_contention:
            st.markdown("**Points of Contention:**")
            for point in debate.points_of_contention:
                st.markdown(f"- {point}")
        else:
            st.markdown("**No points of contention** — unanimous assessment.")

    st.info(f"**Resolution:** {debate.resolution_reasoning}")

    # --- Transaction Details + Raw Tool Results ---
    col_left, col_right = st.columns(2)

    with col_left:
        st.subheader("Transaction Details")
        st.json({
            "transaction_id": txn.transaction_id,
            "amount": txn.amount,
            "merchant_category": txn.merchant_category,
            "customer_id": txn.customer_id,
            "customer_email": txn.customer_email,
            "billing_country": txn.billing_country,
            "shipping_country": txn.shipping_country,
            "ip_address": txn.ip_address,
        })

    with col_right:
        st.subheader("Raw Tool Results")
        tabs = st.tabs(["Velocity", "Geo", "Device", "Identity", "Behavioral"])
        with tabs[0]:
            st.json(assessment.tool_results.velocity.model_dump())
        with tabs[1]:
            st.json(assessment.tool_results.geo.model_dump())
        with tabs[2]:
            st.json(assessment.tool_results.device.model_dump())
        with tabs[3]:
            st.json(assessment.identity_signals.model_dump())
        with tabs[4]:
            st.json(assessment.behavioral_signals.model_dump())

    # --- Audit Trail ---
    with st.expander("Full Audit Trail (JSON)"):
        st.json(assessment.model_dump(mode="json"))

# --- Footer ---
st.markdown("---")
st.markdown(
    "*Part of the [Fintech Agentic AI Portfolio](https://github.com/dimon2255/fintech-agentic-portfolio) "
    "— Project 2: multi-agent debate for fraud detection.*"
)
