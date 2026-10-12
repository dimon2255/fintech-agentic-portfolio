"""LangGraph graph definition for the KYC/AML Compliance Platform.

Project 3 topology — supervisor hub-and-spoke with conditional routing:

    START → supervisor ──[conditional]──→ document_intake ──→ supervisor
                        ├──→ identity_verification ──→ supervisor
                        ├──→ sanctions_screening ──→ supervisor
                        ├──→ risk_assessment ──→ supervisor
                        ├──→ human_review ──→ final_decision ──→ END
                        └──→ final_decision ──→ END

Key architectural feature: add_conditional_edges
    Unlike P1 (static linear) and P2 (static fan-out), P3 uses LangGraph's
    conditional routing. The supervisor runs after each agent, examines the
    state, and dynamically decides the next step — enabling escalation
    and dependency-ordered execution. Sanctions screening is never skipped.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from langgraph.graph import END, START, StateGraph

from .models import (
    AuditEntry,
    ComplianceChecklist,
    ComplianceDecision,
    KYCApplication,
    KYCState,
    RiskTier,
)
from .supervisor import supervisor_node
from .agents.document_intake import document_intake_node
from .agents.identity_verification import identity_verification_node
from .agents.sanctions_screening import sanctions_screening_node
from .agents.risk_assessment import risk_assessment_node

load_dotenv(Path(__file__).resolve().parent.parent / ".env")


# ============================================================
# Routing function (reads supervisor's latest decision)
# ============================================================

def route_from_supervisor(state: KYCState) -> str:
    """Read the supervisor's latest decision and return the next node name."""
    decisions = state.get("supervisor_decisions", [])
    if not decisions:
        return "document_intake"
    return decisions[-1].next_step


# ============================================================
# Wrapper nodes that update checklist on entry/exit
# ============================================================

async def document_intake_wrapper(state: KYCState) -> dict:
    """Run Document Intake agent and update checklist."""
    checklist = state.get("checklist") or ComplianceChecklist()
    audit_trail = list(state.get("audit_trail", []))
    now = datetime.now(timezone.utc).isoformat()

    audit_trail.append(AuditEntry(
        timestamp=now, step="document_intake", action="started",
        details="Document Intake agent started processing",
        agent_name="document_intake",
    ))

    result = await document_intake_node(state)

    checklist = checklist.model_copy(update={"document_intake": "completed"})
    checklist.completed_at["document_intake"] = now

    audit_trail.append(AuditEntry(
        timestamp=datetime.now(timezone.utc).isoformat(),
        step="document_intake", action="completed",
        details=f"Processed {result['document_intake_result'].documents_processed} documents, quality: {result['document_intake_result'].overall_document_quality:.0%}",
        agent_name="document_intake",
    ))

    return {**result, "checklist": checklist, "audit_trail": audit_trail}


async def identity_verification_wrapper(state: KYCState) -> dict:
    """Run Identity Verification agent and update checklist."""
    checklist = state.get("checklist") or ComplianceChecklist()
    audit_trail = list(state.get("audit_trail", []))
    now = datetime.now(timezone.utc).isoformat()

    audit_trail.append(AuditEntry(
        timestamp=now, step="identity_verification", action="started",
        details="Identity Verification agent started processing",
        agent_name="identity_verification",
    ))

    result = await identity_verification_node(state)

    checklist = checklist.model_copy(update={"identity_verification": "completed"})
    checklist.completed_at["identity_verification"] = now
    iv = result["identity_verification_result"]

    audit_trail.append(AuditEntry(
        timestamp=datetime.now(timezone.utc).isoformat(),
        step="identity_verification", action="completed",
        details=f"Identity {'confirmed' if iv.identity_confirmed else 'NOT confirmed'} (confidence: {iv.confidence:.0%})",
        agent_name="identity_verification",
    ))

    return {**result, "checklist": checklist, "audit_trail": audit_trail}


async def sanctions_screening_wrapper(state: KYCState) -> dict:
    """Run Sanctions Screening agent and update checklist."""
    checklist = state.get("checklist") or ComplianceChecklist()
    audit_trail = list(state.get("audit_trail", []))
    now = datetime.now(timezone.utc).isoformat()

    audit_trail.append(AuditEntry(
        timestamp=now, step="sanctions_screening", action="started",
        details="Sanctions Screening agent started processing",
        agent_name="sanctions_screening",
    ))

    result = await sanctions_screening_node(state)

    checklist = checklist.model_copy(update={"sanctions_screening": "completed"})
    checklist.completed_at["sanctions_screening"] = now
    ss = result["sanctions_screening_result"]

    status = f"{'HITS FOUND (score: ' + str(ss.highest_match_score) + ')' if ss.any_hits else 'Clear — no hits'}"
    audit_trail.append(AuditEntry(
        timestamp=datetime.now(timezone.utc).isoformat(),
        step="sanctions_screening", action="completed",
        details=f"Sanctions screening: {status}",
        agent_name="sanctions_screening",
    ))

    return {**result, "checklist": checklist, "audit_trail": audit_trail}


