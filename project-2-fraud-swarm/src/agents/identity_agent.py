"""Identity Graph Specialist Agent.

Analyzes identity coherence by cross-referencing email intelligence,
address verification, device-identity correlation, linked accounts,
and chargeback history to detect synthetic identities, account
takeover, and stolen credentials.

Consumes: GeoResult, DeviceFingerprintResult, IdentitySignals
Produces: SpecialistVerdict with reasoning chain
"""

from __future__ import annotations

import json
import os

from ..models import (
    SpecialistVerdict,
    SwarmState,
)
from ..mock_llm import mock_identity_assess


IDENTITY_SYSTEM_PROMPT = """You are a specialist fraud analyst focused on IDENTITY GRAPH analysis.

Your expertise: detecting synthetic identities, account takeover, and stolen credentials
by cross-referencing identity elements (email, address, phone, device, account history).

You will receive identity signals, geolocation data, and device fingerprint data.
Produce your verdict as JSON:

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

Focus on: email age/reputation, address verification, linked accounts, chargebacks,
device-identity correlation, account age patterns.
Output ONLY the JSON object, nothing else."""


def _has_api_key() -> bool:
    return bool(os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY"))


async def identity_agent_node(state: SwarmState) -> dict:
    """LangGraph node: Identity Graph Specialist.

    Reads geo, device, and identity signals from state,
    produces a SpecialistVerdict.
    """
    tool_results = state["tool_results"]
    identity = state["identity_signals"]
    geo = tool_results.geo
    device = tool_results.device

    if not _has_api_key():
        verdict = mock_identity_assess(geo, device, identity)
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
            SystemMessage(content=IDENTITY_SYSTEM_PROMPT),
            HumanMessage(content=(
                f"Identity Signals:\n{identity.model_dump_json(indent=2)}\n\n"
                f"Geolocation Data:\n{geo.model_dump_json(indent=2)}\n\n"
                f"Device Fingerprint:\n{device.model_dump_json(indent=2)}"
            )),
        ]

        response = await llm.ainvoke(messages)

        try:
            content = response.content
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]

            data = json.loads(content.strip())
            data["agent_name"] = "identity"
            verdict = SpecialistVerdict.model_validate(data)

        except (json.JSONDecodeError, KeyError, Exception):
            verdict = mock_identity_assess(geo, device, identity)

    return {"identity_verdict": verdict}
