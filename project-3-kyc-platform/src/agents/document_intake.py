"""Document Intake Agent.

Validates submitted identity and address documents by extracting key fields,
classifying document types, and checking authenticity (expiry, format, tampering).

Consumes: application.documents_submitted from KYCState
Produces: document_intake_result (DocumentIntakeResult) in KYCState
"""

from __future__ import annotations

import json
import os

from ..models import (
    DocumentIntakeResult,
    KYCState,
)
from ..tools import run_document_intake_tools
from ..mock_llm import mock_document_intake


DOCUMENT_INTAKE_SYSTEM_PROMPT = """You are a specialist KYC/AML compliance analyst focused on DOCUMENT VERIFICATION.

Your expertise: validating identity documents, detecting forgeries, assessing document quality.

You will receive extraction, classification, and validation results for submitted documents.
Produce your assessment as JSON:

{
  "overall_document_quality": <float 0.0 to 1.0>,
  "issues_found": ["<issue 1>", "<issue 2>"],
  "reasoning_chain": [
    {
      "signal": "<signal name>",
      "observation": "<what the data shows>",
      "assessment": "<your expert interpretation>",
      "risk_impact": "increases" | "decreases" | "neutral"
    }
  ]
}

Focus on: document expiry, extraction quality, classification accuracy, tampering indicators.
Output ONLY the JSON object, nothing else."""


def _has_api_key() -> bool:
    return bool(os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY"))


async def document_intake_node(state: KYCState) -> dict:
    """LangGraph node: Document Intake Agent."""
    application = state["application"]
    documents = application.documents_submitted

    # Run all document tools in parallel
    tool_results = await run_document_intake_tools(documents)

    extractions = tool_results["extractions"]
    classifications = tool_results["classifications"]
    validations = tool_results["validations"]

    if not _has_api_key():
        result = mock_document_intake(extractions, classifications, validations)
    else:
        from langchain_anthropic import ChatAnthropic
        from langchain_openai import ChatOpenAI
        from langchain_core.messages import HumanMessage, SystemMessage

        model_name = os.getenv("DEFAULT_MODEL", "claude-haiku-4-5-20251001")
        if "claude" in model_name:
            llm = ChatAnthropic(model=model_name, temperature=0)
        else:
            llm = ChatOpenAI(model=model_name, temperature=0)

        tool_data = {
            "extractions": [e.model_dump() for e in extractions],
            "classifications": [c.model_dump() for c in classifications],
            "validations": [v.model_dump() for v in validations],
        }

        messages = [
            SystemMessage(content=DOCUMENT_INTAKE_SYSTEM_PROMPT),
            HumanMessage(content=f"Document Analysis Results:\n{json.dumps(tool_data, indent=2, default=str)}"),
        ]

        response = await llm.ainvoke(messages)

        try:
            content = response.content
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]

            data = json.loads(content.strip())
            result = DocumentIntakeResult(
                documents_processed=len(extractions),
                extractions=extractions,
                classifications=classifications,
                validations=validations,
                overall_document_quality=data["overall_document_quality"],
                issues_found=data["issues_found"],
                reasoning_chain=data["reasoning_chain"],
            )
        except (json.JSONDecodeError, KeyError, Exception):
            result = mock_document_intake(extractions, classifications, validations)

    return {"document_intake_result": result}