async def risk_assessment_wrapper(state: KYCState) -> dict:
    """Run Risk Assessment agent and update checklist."""
    checklist = state.get("checklist") or ComplianceChecklist()
    audit_trail = list(state.get("audit_trail", []))
    now = datetime.now(timezone.utc).isoformat()

    audit_trail.append(AuditEntry(
        timestamp=now, step="risk_assessment", action="started",
        details="Risk Assessment agent started processing",
        agent_name="risk_assessment",
    ))

    result = await risk_assessment_node(state)

    checklist = checklist.model_copy(update={"risk_assessment": "completed"})
    checklist.completed_at["risk_assessment"] = now
    ra = result["risk_assessment_result"]

    audit_trail.append(AuditEntry(
        timestamp=datetime.now(timezone.utc).isoformat(),
        step="risk_assessment", action="completed",
        details=f"Risk tier: {ra.risk_tier.value}, EDD: {'yes' if ra.edd_recommended else 'no'}",
        agent_name="risk_assessment",
    ))

    return {**result, "checklist": checklist, "audit_trail": audit_trail}


# ============================================================
# Human review node
# ============================================================

async def human_review_node(state: KYCState) -> dict:
    """Simulates human review for escalated cases.

    In production, this would use LangGraph interrupt() for true HITL.
    For the demo, it auto-resolves based on the escalation context.
    """
    audit_trail = list(state.get("audit_trail", []))
    now = datetime.now(timezone.utc).isoformat()

    # Build escalation context from the last supervisor decision
    decisions = state.get("supervisor_decisions", [])
    reason = decisions[-1].reasoning if decisions else "Unknown escalation reason"

    audit_trail.append(AuditEntry(
        timestamp=now,
        step="human_review",
        action="escalated",
        details=f"Case escalated to human reviewer. Reason: {reason}",
        agent_name="human_review",
    ))

    # Simulate human review decision
    audit_trail.append(AuditEntry(
        timestamp=datetime.now(timezone.utc).isoformat(),
        step="human_review",
        action="reviewed",
        details="Human reviewer examined the case and documented findings.",
        agent_name="human_reviewer",
    ))

    return {"audit_trail": audit_trail}


# ============================================================
# Final decision node
# ============================================================

