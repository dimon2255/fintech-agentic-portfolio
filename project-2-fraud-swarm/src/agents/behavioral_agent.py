"""Behavioral Anomaly Specialist Agent.

Analyzes session behavior patterns to detect bot-driven fraud,
account takeover through unfamiliar navigation, and social
engineering through erratic interaction patterns.

Consumes: BehavioralSignals
Produces: SpecialistVerdict with reasoning chain
"""

from __future__ import annotations

import json
import os

from ..models import (
    SpecialistVerdict,
    SwarmState,
)
from ..mock_llm import mock_behavioral_assess


BEHAVIORAL_SYSTEM_PROMPT = """You are a specialist fraud analyst focused on BEHAVIORAL ANOMALY detection.

Your expertise: detecting bot-driven fraud, account takeover, and social engineering
by analyzing session telemetry — navigation patterns, checkout speed, input anomalies,
and temporal patterns.

You will receive behavioral session data. Produce your verdict as JSON:

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

Focus on: navigation pattern (direct-to-checkout vs normal browsing), checkout speed,
typing/mouse anomalies (bot indicators), time-of-day patterns, session duration.
Output ONLY the JSON object, nothing else."""


def _has_api_key() -> bool:
    return bool(os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY"))


async def behavioral_agent_node(state: SwarmState) -> dict:
    """LangGraph node: Behavioral Anomaly Specialist.

    Reads behavioral signals from state, produces a SpecialistVerdict.
    """
    behavioral = state["behavioral_signals"]

    if not _has_api_key():
        verdict = mock_behavioral_assess(behavioral)
    else:
        from langchain_anthropic import ChatAnthropic
        from langchain_openai import ChatOpenAI
        from langchain_core.messages import HumanMessage, SystemMessage

        model_name = os.getenv("DEFAULT_MODEL", "claude-haiku-4-5-20251001")
        if "claude" in model_name:
            llm = ChatAnthropic(model=model_name, temperature=0)
        else:
            llm = ChatOpenAI(model=model_name, temperature=0)

        messages = [
            SystemMessage(content=BEHAVIORAL_SYSTEM_PROMPT),
            HumanMessage(content=f"Behavioral Session Data:\n{behavioral.model_dump_json(indent=2)}"),
        ]

        response = await llm.ainvoke(messages)

        try:
            content = response.content
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]

            data = json.loads(content.strip())
            data["agent_name"] = "behavioral"
            verdict = SpecialistVerdict.model_validate(data)

        except (json.JSONDecodeError, KeyError, Exception):
            verdict = mock_behavioral_assess(behavioral)

    return {"behavioral_verdict": verdict}
