"""Velocity Pattern Specialist Agent.

Analyzes transaction frequency patterns, amount deviations, and
rapid succession indicators to detect card testing, burst fraud,
and unusual spending velocity.

Consumes: VelocityResult from the velocity check tool
Produces: SpecialistVerdict with reasoning chain

Supports both mock (deterministic) and LLM (API-based) modes.
"""

from __future__ import annotations

import json
import os

from ..models import (
    ReasoningStep,
    RiskLevel,
    SpecialistVerdict,
    SwarmState,
)
from ..llm import build_chat_model, message_text
from ..mock_llm import mock_velocity_assess


VELOCITY_SYSTEM_PROMPT = """You are a specialist fraud analyst focused on TRANSACTION VELOCITY patterns.

Your expertise: detecting card testing, burst fraud, and unusual spending velocity.

You will receive velocity analysis data. Produce your verdict as JSON:

{
  "risk_score": <float 0.0 to 1.0>,
  "risk_level": "low" | "medium" | "high" | "critical",
  "confidence": <float 0.0 to 1.0>,
  "reasoning_chain": [
    {
      "signal": "<signal name>",
      "observation": "<what the data shows>",
      "assessment": "<your expert interpretation>",
      "risk_impact": "increases" | "decreases" | "neutral"
    }
  ],
  "key_findings": ["<finding 1>", "<finding 2>"],
  "recommended_action": "approve" | "review" | "decline"
}

Focus on: transaction frequency, amount deviation from baseline, rapid succession patterns.
Output ONLY the JSON object, nothing else."""


def _has_api_key() -> bool:
    return bool(os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY"))


async def velocity_agent_node(state: SwarmState) -> dict:
    """LangGraph node: Velocity Pattern Specialist.

    Reads velocity tool results from state, produces a SpecialistVerdict.
    """
    tool_results = state["tool_results"]
    velocity = tool_results.velocity

    if not _has_api_key():
        verdict = mock_velocity_assess(velocity)
    else:
        from langchain_core.messages import HumanMessage, SystemMessage

        model_name = os.getenv("DEFAULT_MODEL", "claude-haiku-5-5")
        llm = build_chat_model(model_name)

        messages = [
            SystemMessage(content=VELOCITY_SYSTEM_PROMPT),
            HumanMessage(content=f"Velocity Analysis Data:\n{velocity.model_dump_json(indent=2)}"),
        ]

        # Invoke the LLM and parse the JSON response into a SpecialistVerdict.
        response = await llm.ainvoke(messages)

        try:
            content = message_text(response)
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]

            data = json.loads(content.strip())
            data["agent_name"] = "velocity"
            verdict = SpecialistVerdict.model_validate(data)
            
        except (json.JSONDecodeError, KeyError, Exception):
            verdict = mock_velocity_assess(velocity)

    return {"velocity_verdict": verdict}
