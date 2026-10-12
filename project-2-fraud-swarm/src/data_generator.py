"""Synthetic transaction data generator for the Fraud Detection Swarm.

Extends P1's generators with a new "disagreement trigger" scenario —
transactions designed to cause specialist agents to disagree, making
the debate pattern visible and testable.

Transaction types:
- Normal: everyday low-risk purchases (amount < $250)
- Suspicious: multiple fraud indicators present
- Edge case: high-value but potentially legitimate
- Disagreement trigger: clean on some dimensions, dirty on others
"""

from __future__ import annotations

import random
import uuid
from datetime import datetime, timedelta

from .models import Transaction


def generate_normal_transaction(rng: random.Random | None = None) -> Transaction:
    """Generate a typical low-risk transaction."""
    rng = rng or random.Random()

    return Transaction(
        transaction_id=f"txn_{uuid.uuid4().hex[:12]}",
        amount=round(rng.uniform(10.0, 250.0), 2),
        currency="USD",
        merchant_category=rng.choice([
            "grocery", "restaurant", "gas_station", "online_retail",
            "subscription", "pharmacy", "coffee_shop",
        ]),
        customer_id=f"cust_{rng.randint(1000, 9999)}",
        customer_email=f"user{rng.randint(100, 999)}@example.com",
        ip_address=f"73.{rng.randint(1, 254)}.{rng.randint(1, 254)}.{rng.randint(1, 254)}",
        device_id=f"dev_{uuid.uuid4().hex[:8]}",
        timestamp=datetime.utcnow() - timedelta(minutes=rng.randint(0, 60)),
        card_last_four=f"{rng.randint(1000, 9999)}",
        billing_country="US",
        shipping_country="US",
    )


def generate_suspicious_transaction(rng: random.Random | None = None) -> Transaction:
    """Generate a transaction with multiple fraud indicators."""
    rng = rng or random.Random()

    return Transaction(
        transaction_id=f"txn_{uuid.uuid4().hex[:12]}",
        amount=round(rng.uniform(2000.0, 15000.0), 2),
        currency="USD",
        merchant_category=rng.choice([
            "electronics", "jewelry", "gift_cards", "wire_transfer",
            "cryptocurrency", "luxury_goods",
        ]),
        customer_id=f"cust_{rng.randint(1000, 9999)}",
        customer_email=f"user{rng.randint(100, 999)}@tempmail.com",
        ip_address=f"185.{rng.randint(1, 254)}.{rng.randint(1, 254)}.{rng.randint(1, 254)}",
        device_id=f"dev_{uuid.uuid4().hex[:8]}",
        timestamp=datetime.utcnow() - timedelta(minutes=rng.randint(0, 5)),
        card_last_four=f"{rng.randint(1000, 9999)}",
        billing_country="US",
        shipping_country=rng.choice(["NG", "RU", "CN", "BR"]),
    )


def generate_edge_case_transaction(rng: random.Random | None = None) -> Transaction:
    """Generate an ambiguous transaction — high-value but potentially legitimate."""
    rng = rng or random.Random()

    return Transaction(
        transaction_id=f"txn_{uuid.uuid4().hex[:12]}",
        amount=round(rng.uniform(800.0, 5000.0), 2),
        currency="USD",
        merchant_category=rng.choice([
            "travel", "hotel", "airline", "car_rental",
            "business_services", "insurance",
        ]),
        customer_id=f"cust_{rng.randint(1000, 9999)}",
        customer_email=f"user{rng.randint(100, 999)}@company.com",
        ip_address=f"104.{rng.randint(1, 254)}.{rng.randint(1, 254)}.{rng.randint(1, 254)}",
        device_id=f"dev_{uuid.uuid4().hex[:8]}",
        timestamp=datetime.utcnow() - timedelta(minutes=rng.randint(0, 30)),
        card_last_four=f"{rng.randint(1000, 9999)}",
        billing_country="US",
        shipping_country=rng.choice(["US", "GB", "DE", "JP"]),
    )


def generate_disagreement_trigger(rng: random.Random | None = None) -> Transaction:
    """Generate a transaction designed to cause specialist disagreement.

    The key insight: this transaction looks CLEAN on velocity (normal spending
    patterns) but DIRTY on identity (new disposable email, fresh account).
    Behavioral signals are ambiguous. This forces the adjudicator to mediate
    a genuine debate — the most valuable signal in multi-agent fraud detection.

    Real-world analog: a sophisticated fraudster who has stolen a card but
    is careful to mimic normal spending patterns. The velocity agent sees
    nothing wrong, but the identity agent flags the synthetic identity.
    """
    rng = rng or random.Random()

    return Transaction(
        transaction_id=f"txn_{uuid.uuid4().hex[:12]}",
        # Moderate amount — doesn't trigger velocity alarms
        amount=round(rng.uniform(150.0, 800.0), 2),
        currency="USD",
        # Normal merchant — nothing suspicious about the category
        merchant_category=rng.choice([
            "online_retail", "electronics", "clothing", "home_goods",
        ]),
        customer_id=f"cust_{rng.randint(8000, 8999)}",
        # Disposable email — identity agent will flag this
        customer_email=f"user{rng.randint(100, 999)}@tempmail.com",
        # Clean US IP — geo looks fine
        ip_address=f"73.{rng.randint(1, 254)}.{rng.randint(1, 254)}.{rng.randint(1, 254)}",
        device_id=f"dev_{uuid.uuid4().hex[:8]}",
        timestamp=datetime.utcnow() - timedelta(minutes=rng.randint(5, 30)),
        card_last_four=f"{rng.randint(1000, 9999)}",
        billing_country="US",
        shipping_country="US",
    )


def generate_test_batch(
    n_normal: int = 3,
    n_suspicious: int = 2,
    n_edge: int = 2,
    n_disagreement: int = 3,
    seed: int | None = 42,
) -> list[Transaction]:
    """Generate a mixed batch of transactions for testing.

    Default mix emphasizes disagreement triggers (30%) since that's
    the key differentiator for Project 2's debate pattern.
    """
    rng = random.Random(seed)
    transactions: list[Transaction] = []

    for _ in range(n_normal):
        transactions.append(generate_normal_transaction(rng))
    for _ in range(n_suspicious):
        transactions.append(generate_suspicious_transaction(rng))
    for _ in range(n_edge):
        transactions.append(generate_edge_case_transaction(rng))
    for _ in range(n_disagreement):
        transactions.append(generate_disagreement_trigger(rng))

    rng.shuffle(transactions)
    return transactions
