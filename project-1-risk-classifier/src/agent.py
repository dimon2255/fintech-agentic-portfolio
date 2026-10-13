"""LangGraph agent for explainable transaction risk classification.

This agent:
1. Receives a transaction
2. Calls 3 analysis tools IN PARALLEL (async)
3. Reasons through the combined signals
4. Produces an explainable risk assessment with full reasoning chain

Unlike traditional fraud scoring (e.g., Kount Omniscore), this agent
doesn't just output a number. It provides a step-by-step reasoning
chain that explains WHY a transaction is risky — critical for
regulatory compliance in fintech.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Annotated, TypedDict

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages

from .models import (
    RiskAssessment,
    Transaction,
    ToolResults,
)
from .llm import build_chat_model, message_text
from .mock_llm import mock_assess
from .tools import run_all_checks

load_dotenv(Path(__file__).resolve().parent.parent / ".env")


def _has_api_key() -> bool:
    """Check if any LLM API key is configured."""
    return bool(os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY"))

# --- Agent State ---

class AgentState(TypedDict):
    """State that flows through the LangGraph graph.

    messages: conversation history for the LLM
    transaction: the transaction being evaluated
    tool_results: results from parallel tool execution
    risk_assessment: final structured output
    """

    messages: Annotated[list, add_messages]
    transaction: Transaction | None
    tool_results: dict | None
    risk_assessment: RiskAssessment | None


# --- System Prompt ---

SYSTEM_PROMPT = """You are an expert fraud analyst agent for a fintech company.
Your job is to analyze transaction data and produce explainable risk assessments.

You will receive:
1. A transaction to evaluate
2. Results from three analysis tools (velocity, geo, device fingerprint)

RESPOND WITH ONLY valid JSON (no markdown, no code fences) in this EXACT schema:

{
  "risk_level": "low" | "medium" | "high" | "critical",
  "confidence": <float 0.0 to 1.0>,
  "reasoning_chain": [
    {
      "signal": "<name of signal analyzed, e.g. Transaction Velocity>",
      "observation": "<what the data shows>",
      "assessment": "<your expert interpretation>",
      "risk_impact": "increases" | "decreases" | "neutral"
    }
  ],
  "recommended_action": "approve" | "review" | "decline",
  "summary": "<2-3 sentence human-readable explanation>"
}

RULES:
- Include exactly one reasoning_chain entry per tool (velocity, geo, device) plus one combined analysis entry
- The "signal" field must be a short label like "Transaction Velocity", "Geolocation Analysis", "Device Fingerprint", "Combined Signal Analysis"
- Consider how signals COMBINE (new device + VPN + high amount = very risky)
- Be specific about what raised or lowered your concern
- When signals conflict, explain the conflict and how you resolved it
- Err on the side of caution: uncertain = "review", not "approve"
- Output ONLY the JSON object, nothing else"""


# --- Graph Nodes ---

async def gather_signals(state: AgentState) -> dict:
    """Node 1: Run all analysis tools in parallel.

    This is where async shines — three independent API calls
    execute simultaneously instead of sequentially.
    """
    transaction = state["transaction"]
    results = await run_all_checks(transaction)

    return {
        "tool_results": results,
        "messages": [
            HumanMessage(content=f"""Analyze this transaction:

        **Transaction:**
        {transaction.model_dump_json(indent=2)}

        **Velocity Analysis:**
        {results['velocity'].model_dump_json(indent=2)}

        **Geolocation Analysis:**
        {results['geo'].model_dump_json(indent=2)}

        **Device Fingerprint Analysis:**
        {results['device'].model_dump_json(indent=2)}

        Produce your risk assessment as JSON.""")
                ],
            }


async def assess_risk(state: AgentState) -> dict:
    """Node 2: Reason through signals and produce assessment.

    Uses real LLM when API key is configured, falls back to
    deterministic mock for development/demo without tokens.
    """
    tool_results = state["tool_results"]
    transaction = state["transaction"]

    if not _has_api_key():
        # Mock mode — deterministic, zero cost, great for dev/demo
        assessment = mock_assess(
            transaction_id=transaction.transaction_id,
            velocity=tool_results["velocity"],
            geo=tool_results["geo"],
            device=tool_results["device"],
        )
    else:
        # Real LLM mode — full reasoning via API
        model_name = os.getenv("DEFAULT_MODEL", "claude-haiku-5-5")
        llm = build_chat_model(model_name)

        messages = [SystemMessage(content=SYSTEM_PROMPT)] + state["messages"]
        response = await llm.ainvoke(messages)

        try:
            content = message_text(response)
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]

            assessment_data = json.loads(content.strip())
            assessment_data["tool_results"] = {
                "velocity": tool_results["velocity"].model_dump(),
                "geo": tool_results["geo"].model_dump(),
                "device": tool_results["device"].model_dump(),
            }
            assessment_data["transaction_id"] = transaction.transaction_id
            assessment_data["assessed_at"] = datetime.utcnow().isoformat()

            assessment = RiskAssessment.model_validate(assessment_data)
        except (json.JSONDecodeError, KeyError, Exception):
            assessment = RiskAssessment(
                transaction_id=transaction.transaction_id,
                risk_level="medium",
                confidence=0.5,
                reasoning_chain=[],
                recommended_action="review",
                summary=f"Agent produced unstructured response. Manual review needed. Raw: {message_text(response)[:500]}",
                tool_results=ToolResults(
                    velocity=tool_results["velocity"],
                    geo=tool_results["geo"],
                    device=tool_results["device"],
                ),
            )

    return {
        "risk_assessment": assessment,
        "messages": [AIMessage(content=assessment.model_dump_json(indent=2))],
    }


# --- Build the Agents Graph ---

def build_risk_classifier_graph() -> StateGraph:
    """Construct the LangGraph workflow for risk classification.

    Graph structure:
        gather_signals  -->  assess_risk  -->  END

    Simple two-node graph for Project 1. Project 2 expands this
    into a multi-agent swarm with debate and escalation.
    """
    graph = StateGraph(AgentState)

    graph.add_node("gather_signals", gather_signals)
    graph.add_node("assess_risk", assess_risk)

    graph.set_entry_point("gather_signals")
    graph.add_edge("gather_signals", "assess_risk")
    graph.add_edge("assess_risk", END)

    return graph.compile()


async def classify_transaction(transaction: Transaction) -> RiskAssessment:
    """Main entry point: classify a single transaction.

    Usage:
        from src.agent import classify_transaction
        from src.models import Transaction

        txn = Transaction(...)
        assessment = await classify_transaction(txn)
        print(assessment.summary)
        print(assessment.reasoning_chain)
    """
    graph = build_risk_classifier_graph()

    result = await graph.ainvoke({
        "messages": [],
        "transaction": transaction,
        "tool_results": None,
        "risk_assessment": None,
    })

    return result["risk_assessment"]