async def final_decision_node(state: KYCState) -> dict:
    """Compile all agent results into the final compliance decision."""
    application = state["application"]
    checklist = state.get("checklist") or ComplianceChecklist()
    audit_trail = list(state.get("audit_trail", []))

    doc_result = state.get("document_intake_result")
    identity_result = state.get("identity_verification_result")
    sanctions_result = state.get("sanctions_screening_result")
    risk_result = state.get("risk_assessment_result")

    # Determine decision
    was_escalated = any(
        e.action == "escalated" for e in audit_trail
    )

    conditions: list[str] = []
    reasoning_parts: list[str] = []

    # Decision logic
    if sanctions_result and sanctions_result.any_hits and sanctions_result.highest_match_score > 0.8:
        decision = "rejected"
        risk_tier = RiskTier.PROHIBITED
        reasoning_parts.append(f"Strong sanctions match detected (score: {sanctions_result.highest_match_score})")
    elif risk_result and risk_result.risk_tier == RiskTier.PROHIBITED:
        decision = "rejected"
        risk_tier = RiskTier.PROHIBITED
        reasoning_parts.append("Composite risk score exceeds prohibited threshold")
    elif identity_result and not identity_result.identity_confirmed:
        decision = "escalated"
        risk_tier = RiskTier.HIGH
        reasoning_parts.append("Applicant identity could not be confirmed")
    elif was_escalated:
        decision = "escalated"
        risk_tier = RiskTier.HIGH
        reasoning_parts.append("Case was escalated during processing")
    elif risk_result and risk_result.risk_tier == RiskTier.HIGH:
        decision = "approved"
        risk_tier = RiskTier.HIGH
        reasoning_parts.append("High risk — approved with Enhanced Due Diligence")
        conditions.append("Enhanced Due Diligence required")
        conditions.append("Quarterly review scheduled")
        if risk_result.edd_recommended:
            conditions.append("Enhanced transaction monitoring")
    elif risk_result and risk_result.risk_tier == RiskTier.MEDIUM:
        decision = "approved"
        risk_tier = RiskTier.MEDIUM
        reasoning_parts.append("Medium risk — approved with standard monitoring")
        conditions.append("Annual review required")
    else:
        decision = "approved"
        risk_tier = RiskTier.LOW
        reasoning_parts.append("Low risk — standard onboarding")

    # Add PEP condition
    if identity_result and identity_result.pep_check.is_pep:
        conditions.append(f"PEP monitoring: {identity_result.pep_check.pep_tier}")
        if "Enhanced Due Diligence required" not in conditions:
            conditions.append("Enhanced Due Diligence required")

    reasoning = ". ".join(reasoning_parts) + "."

    now = datetime.now(timezone.utc).isoformat()
    audit_trail.append(AuditEntry(
        timestamp=now,
        step="final_decision",
        action=decision,
        details=f"Final decision: {decision.upper()} — {reasoning}",
        agent_name="supervisor",
    ))

    compliance_decision = ComplianceDecision(
        application_id=application.application_id,
        decision=decision,
        risk_tier=risk_tier,
        reasoning=reasoning,
        conditions=conditions,
        checklist=checklist,
        audit_trail=audit_trail,
        document_intake_result=doc_result,
        identity_verification_result=identity_result,
        sanctions_screening_result=sanctions_result,
        risk_assessment_result=risk_result,
        supervisor_decisions=list(state.get("supervisor_decisions", [])),
        was_escalated=was_escalated,
        decided_at=now,
    )

    return {"compliance_decision": compliance_decision}


# ============================================================
# Graph construction
# ============================================================

def build_kyc_graph():
    """Construct the LangGraph workflow for KYC/AML compliance.

    Supervisor hub-and-spoke topology with conditional routing:
        START → supervisor ──[conditional]──→ agents → supervisor → ... → END

    Uses add_conditional_edges — the key LangGraph feature that
    P1 and P2 never use. This enables dynamic routing based on
    runtime state (escalation, dependency ordering).
    """
    graph = StateGraph(KYCState)

    # Add nodes
    graph.add_node("supervisor", supervisor_node)
    graph.add_node("document_intake", document_intake_wrapper)
    graph.add_node("identity_verification", identity_verification_wrapper)
    graph.add_node("sanctions_screening", sanctions_screening_wrapper)
    graph.add_node("risk_assessment", risk_assessment_wrapper)
    graph.add_node("human_review", human_review_node)
    graph.add_node("final_decision", final_decision_node)

    # Entry: always start with supervisor
    graph.add_edge(START, "supervisor")

    # THE KEY FEATURE: conditional routing from supervisor
    graph.add_conditional_edges(
        "supervisor",
        route_from_supervisor,
        {
            "document_intake": "document_intake",
            "identity_verification": "identity_verification",
            "sanctions_screening": "sanctions_screening",
            "risk_assessment": "risk_assessment",
            "final_decision": "final_decision",
            "human_review": "human_review",
        },
    )

    # After each agent completes, return to supervisor (hub-and-spoke)
    graph.add_edge("document_intake", "supervisor")
    graph.add_edge("identity_verification", "supervisor")
    graph.add_edge("sanctions_screening", "supervisor")
    graph.add_edge("risk_assessment", "supervisor")

    # Human review leads to final decision
    graph.add_edge("human_review", "final_decision")

    # Final decision ends the graph
    graph.add_edge("final_decision", END)

    return graph.compile()


# ============================================================
# Entry point
# ============================================================

async def run_kyc_application(application: KYCApplication) -> dict:
    """Main entry point: run a KYC application through the compliance pipeline.

    Returns the full state dict with all agent results, supervisor decisions,
    compliance checklist, audit trail, and final ComplianceDecision.
    """
    graph = build_kyc_graph()

    result = await graph.ainvoke({
        "messages": [],
        "application": application,
        "checklist": ComplianceChecklist(),
        "supervisor_decisions": [],
        "current_step": None,
        "audit_trail": [],
        "document_intake_result": None,
        "identity_verification_result": None,
        "sanctions_screening_result": None,
        "risk_assessment_result": None,
        "compliance_decision": None,
    })

    return result
