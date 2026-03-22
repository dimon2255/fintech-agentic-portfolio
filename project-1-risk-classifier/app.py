"""Streamlit demo for the Transaction Risk Classifier.

Run with: streamlit run project-1-risk-classifier/app.py
"""

from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path

# Ensure project is importable
sys.path.insert(0, str(Path(__file__).parent))

import streamlit as st

from src.agent import classify_transaction
from src.data_generator import (
    generate_edge_case_transaction,
    generate_normal_transaction,
    generate_suspicious_transaction,
)
from src.models import RiskLevel, Transaction

# --- Page Config ---
st.set_page_config(
    page_title="Transaction Risk Classifier",
    page_icon="🔍",
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


def run_async(coro):
    """Run async function from sync Streamlit context."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# --- Header ---
st.title("🔍 Transaction Risk Classifier")
st.markdown(
    "Explainable fraud detection powered by LangGraph. "
    "Unlike single-score systems, this agent provides **full reasoning chains** "
    "for every decision — critical for regulatory compliance in fintech."
)

# --- Sidebar ---
with st.sidebar:
    st.header("Generate Transaction")
    txn_type = st.radio(
        "Transaction type:",
        ["Normal", "Suspicious", "Edge Case", "Custom"],
        help="Generate synthetic transactions of different risk profiles",
    )

    if txn_type == "Custom":
        st.subheader("Custom Transaction")
        amount = st.number_input("Amount ($)", min_value=1.0, max_value=50000.0, value=500.0)
        merchant = st.selectbox(
            "Merchant Category",
            ["grocery", "restaurant", "electronics", "jewelry", "gift_cards",
             "travel", "hotel", "airline", "cryptocurrency", "luxury_goods"],
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
if st.button("🔍 Classify Transaction", type="primary", use_container_width=True):
    if txn_type == "Normal":
        txn = generate_normal_transaction()
    elif txn_type == "Suspicious":
        txn = generate_suspicious_transaction()
    elif txn_type == "Edge Case":
        txn = generate_edge_case_transaction()
    else:
        import random
        import uuid
        from datetime import datetime

        ip_map = {
            "73.x.x.x (residential US)": f"73.{random.randint(1,254)}.{random.randint(1,254)}.{random.randint(1,254)}",
            "185.x.x.x (hosting/VPN range)": f"185.{random.randint(1,254)}.{random.randint(1,254)}.{random.randint(1,254)}",
            "104.x.x.x (CDN/cloud)": f"104.{random.randint(1,254)}.{random.randint(1,254)}.{random.randint(1,254)}",
        }
        txn = Transaction(
            transaction_id=f"txn_{uuid.uuid4().hex[:12]}",
            amount=amount,
            merchant_category=merchant,
            customer_id=f"cust_{random.randint(1000, 9999)}",
            customer_email=f"user{random.randint(100,999)}@example.com",
            ip_address=ip_map[ip_prefix],
            device_id=f"dev_{uuid.uuid4().hex[:8]}",
            timestamp=datetime.utcnow(),
            card_last_four=f"{random.randint(1000, 9999)}",
            billing_country=billing_country,
            shipping_country=shipping_country,
        )

    # --- Run Classification ---
    with st.spinner("Running analysis tools in parallel..."):
        start = time.monotonic()
        assessment = run_async(classify_transaction(txn))
        elapsed = time.monotonic() - start

    # --- Results ---
    risk_color = RISK_COLORS[assessment.risk_level]
    risk_icon = RISK_ICONS[assessment.risk_level]

    # Top-level metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Risk Level", f"{risk_icon} {assessment.risk_level.value.upper()}")
    with col2:
        st.metric("Action", assessment.recommended_action.upper())
    with col3:
        st.metric("Confidence", f"{assessment.confidence:.0%}")
    with col4:
        st.metric("Analysis Time", f"{elapsed:.2f}s")

    st.markdown(f"**Summary:** {assessment.summary}")

    # --- Reasoning Chain ---
    st.subheader("Reasoning Chain")
    st.markdown("*Step-by-step analysis — this is what makes this approach auditable*")

    for i, step in enumerate(assessment.reasoning_chain, 1):
        impact_colors = {
            "increases": "🔴",
            "decreases": "🟢",
            "neutral": "⚪",
        }
        icon = impact_colors.get(step.risk_impact, "⚪")

        with st.expander(f"{icon} Step {i}: {step.signal} — risk {step.risk_impact}", expanded=True):
            st.markdown(f"**Observed:** {step.observation}")
            st.markdown(f"**Assessment:** {step.assessment}")

    # --- Transaction Details ---
    col_left, col_right = st.columns(2)

    with col_left:
        st.subheader("Transaction Details")
        st.json({
            "transaction_id": txn.transaction_id,
            "amount": txn.amount,
            "merchant_category": txn.merchant_category,
            "customer_id": txn.customer_id,
            "billing_country": txn.billing_country,
            "shipping_country": txn.shipping_country,
            "ip_address": txn.ip_address,
        })

    with col_right:
        st.subheader("Raw Tool Results")
        tabs = st.tabs(["Velocity", "Geo", "Device"])
        with tabs[0]:
            st.json(assessment.tool_results.velocity.model_dump())
        with tabs[1]:
            st.json(assessment.tool_results.geo.model_dump())
        with tabs[2]:
            st.json(assessment.tool_results.device.model_dump())

    # --- Audit Trail ---
    with st.expander("Full Audit Trail (JSON)"):
        st.json(assessment.model_dump(mode="json"))

# --- Footer ---
st.markdown("---")
st.markdown(
    "*Part of the [Fintech Agentic AI Portfolio](https://github.com/dimon2255/fintech-agentic-portfolio) "
    "— demonstrating explainable fraud detection for enterprise fintech.*"
)
