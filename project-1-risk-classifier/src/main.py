"""Main entry point for the Transaction Risk Classifier.

Run with: python -m src.main
"""

from __future__ import annotations

import asyncio
import json
import time

from .agent import classify_transaction
from .data_generator import (
    generate_edge_case_transaction,
    generate_normal_transaction,
    generate_suspicious_transaction,
)


def print_assessment(assessment, elapsed: float) -> None:
    """Pretty-print a risk assessment to the console."""
    print("\n" + "=" * 70)
    print(f"  Transaction: {assessment.transaction_id}")
    print(f"  Risk Level:  {assessment.risk_level.value.upper()}")
    print(f"  Confidence:  {assessment.confidence:.0%}")
    print(f"  Action:      {assessment.recommended_action}")
    print(f"  Time:        {elapsed:.2f}s")
    print("=" * 70)
    print(f"\n  Summary: {assessment.summary}\n")

    if assessment.reasoning_chain:
        print("  Reasoning Chain:")
        print("  " + "-" * 50)
        for i, step in enumerate(assessment.reasoning_chain, 1):
            print(f"  {i}. [{step.risk_impact.upper()}] {step.signal}")
            print(f"     Observed: {step.observation}")
            print(f"     Assessment: {step.assessment}")
            print()


async def main() -> None:
    """Run the classifier on sample transactions."""
    print("\n🔍 Transaction Risk Classifier — Explainable Fraud Detection")
    print("=" * 70)

    # Generate one of each type
    transactions = [
        ("NORMAL", generate_normal_transaction()),
        ("SUSPICIOUS", generate_suspicious_transaction()),
        ("EDGE CASE", generate_edge_case_transaction()),
    ]

    for label, txn in transactions:
        print(f"\n📋 Classifying {label} transaction: ${txn.amount:.2f} "
              f"at {txn.merchant_category} from {txn.billing_country}")

        start = time.monotonic()
        assessment = await classify_transaction(txn)
        elapsed = time.monotonic() - start

        print_assessment(assessment, elapsed)

    print("\n✅ All transactions classified. Full reasoning chains above.\n")


if __name__ == "__main__":
    asyncio.run(main())
