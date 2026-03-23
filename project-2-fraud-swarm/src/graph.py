"""LangGraph graph definition for the Fraud Detection Swarm.

Phase 2 topology (current):
    START → gather_all_signals
        → velocity_agent  ─┐
        → identity_agent  ─┼→ adjudicator → END
        → behavioral_agent─┘

Three specialists run in parallel via LangGraph fan-out edges.
The adjudicator receives all 3 verdicts (fan-in), detects
disagreement, and produces the final SwarmAssessment.

Phase 3 (next): Adds conditional routing to human_review node
with LangGraph interrupt() for human-in-the-loop escalation.
"""

from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from langgraph.graph import END, START, StateGraph

from .models import (
    SwarmState,
    ToolResults,
    Transaction,
)
from .tools import run_all_checks
from .agents.velocity_agent import velocity_agent_node
from .agents.identity_agent import identity_agent_node
from .agents.behavioral_agent import behavioral_agent_node
from .adjudicator import adjudicator_node

load_dotenv(Path(__file__).resolve().parent.parent / ".env")


# ============================================================
# Graph nodes
# ============================================================

async def gather_all_signals(state: SwarmState) -> dict:
    """Run all 5 analysis tools in parallel.

    Populates tool_results (P1 tools), identity_signals, and
    behavioral_signals in the state for specialist agents to consume.
    """
    transaction = state["transaction"]
    results = await run_all_checks(transaction)

    tool_results = ToolResults(
        velocity=results["velocity"],
        geo=results["geo"],
        device=results["device"],
    )

    return {
        "tool_results": tool_results,
        "identity_signals": results["identity"],
        "behavioral_signals": results["behavioral"],
        "messages": [
            HumanMessage(content=(
                f"Analyzing transaction {transaction.transaction_id}: "
                f"${transaction.amount:.2f} at {transaction.merchant_category} "
                f"from {transaction.billing_country}. "
                f"All 5 signal checks completed."
            ))
        ],
    }


# ============================================================
# Graph construction
# ============================================================

def build_fraud_swarm_graph():
    """Construct the LangGraph workflow for the fraud detection swarm.

    Phase 2 topology — fan-out/fan-in:
        gather_all_signals
            → velocity_agent  ─┐
            → identity_agent  ─┼→ adjudicator → END
            → behavioral_agent─┘

    Three specialists execute in PARALLEL via LangGraph's native
    fan-out. When all three complete, the adjudicator node fires
    (fan-in), receives all verdicts, and produces the final assessment.
    """
    graph = StateGraph(SwarmState)

    # Add nodes
    graph.add_node("gather_all_signals", gather_all_signals)
    graph.add_node("velocity_agent", velocity_agent_node)
    graph.add_node("identity_agent", identity_agent_node)
    graph.add_node("behavioral_agent", behavioral_agent_node)
    graph.add_node("adjudicator", adjudicator_node)

    # Entry edge
    graph.add_edge(START, "gather_all_signals")

    # Fan-out: gather → 3 specialists in parallel
    graph.add_edge("gather_all_signals", "velocity_agent")
    graph.add_edge("gather_all_signals", "identity_agent")
    graph.add_edge("gather_all_signals", "behavioral_agent")

    # Fan-in: 3 specialists → adjudicator
    graph.add_edge("velocity_agent", "adjudicator")
    graph.add_edge("identity_agent", "adjudicator")
    graph.add_edge("behavioral_agent", "adjudicator")

    # Adjudicator → END
    graph.add_edge("adjudicator", END)

    return graph.compile()


async def analyze_transaction(transaction: Transaction) -> dict:
    """Main entry point: run a transaction through the swarm.

    Returns the full state dict with specialist verdicts,
    debate analysis, and final SwarmAssessment.
    """
    graph = build_fraud_swarm_graph()

    result = await graph.ainvoke({
        "messages": [],
        "transaction": transaction,
        "tool_results": None,
        "identity_signals": None,
        "behavioral_signals": None,
        "velocity_verdict": None,
        "identity_verdict": None,
        "behavioral_verdict": None,
        "debate_analysis": None,
        "escalation_context": None,
        "human_decision": None,
        "final_assessment": None,
    })

    return result
