"""Sanctions Screening Agent.

Screens the applicant against OFAC SDN, EU Consolidated, and UN Consolidated
sanctions lists plus adverse media. Uses fuzzy name matching with configurable
threshold.

Consumes: application from KYCState
Produces: sanctions_screening_result (SanctionsScreeningResult) in KYCState
"""

from __future__ import annotations

import json
import os

from ..models import (
    KYCState,
    SanctionsScreeningResult,
)
from ..tools import run_sanctions_tools
from ..llm import build_chat_model, message_text
from ..mock_llm import mock_sanctions_screen


SANCTIONS_SCREENING_SYSTEM_PROMPT = """You are a specialist KYC/AML compliance analyst focused on SANCTIONS SCREENING.

Your expertise: OFAC, EU, and UN sanctions list matching, adverse media analysis, fuzzy name matching.

You will receive screening results from OFAC SDN, EU Consolidated, UN Consolidated, and adverse media.
Produce your assessment as JSON:

{
  "any_hits": true | false,
  "highest_match_score": <float 0.0 to 1.0>,
  "reasoning_chain": [
    {
      "signal": "<signal name>",
      "observation": "<what the data shows>",
      "assessment": "<your expert interpretation>",
      "risk_impact": "increases" | "decreases" | "neutral"
    }
  ]
}

Focus on: match confidence, false positive assessment, adverse media severity, cross-list correlation.
Output ONLY the JSON object, nothing else."""


def _has_api_key() -> bool:
    return bool(os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY"))


async def sanctions_screening_node(state: KYCState) -> dict:
    """LangGraph node: Sanctions Screening Agent."""
    application = state["application"]

    # Run all 4 sanctions tools in parallel
    tool_results = await run_sanctions_tools(
        application.applicant_name, application.nationality
    )

    ofac = tool_results["ofac"]
    eu = tool_results["eu"]
    un = tool_results["un"]
    media = tool_results["adverse_media"]

    if not _has_api_key():
        result = mock_sanctions_screen(ofac, eu, un, media)
    else:
        from langchain_core.messages import HumanMessage, SystemMessage

        model_name = os.getenv("DEFAULT_MODEL", "claude-haiku-5-5")
        llm = build_chat_model(model_name)

        tool_data = {
            "ofac": ofac.model_dump(),
            "eu_sanctions": eu.model_dump(),
            "un_sanctions": un.model_dump(),
            "adverse_media": media.model_dump(),
        }

        messages = [
            SystemMessage(content=SANCTIONS_SCREENING_SYSTEM_PROMPT),
            HumanMessage(content=f"Sanctions Screening Data:\n{json.dumps(tool_data, indent=2, default=str)}"),
        ]

        response = await llm.ainvoke(messages)

        try:
            content = message_text(response)
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]

            data = json.loads(content.strip())
            result = SanctionsScreeningResult(
                ofac_result=ofac,
                eu_result=eu,
                un_result=un,
                adverse_media=media,
                any_hits=data["any_hits"],
                highest_match_score=data["highest_match_score"],
                reasoning_chain=data["reasoning_chain"],
            )
        except (json.JSONDecodeError, KeyError, Exception):
            result = mock_sanctions_screen(ofac, eu, un, media)

    return {"sanctions_screening_result": result}
