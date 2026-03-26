"""Supervisor node for the KYC/AML Compliance Platform.

The supervisor is the brain of Project 3's architecture — a cyclic orchestrator
that runs after each specialist agent and dynamically decides the next step.

This is the key architectural advancement over Project 2's adjudicator:
- P2's adjudicator runs ONCE after all agents (terminal reducer)
- P3's supervisor runs AFTER EACH agent and re-routes (cyclic orchestrator)

Routing logic:
    1. Default sequential flow: doc_intake -> identity -> sanctions -> risk -> final
    2. Skip logic: low-risk domestic individuals skip sanctions screening
    3. Escalation: document failures, identity failures, strong sanctions hits
    4. Auto-reject: PROHIBITED risk tier
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone

from .models import (
    AuditEntry,
    ComplianceChecklist,
    KYCState,
    SupervisorDecision,
)
from .mock_llm import mock_supervisor_route


SUPERVISOR_SYSTEM_PROMPT = """You are the SUPERVISOR of a KYC/AML compliance pipeline.

You orchestrate 4 specialist agents in sequence:
1. Document Intake — validates submitted documents
2. Identity Verification — cross-references identity data
3. Sanctions Screening — checks OFAC, EU, UN lists
4. Risk Assessment — computes composite risk score

After each agent completes, you decide the next step. Your options:
- Route to the next pending agent
- Skip an agent (e.g., sanctions for low-risk domestic individuals)
- Escalate to human_review (if critical issues found)
- Route to final_decision (when all steps done or auto-reject)

Current pipeline state and completed agent results will be provided.

RESPOND WITH ONLY valid JSON:

{
  "next_step": "document_intake" | "identity_verification" | "sanctions_screening" | "risk_assessment" | "final_decision" | "human_review",
  "reasoning": "why you chose this routing",
  "skipped_steps": ["step: reason"],
  "risk_flags_so_far": ["flag 1", "flag 2"]
}

Output ONLY the JSON object, nothing else."""


def _has_api_key() -> bool:
    return bool(os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY"))


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def supervisor_node(state: KYCState) -> dict:
    """LangGraph node: Supervisor hub.

    Examines completed work and routes to the next step.
    Uses add_conditional_edges in graph.py to implement the routing.
    """
    if not _has_api_key():
        decision = mock_supervisor_route(state)
    else:
        from langchain_anthropic import ChatAnthropic
        from langchain_openai import ChatOpenAI
        from langchain_core.messages import HumanMessage, SystemMessage

        model_name = os.getenv("DEFAULT_MODEL", "claude-haiku-4-5-20251001")
        if "claude" in model_name:
            llm = ChatAnthropic(model=model_name, temperature=0)
        else:
            llm = ChatOpenAI(model=model_name, temperature=0)

        # Build state summary for the LLM
        checklist = state.get("checklist") or ComplianceChecklist()
        state_summary = {
            "applicant": state["application"].applicant_name,
            "nationality": state["application"].nationality,
            "country_of_residence": state["application"].country_of_residence,
            "business_type": state["application"].business_type,
            "expected_volume": state["application"].expected_monthly_volume,
            "checklist": checklist.model_dump(),
        }

        # Add summaries of completed agent results
        if state.get("document_intake_result"):
            r = state["document_intake_result"]
            state_summary["document_intake_summary"] = {
                "quality": r.overall_document_quality,
                "issues": r.issues_found,
            }
        if state.get("identity_verification_result"):
            r = state["identity_verification_result"]
            state_summary["identity_summary"] = {
                "confirmed": r.identity_confirmed,
                "confidence": r.confidence,
                "discrepancies": r.discrepancies,
            }
        if state.get("sanctions_screening_result"):
            r = state["sanctions_screening_result"]
            state_summary["sanctions_summary"] = {
                "any_hits": r.any_hits,
                "highest_match": r.highest_match_score,
            }
        if state.get("risk_assessment_result"):
            r = state["risk_assessment_result"]
            state_summary["risk_summary"] = {
                "tier": r.risk_tier.value,
                "edd_recommended": r.edd_recommended,
            }

        messages = [
            SystemMessage(content=SUPERVISOR_SYSTEM_PROMPT),
            HumanMessage(content=f"Pipeline State:\n{json.dumps(state_summary, indent=2, default=str)}"),
        ]

        response = await llm.ainvoke(messages)

        try:
            content = response.content
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]

            data = json.loads(content.strip())
            decision = SupervisorDecision.model_validate(data)
        except (json.JSONDecodeError, KeyError, Exception):
            decision = mock_supervisor_route(state)

    # Update checklist for skipped steps
    checklist = state.get("checklist") or ComplianceChecklist()
    audit_trail = list(state.get("audit_trail", []))

    for skip_note in decision.skipped_steps:
        step_name = skip_note.split(":")[0].strip()
        if hasattr(checklist, step_name) and getattr(checklist, step_name) == "pending":
            checklist = checklist.model_copy(update={step_name: "skipped"})
            checklist.completed_at[step_name] = _now_iso()
            audit_trail.append(AuditEntry(
                timestamp=_now_iso(),
                step=step_name,
                action="skipped",
                details=skip_note,
                agent_name="supervisor",
            ))

    # Log the routing decision
    audit_trail.append(AuditEntry(
        timestamp=_now_iso(),
        step="supervisor",
        action="routing",
        details=f"Routing to {decision.next_step}: {decision.reasoning}",
        agent_name="supervisor",
    ))

    # Build the updated supervisor_decisions list
    existing_decisions = list(state.get("supervisor_decisions", []))
    existing_decisions.append(decision)

    return {
        "supervisor_decisions": existing_decisions,
        "current_step": decision.next_step,
        "checklist": checklist,
        "audit_trail": audit_trail,
    }
