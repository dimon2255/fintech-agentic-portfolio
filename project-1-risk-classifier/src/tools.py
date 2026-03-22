"""Async tool implementations for transaction risk analysis.

Each tool simulates an external API call (velocity check, geo lookup,
device fingerprint) using async patterns. In production, these would
call real services — the async pattern ensures we don't block while
waiting for responses.

KEY ASYNC CONCEPT:
    These tools run in parallel via asyncio.gather(), meaning a
    3-tool check that takes 2 seconds each completes in ~2 seconds
    total instead of 6 seconds sequentially. Critical for real-time
    fraud detection where sub-second decisions matter.
"""

from __future__ import annotations

import asyncio
import hashlib
import random

from .models import (
    DeviceFingerprintResult,
    GeoResult,
    Transaction,
    VelocityResult,
)

# --- Simulated latency to mimic real API calls ---
SIMULATED_LATENCY_SECONDS = 0.3


async def check_velocity(transaction: Transaction) -> VelocityResult:
    """Check transaction velocity patterns for the customer.

    In production: queries a time-series database of recent transactions.
    Flags rapid-fire purchasing, unusual amounts, or spending spikes.

    This is ASYNC because the database query takes time — while we wait,
    other tools (geo, device) can run simultaneously.
    """
    # Simulate API latency — this is where async shines
    await asyncio.sleep(SIMULATED_LATENCY_SECONDS)

    # Deterministic synthetic data based on customer_id for reproducibility
    seed = int(hashlib.md5(transaction.customer_id.encode()).hexdigest()[:8], 16)
    rng = random.Random(seed + int(transaction.amount))

    txn_last_hour = rng.randint(0, 8)
    txn_last_24h = rng.randint(txn_last_hour, 25)
    avg_amount = rng.uniform(50.0, 500.0)
    deviation = abs(transaction.amount - avg_amount) / max(avg_amount * 0.3, 1.0)
    rapid_succession = txn_last_hour > 4

    # Calculate risk: high velocity + high deviation = risky
    risk = min(1.0, (txn_last_hour / 10) * 0.4 + min(deviation / 5, 1.0) * 0.6)

    return VelocityResult(
        transactions_last_hour=txn_last_hour,
        transactions_last_24h=txn_last_24h,
        avg_transaction_amount_30d=round(avg_amount, 2),
        amount_deviation_factor=round(deviation, 2),
        rapid_succession_flag=rapid_succession,
        velocity_risk_score=round(risk, 3),
    )


async def lookup_geo(transaction: Transaction) -> GeoResult:
    """Analyze geolocation signals from the transaction IP.

    In production: calls an IP intelligence API (MaxMind, IPinfo)
    to resolve location, VPN/proxy detection, and Tor exit nodes.

    ASYNC because external API calls are I/O-bound — the CPU sits
    idle while waiting for the network response.
    """
    await asyncio.sleep(SIMULATED_LATENCY_SECONDS)

    seed = int(hashlib.md5(transaction.ip_address.encode()).hexdigest()[:8], 16)
    rng = random.Random(seed)

    # Synthetic geo data
    countries = ["US", "US", "US", "GB", "DE", "NG", "RU", "CN", "BR", "IN"]
    cities = ["New York", "London", "Berlin", "Lagos", "Moscow", "Beijing", "Sao Paulo", "Mumbai"]
    ip_country = rng.choice(countries)
    ip_city = rng.choice(cities)

    is_vpn = rng.random() < 0.15
    is_tor = rng.random() < 0.05
    billing_match = ip_country == transaction.billing_country
    distance = rng.uniform(0, 5000) if not billing_match else rng.uniform(0, 200)

    # Risk: VPN/Tor, geo mismatch, and distance all increase risk
    risk = 0.0
    if is_vpn:
        risk += 0.3
    if is_tor:
        risk += 0.4
    if not billing_match:
        risk += 0.2
    risk += min(distance / 10000, 0.1)
    risk = min(1.0, risk)

    return GeoResult(
        ip_country=ip_country,
        ip_city=ip_city,
        is_vpn=is_vpn,
        is_tor=is_tor,
        billing_geo_match=billing_match,
        distance_from_usual_km=round(distance, 1),
        geo_risk_score=round(risk, 3),
    )


async def fingerprint_device(transaction: Transaction) -> DeviceFingerprintResult:
    """Analyze device fingerprint for trust and anomaly signals.

    In production: queries a device intelligence service (fingerprint.com,
    HUMAN Security) to assess device reputation and history.

    ASYNC for the same reason — external service call, I/O-bound wait.
    """
    await asyncio.sleep(SIMULATED_LATENCY_SECONDS)

    seed = int(hashlib.md5(transaction.device_id.encode()).hexdigest()[:8], 16)
    rng = random.Random(seed)

    device_known = rng.random() > 0.25
    device_age = rng.randint(0, 365) if device_known else 0
    trust_score = min(1.0, device_age / 180) if device_known else 0.1
    multi_account = rng.random() < 0.1
    fingerprint_changed = rng.random() < 0.08

    # Risk: unknown devices, multi-account, fingerprint changes
    risk = 0.0
    if not device_known:
        risk += 0.4
    if multi_account:
        risk += 0.3
    if fingerprint_changed:
        risk += 0.2
    risk += (1.0 - trust_score) * 0.1
    risk = min(1.0, risk)

    return DeviceFingerprintResult(
        device_known=device_known,
        device_age_days=device_age,
        device_trust_score=round(trust_score, 3),
        multiple_accounts_on_device=multi_account,
        os_fingerprint_changed=fingerprint_changed,
        device_risk_score=round(risk, 3),
    )


async def run_all_checks(transaction: Transaction) -> dict:
    """Run all three analysis tools in PARALLEL using asyncio.gather.

    THIS IS THE KEY ASYNC PATTERN:
        Instead of:
            velocity = await check_velocity(txn)    # 0.3s
            geo = await lookup_geo(txn)              # 0.3s  (waits for velocity)
            device = await fingerprint_device(txn)   # 0.3s  (waits for geo)
            # Total: 0.9s sequential

        We do:
            velocity, geo, device = await asyncio.gather(
                check_velocity(txn),
                lookup_geo(txn),
                fingerprint_device(txn),
            )
            # Total: ~0.3s parallel — 3x faster

    In real fraud detection, this is the difference between
    a 200ms and a 600ms decision. At scale, that matters.
    """
    velocity, geo, device = await asyncio.gather(
        check_velocity(transaction),
        lookup_geo(transaction),
        fingerprint_device(transaction),
    )

    return {
        "velocity": velocity,
        "geo": geo,
        "device": device,
    }
