"""Streamlit dashboard for the KYC/AML Compliance Platform.

Walkthrough-quality demo with:
- Real-time pipeline status with st.status() progress
- Color-coded compliance checklist (the hero visual)
- Supervisor routing trail
- Agent detail tabs with reasoning chains
- Expandable audit trail

Run with: streamlit run project-3-kyc-platform/app.py
"""

from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path

# Ensure project is importable
sys.path.insert(0, str(Path(__file__).parent))

import streamlit as st

from src.graph import run_kyc_application
from src.data_generator import (
    generate_borderline_application,
    generate_clean_application,
    generate_document_issues_application,
    generate_high_risk_application,
    generate_sanctions_hit_application,
)
from src.models import RiskTier


# --- Page Config ---
st.set_page_config(
    page_title="KYC/AML Compliance Platform",
    page_icon="🛡️",
    layout="wide",
)

# --- Constants ---
RISK_COLORS = {
    RiskTier.LOW: "#51cf66",
    RiskTier.MEDIUM: "#ffd43b",
    RiskTier.HIGH: "#ff6b6b",
    RiskTier.PROHIBITED: "#c92a2a",
}

DECISION_COLORS = {
    "approved": "#51cf66",
    "rejected": "#c92a2a",
    "escalated": "#ffd43b",
}

DECISION_ICONS = {
    "approved": "✅",
    "rejected": "🚫",
    "escalated": "⚠️",
}

RISK_ICONS = {
    RiskTier.LOW: "🟢",
    RiskTier.MEDIUM: "🟡",
    RiskTier.HIGH: "🔴",
    RiskTier.PROHIBITED: "⛔",
}

CHECKLIST_STATUS = {
    "completed": ("✅", "#51cf66"),
    "skipped": ("⏭️", "#868e96"),
    "pending": ("⏳", "#ffd43b"),
    "failed": ("❌", "#ff6b6b"),
}

STEP_LABELS = {
    "document_intake": "Document Intake",
    "identity_verification": "Identity Verification",
    "sanctions_screening": "Sanctions Screening",
    "risk_assessment": "Risk Assessment",
}


