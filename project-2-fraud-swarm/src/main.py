"""Main entry point for the Fraud Detection Swarm.

Run with: python -m src.main
"""

from __future__ import annotations

import asyncio
import os
import sys
import time

# Fix Windows console encoding for Unicode output
if sys.platform == "win32":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    except (AttributeError, OSError):
        pass

from .graph import analyze_transaction
from .data_generator import (
    generate_disagreement_trigger,
    generate_edge_case_transaction,
    generate_normal_transaction,
    generate_suspicious_transaction,
)

RISK_ICONS = {"low": "\u2705", "medium": "\u26a0\ufe0f", "high": "\U0001f6a8", "critical": "\U0001f534"}


def print_verdict(verdict) -> None:
    """Pretty-print a specialist verdict."""
    icon = RISK_ICONS.get(verdict.risk_level.value, "?")
    print(f"\n  {icon} {verdict.agent_name.upper()} AGENT")
    print(f"  {'=' * 45}")
    print(f"  Risk: {verdict.risk_level.value.upper()} "
          f"(score: {verdict.risk_score:.3f}, confidence: {verdict.confidence:.0%})")
    print(f"  Action: {verdict.recommended_action}")
    print(f"  Findings:")
    for finding in verdict.key_findings:
        print(f"    - {finding}")
    print(f"  Reasoning:")
    for i, step in enumerate(verdict.reasoning_chain, 1):
        print(f"    {i}. [{step.risk_impact.upper()}] {step.signal}")
        print(f"       {step.observation}")


def print_debate(debate) -> None:
    """Pretty-print the adjudicator's debate analysis."""
    print(f"\n  \U0001f3db ADJUDICATOR DEBATE ANALYSIS")
    print(f"  {'=' * 45}")
    agreement_bar = "\u2588" * int(debate.agreement_score * 10) + "\u2591" * (10 - int(debate.agreement_score * 10))
    print(f"  Agreement: [{agreement_bar}] {debate.agreement_score:.0%}")
    print(f"  Agreeing:   {', '.join(debate.agreeing_agents) or 'none'}")
    print(f"  Dissenting: {', '.join(debate.dissenting_agents) or 'none'}")
    if debate.points_of_contention:
        print(f"  Contention:")
        for point in debate.points_of_contention:
            print(f"    - {point}")
    print(f"  Resolution: {debate.resolution_reasoning}")
    print(f"  Confidence adjustment: {debate.confidence_adjustment:+.2f}")


def print_final(assessment, elapsed: float) -> None:
    """Pretty-print the final swarm assessment."""
    icon = RISK_ICONS.get(assessment.risk_level.value, "?")
    print(f"\n  {icon} FINAL SWARM VERDICT")
    print(f"  {'=' * 45}")
    print(f"  Risk Level:  {assessment.risk_level.value.upper()}")
    print(f"  Confidence:  {assessment.confidence:.0%}")
    print(f"  Action:      {assessment.recommended_action}")
    print(f"  Summary:     {assessment.summary}")
    print(f"  \u23f1 Completed in {elapsed:.2f}s")


async def main() -> None:
    """Run the swarm on sample transactions."""
    print("\n\U0001f50d Fraud Detection Swarm \u2014 Phase 2: Full Multi-Agent Debate")
    print("=" * 70)
    print("  3 specialists (parallel) \u2192 adjudicator debate \u2192 final verdict")

    transactions = [
        ("NORMAL", generate_normal_transaction()),
        ("SUSPICIOUS", generate_suspicious_transaction()),
        ("EDGE CASE", generate_edge_case_transaction()),
        ("DISAGREEMENT TRIGGER", generate_disagreement_trigger()),
    ]

    for label, txn in transactions:
        print(f"\n{'=' * 70}")
        print(f"\U0001f4cb {label}: ${txn.amount:.2f} at {txn.merchant_category}")
        print(f"   Email: {txn.customer_email} | IP: {txn.ip_address}")
        print(f"   Billing: {txn.billing_country} | Shipping: {txn.shipping_country}")

        start = time.monotonic()
        result = await analyze_transaction(txn)
        elapsed = time.monotonic() - start

        # Print all 3 specialist verdicts
        for key in ["velocity_verdict", "identity_verdict", "behavioral_verdict"]:
            verdict = result.get(key)
            if verdict:
                print_verdict(verdict)

        # Print debate analysis
        debate = result.get("debate_analysis")
        if debate:
            print_debate(debate)

        # Print final assessment
        assessment = result.get("final_assessment")
        if assessment:
            print_final(assessment, elapsed)

    print(f"\n{'=' * 70}")
    print("\u2705 Phase 2 complete. Full multi-agent debate operational.")
    print("   Next: Phase 3 adds human-in-the-loop escalation via interrupt().\n")


if __name__ == "__main__":
    asyncio.run(main())
