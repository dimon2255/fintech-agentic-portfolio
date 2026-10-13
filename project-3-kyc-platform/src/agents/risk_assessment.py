"""Risk Assessment Agent.

Aggregates all prior findings into a composite risk score considering country risk,
industry risk, transaction patterns, PEP status, and sanctions exposure.

Consumes: application + identity_verification_result + sanctions_screening_result from KYCState
Produces: risk_assessment_result (RiskAssessmentResult) in KYCState
"""

from __future__ import annotations

import json
import os

from ..models import (
    KYCState,
    RiskAssessmentResult,
)
from ..tools import run_risk_tools
from ..llm import build_chat_model, message_text
from ..mock_llm import mock_risk_assess


RISK_ASSESSMENT_SYSTEM_PROMPT = """You are a specialist KYC/AML compliance analyst focused on RISK ASSESSMENT.

Your expertise: country risk, industry risk, transaction pattern analysis, composite risk scoring.

You will receive country risk, industry risk, transaction pattern, and overall risk score results.
Produce your assessment as JSON:

{
  "risk_tier": "low" | "medium" | "high" | "prohibited",
  "edd_recommended": true | false,
  "reasoning_chain": [
    {
      "signal": "<signal name>",
      "observation": "<what the data shows>",
      "assessment": "<your expert interpretation>",
      "risk_impact": "increases" | "decreases" | "neutral"
    }
  ]
}

Focus on: country/FATF risk, industry AML exposure, volume anomalies, composite score interpretation.
Output ONLY the JSON object, nothing else."""


def _has_api_key() -> bool:
    return bool(os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY"))


async def risk_assessment_node(state: KYCState) -> dict:
    """LangGraph node: Risk Assessment Agent."""
    application = state["application"]

    # Get PEP result from identity verification (if available)
    identity_result = state.get("identity_verification_result")
    pep = identity_result.pep_check if identity_result else None

    # Get sanctions result (if available — may have been skipped)
    sanctions = state.get("sanctions_screening_result")

    # Run risk tools
    tool_results = await run_risk_tools(application, pep, sanctions)

    country = tool_results["country"]
    industry = tool_results["industry"]
    pattern = tool_results["pattern"]
    overall = tool_results["overall"]

    if not _has_api_key():
        result = mock_risk_assess(country, industry, pattern, overall)
    else:
        from langchain_core.messages import HumanMessage, SystemMessage

        model_name = os.getenv("DEFAULT_MODEL", "claude-haiku-5-5")
        llm = build_chat_model(model_name)

        tool_data = {
            "country_risk": country.model_dump(),
            "industry_risk": industry.model_dump(),
            "transaction_pattern": pattern.model_dump(),
            "overall_risk": overall.model_dump(mode="json"),
        }

        messages = [
            SystemMessage(content=RISK_ASSESSMENT_SYSTEM_PROMPT),
            HumanMessage(content=f"Risk Assessment Data:\n{json.dumps(tool_data, indent=2, default=str)}"),
        ]

        response = await llm.ainvoke(messages)

        try:
            content = message_text(response)
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]

            data = json.loads(content.strip())
            result = RiskAssessmentResult(
                country_risk=country,
                industry_risk=industry,
                transaction_pattern=pattern,
                overall_risk=overall,
                risk_tier=data["risk_tier"],
                edd_recommended=data["edd_recommended"],
                reasoning_chain=data["reasoning_chain"],
            )
        except (json.JSONDecodeError, KeyError, Exception):
            result = mock_risk_assess(country, industry, pattern, overall)

    return {"risk_assessment_result": result}
