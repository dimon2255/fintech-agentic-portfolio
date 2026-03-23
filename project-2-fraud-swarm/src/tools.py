"""Async tool implementations for the Fraud Detection Swarm.

Includes P1 tools (velocity, geo, device) plus two new P2 tools:
- check_identity(): Identity graph analysis (email, address, linked accounts)
- analyze_behavior(): Behavioral anomaly detection (session, navigation, bot patterns)

All tools follow the same async pattern:
- Seeded RNG for deterministic, reproducible output
- Simulated latency via asyncio.sleep() to mimic real API calls
- Pydantic return types for type safety
- Parallel execution via asyncio.gather() in run_all_checks()
"""

from __future__ import annotations

import asyncio
import hashlib
import random

from .models import (
    BehavioralSignals,
    DeviceFingerprintResult,
    GeoResult,
    IdentitySignals,
    Transaction,
    VelocityResult,
)

# --- Simulated latency to mimic real API calls ---
SIMULATED_LATENCY_SECONDS = 0.3


# ============================================================
# P1 tools (copied from project-1-risk-classifier)
# ============================================================

async def check_velocity(transaction: Transaction) -> VelocityResult:
    """Check transaction velocity patterns for the customer.

    In production: queries a time-series database of recent transactions.
    """
    await asyncio.sleep(SIMULATED_LATENCY_SECONDS)

    seed = int(hashlib.md5(transaction.customer_id.encode()).hexdigest()[:8], 16)
    rng = random.Random(seed + int(transaction.amount))

    txn_last_hour = rng.randint(0, 8)
    txn_last_24h = rng.randint(txn_last_hour, 25)
    avg_amount = rng.uniform(50.0, 500.0)
    deviation = abs(transaction.amount - avg_amount) / max(avg_amount * 0.3, 1.0)
    rapid_succession = txn_last_hour > 4

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

    In production: calls an IP intelligence API (MaxMind, IPinfo).
    """
    await asyncio.sleep(SIMULATED_LATENCY_SECONDS)

    seed = int(hashlib.md5(transaction.ip_address.encode()).hexdigest()[:8], 16)
    rng = random.Random(seed)

    countries = ["US", "US", "US", "GB", "DE", "NG", "RU", "CN", "BR", "IN"]
    cities = ["New York", "London", "Berlin", "Lagos", "Moscow", "Beijing", "Sao Paulo", "Mumbai"]
    ip_country = rng.choice(countries)
    ip_city = rng.choice(cities)

    is_vpn = rng.random() < 0.15
    is_tor = rng.random() < 0.05
    billing_match = ip_country == transaction.billing_country
    distance = rng.uniform(0, 5000) if not billing_match else rng.uniform(0, 200)

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

    In production: queries a device intelligence service (fingerprint.com).
    """
    await asyncio.sleep(SIMULATED_LATENCY_SECONDS)

    seed = int(hashlib.md5(transaction.device_id.encode()).hexdigest()[:8], 16)
    rng = random.Random(seed)

    device_known = rng.random() > 0.25
    device_age = rng.randint(0, 365) if device_known else 0
    trust_score = min(1.0, device_age / 180) if device_known else 0.1
    multi_account = rng.random() < 0.1
    fingerprint_changed = rng.random() < 0.08

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


# ============================================================
# P2 new tools
# ============================================================

