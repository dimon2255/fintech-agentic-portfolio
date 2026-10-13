"""Adjudicator / Supervisor for the Fraud Detection Swarm.

Receives all 3 specialist verdicts, detects agreement/disagreement,
and produces the final assessment: the unweighted mean of the
specialist risk scores, with low agreement turning an approval into
a review, plus the debate analysis.

In LLM mode the adjudicator also analyzes why the agents disagree; that
analysis and its agreement score are recorded, but the LLM's own final
verdict is not used.
"""

from __future__ import annotations

import json
import os
from datetime import datetime

from .models import (
    DebateAnalysis,
    RiskLevel,
    SpecialistVerdict,
    SwarmAssessment,
    SwarmState,
)
from .llm import build_chat_model, message_text
from .mock_llm import mock_adjudicate


ADJUDICATOR_SYSTEM_PROMPT = """You are the senior adjudicator in a multi-agent fraud detection system.

Three specialist agents have independently analyzed a transaction:
- Velocity Agent: analyzes spending patterns, frequency, amount deviation
- Identity Agent: analyzes identity coherence, email, address, linked accounts
- Behavioral Agent: analyzes session behavior, navigation, bot indicators

You will receive all three verdicts. Your job is to:
1. Identify where agents AGREE and DISAGREE
2. Analyze WHY they disagree — which reasoning is more compelling
3. Weight each agent's expertise based on the transaction context
4. Produce a synthesized final verdict

RESPOND WITH ONLY valid JSON:

{
  "debate_analysis": {
    "agreement_score": <float 0.0 to 1.0 — 1.0=unanimous>,
    "agreeing_agents": ["agent1", "agent2"],
    "dissenting_agents": ["agent3"],
    "points_of_contention": ["what they disagree about"],
    "resolution_reasoning": "how you resolved the disagreement",
    "confidence_adjustment": <float — negative means debate lowered confidence>
  },
  "final_risk_level": "low" | "medium" | "high" | "critical",
  "final_confidence": <float 0.0 to 1.0>,
  "final_action": "approve" | "review" | "decline",
  "summary": "2-3 sentence summary of the multi-agent assessment"
}

Output ONLY the JSON object, nothing else."""


def _has_api_key() -> bool:
    return bool(os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY"))


def _determine_final_verdict(
    verdicts: list[SpecialistVerdict],
    debate: DebateAnalysis,
) -> tuple[RiskLevel, float, str, str]:
    """Synthesize final risk level, confidence, action, and summary from debate."""
    # Unweighted mean of the specialist risk scores
    avg_score = sum(v.risk_score for v in verdicts) / len(verdicts)
    avg_confidence = sum(v.confidence for v in verdicts) / len(verdicts)

    # Apply debate confidence adjustment
    final_confidence = max(0.1, min(0.99, avg_confidence + debate.confidence_adjustment))

    # Determine risk level from the mean score
    if avg_score > 0.6:
        risk_level = RiskLevel.CRITICAL if avg_score > 0.8 else RiskLevel.HIGH
        action = "decline"
    elif avg_score > 0.35:
        risk_level = RiskLevel.MEDIUM
        action = "review"
    else:
        risk_level = RiskLevel.LOW
        action = "approve"

    # If heavy disagreement, bump toward review
    if debate.agreement_score < 0.5 and action == "approve":
        risk_level = RiskLevel.MEDIUM
        action = "review"

    # Build summary
    if not debate.dissenting_agents:
        summary = (
            f"All 3 specialists unanimously assess {risk_level.value} risk "
            f"({final_confidence:.0%} confidence). {debate.resolution_reasoning}"
        )
    else:
        summary = (
            f"Swarm assessment: {risk_level.value} risk ({final_confidence:.0%} confidence). "
            f"{', '.join(debate.agreeing_agents)} agree while "
            f"{', '.join(debate.dissenting_agents)} dissent. "
            f"{debate.resolution_reasoning}"
        )

    return risk_level, final_confidence, action, summary


async def adjudicator_node(state: SwarmState) -> dict:
    """LangGraph node: Adjudicator / Debate Resolver.

    Reads all 3 specialist verdicts, produces DebateAnalysis and
    the final SwarmAssessment with complete audit trail.
    """
    verdicts = [
        state["velocity_verdict"],
        state["identity_verdict"],
        state["behavioral_verdict"],
    ]
    transaction = state["transaction"]

    if not _has_api_key():
        debate = mock_adjudicate(verdicts)
    else:
        from langchain_core.messages import HumanMessage, SystemMessage

        model_name = os.getenv("DEFAULT_MODEL", "claude-haiku-5-5")
        llm = build_chat_model(model_name)

        verdicts_json = "\n\n".join([
            f"--- {v.agent_name.upper()} AGENT ---\n{v.model_dump_json(indent=2)}"
            for v in verdicts
        ])

        messages = [
            SystemMessage(content=ADJUDICATOR_SYSTEM_PROMPT),
            HumanMessage(content=(
                f"Transaction: {transaction.transaction_id} — "
                f"${transaction.amount:.2f} at {transaction.merchant_category}\n\n"
                f"Specialist Verdicts:\n{verdicts_json}"
            )),
        ]

        response = await llm.ainvoke(messages)

        try:
            content = message_text(response)
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]

            data = json.loads(content.strip())
            debate = DebateAnalysis.model_validate(data["debate_analysis"])
        except (json.JSONDecodeError, KeyError, Exception):
            debate = mock_adjudicate(verdicts)

    # Synthesize final verdict
    risk_level, confidence, action, summary = _determine_final_verdict(verdicts, debate)

    assessment = SwarmAssessment(
        transaction_id=transaction.transaction_id,
        risk_level=risk_level,
        confidence=round(confidence, 3),
        recommended_action=action,
        summary=summary,
        specialist_verdicts=verdicts,
        debate_analysis=debate,
        tool_results=state["tool_results"],
        identity_signals=state["identity_signals"],
        behavioral_signals=state["behavioral_signals"],
        assessed_at=datetime.utcnow(),
    )

    return {
        "debate_analysis": debate,
        "final_assessment": assessment,
    }
