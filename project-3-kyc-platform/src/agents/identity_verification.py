"""Identity Verification Agent.

Cross-references extracted document data against application data to confirm
the applicant's identity. Checks name matching, address verification, DOB
consistency, and PEP screening.

Consumes: application + document_intake_result from KYCState
Produces: identity_verification_result (IdentityVerificationResult) in KYCState
"""

from __future__ import annotations

import json
import os

from ..models import (
    IdentityVerificationResult,
    KYCState,
)
from ..tools import run_identity_tools
from ..llm import build_chat_model, message_text
from ..mock_llm import mock_identity_verify


IDENTITY_VERIFICATION_SYSTEM_PROMPT = """You are a specialist KYC/AML compliance analyst focused on IDENTITY VERIFICATION.

Your expertise: cross-referencing identity documents, detecting inconsistencies, PEP screening.

You will receive name match, address verification, DOB cross-check, and PEP screening results.
Produce your assessment as JSON:

{
  "identity_confirmed": true | false,
  "confidence": <float 0.0 to 1.0>,
  "discrepancies": ["<discrepancy 1>", "<discrepancy 2>"],
  "reasoning_chain": [
    {
      "signal": "<signal name>",
      "observation": "<what the data shows>",
      "assessment": "<your expert interpretation>",
      "risk_impact": "increases" | "decreases" | "neutral"
    }
  ]
}

Focus on: name consistency, address match, DOB verification, PEP status.
Output ONLY the JSON object, nothing else."""


def _has_api_key() -> bool:
    return bool(os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY"))


async def identity_verification_node(state: KYCState) -> dict:
    """LangGraph node: Identity Verification Agent."""
    application = state["application"]
    doc_result = state["document_intake_result"]

    # Use the first (primary) extraction for identity checks
    primary_extraction = doc_result.extractions[0]

    # Run identity tools in parallel
    tool_results = await run_identity_tools(application, primary_extraction)

    name_res = tool_results["name_match"]
    addr_res = tool_results["address_verify"]
    dob_res = tool_results["dob_crosscheck"]
    pep_res = tool_results["pep_check"]

    if not _has_api_key():
        result = mock_identity_verify(name_res, addr_res, dob_res, pep_res)
    else:
        from langchain_core.messages import HumanMessage, SystemMessage

        model_name = os.getenv("DEFAULT_MODEL", "claude-haiku-5-5")
        llm = build_chat_model(model_name)

        tool_data = {
            "name_match": name_res.model_dump(),
            "address_verify": addr_res.model_dump(),
            "dob_crosscheck": dob_res.model_dump(),
            "pep_check": pep_res.model_dump(),
        }

        messages = [
            SystemMessage(content=IDENTITY_VERIFICATION_SYSTEM_PROMPT),
            HumanMessage(content=f"Identity Verification Data:\n{json.dumps(tool_data, indent=2, default=str)}"),
        ]

        response = await llm.ainvoke(messages)

        try:
            content = message_text(response)
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]

            data = json.loads(content.strip())
            result = IdentityVerificationResult(
                name_match=name_res,
                address_verify=addr_res,
                dob_crosscheck=dob_res,
                pep_check=pep_res,
                identity_confirmed=data["identity_confirmed"],
                confidence=data["confidence"],
                discrepancies=data["discrepancies"],
                reasoning_chain=data["reasoning_chain"],
            )
        except (json.JSONDecodeError, KeyError, Exception):
            result = mock_identity_verify(name_res, addr_res, dob_res, pep_res)

    return {"identity_verification_result": result}