def run_async(coro):
    """Run async function from sync Streamlit context."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# --- Header ---
st.title("🛡️ KYC/AML Compliance Platform")
st.markdown(
    "Supervisor-orchestrated KYC/AML compliance pipeline with **conditional routing**, "
    "skip logic, and human-in-the-loop escalation. Four specialist agents coordinate "
    "through a dynamic supervisor — the capstone of the agentic AI portfolio."
)

# --- Sidebar ---
with st.sidebar:
    st.header("KYC Application")
    app_type = st.radio(
        "Application profile:",
        [
            "Clean (US Individual)",
            "High-Risk (PEP + Crypto)",
            "Sanctions Hit (Name Match)",
            "Document Issues (Expired + Mismatch)",
            "Borderline (Ambiguous)",
        ],
        help="Each profile exercises different supervisor routing paths.",
    )

    st.divider()

    st.markdown(
        "**Architecture:** Supervisor hub-and-spoke  \n"
        "**Routing:** LangGraph `add_conditional_edges`  \n"
        "**Mode:** Mock LLM (deterministic)  \n\n"
        "*Add an API key in `.env` for live LLM reasoning.*"
    )

# --- Generate Application ---
generators = {
    "Clean (US Individual)": generate_clean_application,
    "High-Risk (PEP + Crypto)": generate_high_risk_application,
    "Sanctions Hit (Name Match)": generate_sanctions_hit_application,
    "Document Issues (Expired + Mismatch)": generate_document_issues_application,
    "Borderline (Ambiguous)": generate_borderline_application,
}

if st.button("🛡️ Run Compliance Check", type="primary", use_container_width=True):
    app = generators[app_type]()

    # --- Application Summary Card ---
    with st.container():
        st.subheader("Application Details")
        acol1, acol2, acol3 = st.columns(3)
        with acol1:
            st.markdown(f"**Applicant:** {app.applicant_name}")
            st.markdown(f"**DOB:** {app.date_of_birth}")
            st.markdown(f"**Email:** {app.email}")
        with acol2:
            st.markdown(f"**Nationality:** {app.nationality}")
            st.markdown(f"**Residence:** {app.country_of_residence}")
            st.markdown(f"**Source of Funds:** {app.source_of_funds}")
        with acol3:
            st.markdown(f"**Business:** {app.business_type or 'Individual'}")
            st.markdown(f"**Industry:** {app.industry or 'N/A'}")
            st.markdown(f"**Expected Volume:** ${app.expected_monthly_volume or 0:,.0f}/month")
        st.markdown(f"**Documents:** {', '.join(d.document_type.value for d in app.documents_submitted)}")

    st.divider()

    # --- Run Pipeline with Status Updates ---
    with st.status("Running KYC/AML compliance pipeline...", expanded=True) as status:
        st.write("🚀 Initializing supervisor...")
        start = time.monotonic()

        result = run_async(run_kyc_application(app))

        elapsed = time.monotonic() - start
        decision = result["compliance_decision"]

        st.write(f"✅ Pipeline complete in {elapsed:.2f}s")
        status.update(
            label=f"Pipeline complete — {decision.decision.upper()}",
            state="complete",
        )

    # --- Decision Banner ---
    d_color = DECISION_COLORS.get(decision.decision, "#868e96")
    d_icon = DECISION_ICONS.get(decision.decision, "❓")
    r_icon = RISK_ICONS.get(decision.risk_tier, "❓")

    st.markdown(
        f"""<div style="background-color: {d_color}20; border-left: 4px solid {d_color};
        padding: 1rem; border-radius: 0.5rem; margin: 1rem 0;">
        <h2 style="margin:0">{d_icon} {decision.decision.upper()}</h2>
        <p style="margin:0.5rem 0 0 0">{decision.reasoning}</p>
        </div>""",
        unsafe_allow_html=True,
    )

    mcol1, mcol2, mcol3, mcol4 = st.columns(4)
    with mcol1:
        st.metric("Decision", f"{d_icon} {decision.decision.upper()}")
    with mcol2:
        st.metric("Risk Tier", f"{r_icon} {decision.risk_tier.value.upper()}")
    with mcol3:
        steps_done = sum(
            1 for s in ["document_intake", "identity_verification", "sanctions_screening", "risk_assessment"]
            if getattr(decision.checklist, s) == "completed"
        )
        st.metric("Steps Completed", f"{steps_done}/4")
    with mcol4:
        st.metric("Processing Time", f"{elapsed:.2f}s")

    if decision.conditions:
        st.info("**Conditions:** " + " | ".join(decision.conditions))

    st.divider()

    # --- Compliance Checklist (THE HERO VISUAL) ---
    st.subheader("📋 Compliance Checklist")
    st.markdown("*Supervisor tracks each step — completed, skipped, or pending*")

    checklist_cols = st.columns(4)
    for i, (step_key, step_label) in enumerate(STEP_LABELS.items()):
        status_val = getattr(decision.checklist, step_key, "pending")
        icon, color = CHECKLIST_STATUS.get(status_val, ("❓", "#868e96"))
        ts = decision.checklist.completed_at.get(step_key, "")

        with checklist_cols[i]:
            st.markdown(
                f"""<div style="background-color: {color}15; border: 2px solid {color};
                padding: 1rem; border-radius: 0.75rem; text-align: center; min-height: 120px;">
                <h1 style="margin:0; font-size: 2rem;">{icon}</h1>
                <p style="margin: 0.5rem 0 0 0; font-weight: bold;">{step_label}</p>
                <p style="margin: 0.25rem 0 0 0; color: {color}; font-size: 0.9rem;">{status_val.upper()}</p>
                </div>""",
                unsafe_allow_html=True,
            )

    st.divider()

    # --- Supervisor Routing Trail ---
    st.subheader("🧭 Supervisor Routing Trail")
    st.markdown("*The supervisor makes a routing decision after each step*")

    for i, sd in enumerate(decision.supervisor_decisions, 1):
        target = sd.next_step.replace("_", " ").title()
        if sd.next_step == "final_decision":
            trail_icon = "🏁"
        elif sd.next_step == "human_review":
            trail_icon = "👤"
        else:
            trail_icon = "➡️"

        with st.container():
            st.markdown(
                f"**{trail_icon} Step {i}:** Supervisor → **{target}**"
            )
            st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;_{sd.reasoning}_")
            if sd.skipped_steps:
                for skip in sd.skipped_steps:
                    st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;⏭️ *Skipped: {skip}*")
            if sd.risk_flags_so_far:
                flags = ", ".join(sd.risk_flags_so_far)
                st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;🚩 Flags: {flags}")

    st.divider()

    # --- Agent Detail Tabs ---
    st.subheader("🔍 Agent Details")

    tab_labels = []
    tab_data = []

    if decision.document_intake_result:
        tab_labels.append("📄 Document Intake")
        tab_data.append(("doc", decision.document_intake_result))
    if decision.identity_verification_result:
        tab_labels.append("🪪 Identity Verification")
        tab_data.append(("identity", decision.identity_verification_result))
    if decision.sanctions_screening_result:
        tab_labels.append("🔒 Sanctions Screening")
        tab_data.append(("sanctions", decision.sanctions_screening_result))
    if decision.risk_assessment_result:
        tab_labels.append("📊 Risk Assessment")
        tab_data.append(("risk", decision.risk_assessment_result))

    if tab_labels:
        tabs = st.tabs(tab_labels)

        for tab, (agent_type, agent_result) in zip(tabs, tab_data):
            with tab:
                # Key findings
                if agent_type == "doc":
                    r = agent_result
                    st.metric("Document Quality", f"{r.overall_document_quality:.0%}")
                    if r.issues_found:
                        st.warning("**Issues Found:**")
                        for issue in r.issues_found:
                            st.markdown(f"- {issue}")
                    else:
                        st.success("No document issues found.")

                elif agent_type == "identity":
                    r = agent_result
                    icol1, icol2 = st.columns(2)
                    with icol1:
                        if r.identity_confirmed:
                            st.success(f"Identity **CONFIRMED** (confidence: {r.confidence:.0%})")
                        else:
                            st.error(f"Identity **NOT CONFIRMED** (confidence: {r.confidence:.0%})")
                    with icol2:
                        if r.pep_check.is_pep:
                            st.warning(f"PEP: {r.pep_check.pep_tier} (confidence: {r.pep_check.match_confidence:.0%})")
                        else:
                            st.success("Not a PEP")

                    st.markdown(f"**Name Match:** {r.name_match.match_score:.0%} ({r.name_match.match_method})")
                    st.markdown(f"**Address:** {r.address_verify.match_status}")
                    st.markdown(f"**DOB:** {'Match ✅' if r.dob_crosscheck.match else 'No match ❌'} (age: {r.dob_crosscheck.age_years})")

                    if r.discrepancies:
                        st.warning("**Discrepancies:**")
                        for d in r.discrepancies:
                            st.markdown(f"- {d}")

                elif agent_type == "sanctions":
                    r = agent_result
                    if r.any_hits:
                        st.error(f"**SANCTIONS HITS FOUND** — highest match: {r.highest_match_score:.0%}")
                        for screen_name, screen_result in [
                            ("OFAC SDN", r.ofac_result),
                            ("EU Consolidated", r.eu_result),
                            ("UN Consolidated", r.un_result),
                        ]:
                            if not screen_result.is_clear:
                                for hit in screen_result.hits:
                                    st.markdown(
                                        f"- **{screen_name}**: '{hit.matched_name}' "
                                        f"(score: {hit.match_score:.0%}, program: {hit.program})"
                                    )
                    else:
                        st.success("Clear on all sanctions lists.")

                    media = r.adverse_media
                    if media.highest_severity != "none":
                        st.warning(
                            f"**Adverse Media:** {media.articles_found} articles, "
                            f"severity: {media.highest_severity}"
                        )
                        st.markdown(f"_{media.summary}_")
                    else:
                        st.success("No adverse media found.")

                elif agent_type == "risk":
                    r = agent_result
                    r_color = RISK_COLORS.get(r.risk_tier, "#868e96")
                    st.markdown(
                        f"**Risk Tier:** <span style='color:{r_color}; font-weight:bold'>"
                        f"{r.risk_tier.value.upper()}</span> &nbsp; "
                        f"Composite Score: `{r.overall_risk.composite_score:.3f}`",
                        unsafe_allow_html=True,
                    )
                    if r.edd_recommended:
                        st.warning("Enhanced Due Diligence recommended")

                    st.markdown("**Factor Breakdown:**")
                    for factor, score in r.overall_risk.factor_breakdown.items():
                        bar_width = int(score * 200)
                        st.markdown(
                            f"<div style='display:flex;align-items:center;margin:0.25rem 0'>"
                            f"<span style='width:180px;font-size:0.85rem'>{factor.replace('_', ' ').title()}</span>"
                            f"<div style='background:#e9ecef;border-radius:4px;width:200px;height:16px'>"
                            f"<div style='background:{r_color};border-radius:4px;width:{bar_width}px;height:16px'></div>"
                            f"</div>"
                            f"<span style='margin-left:8px;font-size:0.85rem'>{score:.4f}</span>"
                            f"</div>",
                            unsafe_allow_html=True,
                        )

                    st.markdown(f"**Country:** {r.country_risk.country_code} — {r.country_risk.risk_tier} (FATF: {r.country_risk.fatf_status})")
                    st.markdown(f"**Industry:** {r.industry_risk.industry} — {r.industry_risk.risk_tier}")
                    st.markdown(f"**Volume:** ${r.transaction_pattern.expected_monthly_volume:,.0f}/month — {r.transaction_pattern.risk_tier}")

                # Reasoning chain (all agents)
                with st.expander("Reasoning Chain"):
                    for j, step in enumerate(agent_result.reasoning_chain, 1):
                        impact_icons = {"increases": "🔴", "decreases": "🟢", "neutral": "⚪"}
                        icon = impact_icons.get(step.risk_impact, "⚪")
                        st.markdown(
                            f"**{icon} {j}. {step.signal}** — risk {step.risk_impact}\n\n"
                            f"*Observed:* {step.observation}\n\n"
                            f"*Assessment:* {step.assessment}"
                        )
                        if j < len(agent_result.reasoning_chain):
                            st.markdown("---")

                # Raw tool results
                with st.expander("Raw Data (JSON)"):
                    st.json(agent_result.model_dump(mode="json"))

    st.divider()

    # --- Audit Trail ---
    st.subheader("📜 Audit Trail")

    with st.expander(f"View all {len(decision.audit_trail)} audit entries", expanded=False):
        for entry in decision.audit_trail:
            action_colors = {
                "started": "🔵",
                "completed": "🟢",
                "skipped": "⏭️",
                "routing": "🧭",
                "escalated": "🔴",
                "reviewed": "👤",
                "approved": "✅",
                "rejected": "🚫",
            }
            a_icon = action_colors.get(entry.action, "⚪")
            st.markdown(
                f"{a_icon} **{entry.step}** — {entry.action}  \n"
                f"&nbsp;&nbsp;&nbsp;&nbsp;{entry.details}  \n"
                f"&nbsp;&nbsp;&nbsp;&nbsp;*{entry.timestamp}*"
            )

    # --- Full JSON ---
    with st.expander("Full Compliance Decision (JSON)"):
        st.json(decision.model_dump(mode="json"))

# --- Footer ---
st.markdown("---")
st.markdown(
    "*Part of the [Fintech Agentic AI Portfolio](https://github.com/dimon2255/fintech-agentic-portfolio) "
    "— Project 3: supervisor-orchestrated KYC/AML compliance.*"
)
