"""Synthetic transaction data generator.

Generates realistic-looking but entirely fake financial transactions
for testing the risk classification agent. NEVER uses real PII.

Produces a mix of:
- Normal transactions (everyday purchases)
- Suspicious transactions (fraud indicators present)
- Edge cases (high-value legitimate, new customer, travel)
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


def generate_test_batch(
    n_normal: int = 5,
    n_suspicious: int = 3,
    n_edge: int = 2,
    seed: int | None = 42,
) -> list[Transaction]:
    """Generate a mixed batch of transactions for testing.

    Default mix: 50% normal, 30% suspicious, 20% edge cases.
    Set seed for reproducible test data.
    """
    rng = random.Random(seed)
    transactions: list[Transaction] = []

    for _ in range(n_normal):
        transactions.append(generate_normal_transaction(rng))
    for _ in range(n_suspicious):
        transactions.append(generate_suspicious_transaction(rng))
    for _ in range(n_edge):
        transactions.append(generate_edge_case_transaction(rng))

    rng.shuffle(transactions)
    return transactions