async def check_identity(transaction: Transaction) -> IdentitySignals:
    """Analyze identity graph signals for the customer.

    In production: cross-references identity elements across multiple
    data sources — email intelligence (Emailage), address verification
    (Melissa), phone verification (Telesign), and account history.

    Key fraud patterns detected:
    - Synthetic identities (new email + new account + no phone verification)
    - Account takeover (sudden change in identity elements)
    - Chargeback patterns across linked accounts
    """
    await asyncio.sleep(SIMULATED_LATENCY_SECONDS)

    seed = int(hashlib.md5(transaction.customer_email.encode()).hexdigest()[:8], 16)
    rng = random.Random(seed + int(transaction.amount))

    # Email analysis
    email_domain = transaction.customer_email.split("@")[-1]
    trusted_domains = ["gmail.com", "outlook.com", "yahoo.com", "company.com", "example.com"]
    disposable_domains = ["tempmail.com", "throwaway.io", "guerrillamail.com"]

    if email_domain in disposable_domains:
        domain_rep = "disposable"
        email_age = rng.randint(0, 7)
    elif email_domain in trusted_domains:
        domain_rep = "trusted"
        email_age = rng.randint(30, 3650)
    else:
        domain_rep = "suspicious"
        email_age = rng.randint(1, 90)

    phone_verified = rng.random() > 0.3
    name_match = rng.uniform(0.3, 1.0) if domain_rep == "trusted" else rng.uniform(0.1, 0.7)

    avs_options = ["match", "match", "match", "partial", "mismatch", "unknown"]
    avs_status = rng.choice(avs_options)

    linked_accounts = rng.randint(1, 3) if domain_rep == "trusted" else rng.randint(1, 8)
    chargebacks = 0 if rng.random() > 0.15 else rng.randint(1, 5)
    account_age = rng.randint(1, 1825) if domain_rep != "disposable" else rng.randint(0, 14)

    # Risk calculation
    risk = 0.0
    if domain_rep == "disposable":
        risk += 0.35
    elif domain_rep == "suspicious":
        risk += 0.15
    if email_age < 30:
        risk += 0.2
    if not phone_verified:
        risk += 0.15
    if avs_status == "mismatch":
        risk += 0.2
    elif avs_status == "unknown":
        risk += 0.1
    if linked_accounts > 4:
        risk += 0.15
    if chargebacks > 0:
        risk += min(chargebacks * 0.15, 0.4)
    if account_age < 7:
        risk += 0.15
    risk = min(1.0, risk)

    return IdentitySignals(
        email_age_days=email_age,
        email_domain_reputation=domain_rep,
        name_email_match_score=round(name_match, 3),
        phone_verified=phone_verified,
        address_verification_status=avs_status,
        linked_accounts_count=linked_accounts,
        previous_chargebacks=chargebacks,
        account_age_days=account_age,
        identity_risk_score=round(risk, 3),
    )


async def analyze_behavior(transaction: Transaction) -> BehavioralSignals:
    """Analyze behavioral patterns for anomaly detection.

    In production: ingests session telemetry from a behavioral
    analytics platform (FullStory, Heap, or custom collectors).

    Key fraud patterns detected:
    - Bot-like behavior (instant checkout, no browsing, scripted mouse)
    - Account takeover (unusual time-of-day, unfamiliar navigation)
    - Social engineering (erratic navigation, hesitation patterns)
    """
    await asyncio.sleep(SIMULATED_LATENCY_SECONDS)

    seed = int(hashlib.md5(
        f"{transaction.device_id}_{transaction.customer_id}".encode()
    ).hexdigest()[:8], 16)
    rng = random.Random(seed + int(transaction.amount))

    # Session behavior
    session_duration = rng.randint(15, 1800)
    pages_visited = rng.randint(1, 20)
    checkout_speed = rng.randint(5, 600)

    # Anomaly indicators
    typing_anomaly = rng.random() < 0.08
    mouse_anomaly = rng.random() < 0.06
    time_unusual = rng.random() < 0.12

    # Navigation pattern based on session behavior
    if checkout_speed < 30 and pages_visited < 3:
        nav_pattern = "direct_to_checkout"
    elif pages_visited > 15 and session_duration < 120:
        nav_pattern = "erratic"
    else:
        nav_pattern = "normal"

    # Risk calculation
    risk = 0.0
    if nav_pattern == "direct_to_checkout":
        risk += 0.3
    elif nav_pattern == "erratic":
        risk += 0.2
    if checkout_speed < 15:
        risk += 0.25
    if typing_anomaly:
        risk += 0.2
    if mouse_anomaly:
        risk += 0.25
    if time_unusual:
        risk += 0.1
    if session_duration < 30:
        risk += 0.15
    risk = min(1.0, risk)

    return BehavioralSignals(
        session_duration_seconds=session_duration,
        pages_visited=pages_visited,
        checkout_speed_seconds=checkout_speed,
        typing_pattern_anomaly=typing_anomaly,
        mouse_movement_anomaly=mouse_anomaly,
        time_of_day_unusual=time_unusual,
        navigation_pattern=nav_pattern,
        behavioral_risk_score=round(risk, 3),
    )


# ============================================================
# Parallel execution orchestrator
# ============================================================

async def run_all_checks(transaction: Transaction) -> dict:
    """Run ALL five analysis tools in parallel.

    Extends P1's 3-tool pattern with identity and behavioral checks.
    5 tools x 0.3s each = ~0.3s total (parallel) vs 1.5s sequential.
    """
    velocity, geo, device, identity, behavioral = await asyncio.gather(
        check_velocity(transaction),
        lookup_geo(transaction),
        fingerprint_device(transaction),
        check_identity(transaction),
        analyze_behavior(transaction),
    )

    return {
        "velocity": velocity,
        "geo": geo,
        "device": device,
        "identity": identity,
        "behavioral": behavioral,
    }
