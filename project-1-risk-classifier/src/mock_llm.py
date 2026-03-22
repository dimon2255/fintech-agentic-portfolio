"""Mock LLM for testing the full pipeline without API keys.

Produces deterministic risk assessments based on tool results,
simulating what the real LLM would reason. Useful for:
- Development iteration without burning tokens
- Unit testing with predictable outputs
- Demo mode when no API key is configured
"""

from __future__ import annotations

from datetime import datetime

from .models import (
    DeviceFingerprintResult,
    GeoResult,
    ReasoningStep,
    RiskAssessment,
    RiskLevel,
    ToolResults,
    VelocityResult,
)


def mock_assess(
    transaction_id: str,
    velocity: VelocityResult,
    geo: GeoResult,
    device: DeviceFingerprintResult,
) -> RiskAssessment:
    """Produce a deterministic risk assessment from tool results.

    Mimics the LLM's reasoning logic with explicit rules,
    generating a reasoning chain that explains each signal.
    """
    reasoning: list[ReasoningStep] = []
    risk_signals: list[float] = []

    # --- Velocity analysis ---
    if velocity.velocity_risk_score > 0.6:
        reasoning.append(ReasoningStep(
            signal="Transaction Velocity",
            observation=f"{velocity.transactions_last_hour} transactions in the last hour, "
                        f"amount deviates {velocity.amount_deviation_factor:.1f}x from 30-day average",
            assessment="Unusually high transaction frequency and amount deviation suggest potential card testing or fraudulent burst activity",
            risk_impact="increases",
        ))
        risk_signals.append(velocity.velocity_risk_score)
    elif velocity.velocity_risk_score > 0.3:
        reasoning.append(ReasoningStep(
            signal="Transaction Velocity",
            observation=f"{velocity.transactions_last_hour} transactions in the last hour, "
                        f"amount deviates {velocity.amount_deviation_factor:.1f}x from average",
            assessment="Moderate velocity — above normal but within plausible range for legitimate shopping sprees or business purchases",
            risk_impact="increases",
        ))
        risk_signals.append(velocity.velocity_risk_score)
    else:
        reasoning.append(ReasoningStep(
            signal="Transaction Velocity",
            observation=f"{velocity.transactions_last_hour} transactions in the last hour, "
                        f"amount within {velocity.amount_deviation_factor:.1f}x of average",
            assessment="Normal transaction velocity and amount — consistent with customer's established pattern",
            risk_impact="decreases",
        ))
        risk_signals.append(0.0)

    # --- Geo analysis ---
    geo_flags: list[str] = []
    if geo.is_vpn:
        geo_flags.append("VPN detected")
    if geo.is_tor:
        geo_flags.append("Tor exit node")
    if not geo.billing_geo_match:
        geo_flags.append(f"geo mismatch (IP: {geo.ip_country}, billing: customer's country)")

    if geo.geo_risk_score > 0.5:
        reasoning.append(ReasoningStep(
            signal="Geolocation Analysis",
            observation=f"IP from {geo.ip_city}, {geo.ip_country}. Flags: {', '.join(geo_flags) if geo_flags else 'none'}. "
                        f"Distance from usual location: {geo.distance_from_usual_km:.0f}km",
            assessment="Multiple geolocation red flags suggest the transaction may originate from a compromised or anonymized source",
            risk_impact="increases",
        ))
        risk_signals.append(geo.geo_risk_score)
    elif geo.geo_risk_score > 0.2:
        reasoning.append(ReasoningStep(
            signal="Geolocation Analysis",
            observation=f"IP from {geo.ip_city}, {geo.ip_country}. Flags: {', '.join(geo_flags) if geo_flags else 'none'}",
            assessment="Some geolocation anomalies present but not conclusive — could indicate travel or remote work",
            risk_impact="increases",
        ))
        risk_signals.append(geo.geo_risk_score)
    else:
        reasoning.append(ReasoningStep(
            signal="Geolocation Analysis",
            observation=f"IP from {geo.ip_city}, {geo.ip_country}. Billing country match: {geo.billing_geo_match}. No VPN/Tor detected",
            assessment="Clean geolocation profile — IP location consistent with billing address, no anonymization detected",
            risk_impact="decreases",
        ))
        risk_signals.append(0.0)

    # --- Device analysis ---
    if device.device_risk_score > 0.4:
        device_flags = []
        if not device.device_known:
            device_flags.append("unknown device")
        if device.multiple_accounts_on_device:
            device_flags.append("multi-account device")
        if device.os_fingerprint_changed:
            device_flags.append("fingerprint changed")
        reasoning.append(ReasoningStep(
            signal="Device Fingerprint",
            observation=f"Device known: {device.device_known}, trust score: {device.device_trust_score:.2f}. "
                        f"Flags: {', '.join(device_flags) if device_flags else 'none'}",
            assessment="Device profile raises concerns — either unknown or showing signs of manipulation",
            risk_impact="increases",
        ))
        risk_signals.append(device.device_risk_score)
    else:
        reasoning.append(ReasoningStep(
            signal="Device Fingerprint",
            observation=f"Device known: {device.device_known}, age: {device.device_age_days} days, "
                        f"trust score: {device.device_trust_score:.2f}",
            assessment="Recognized device with established trust history — consistent with legitimate customer behavior",
            risk_impact="decreases",
        ))
        risk_signals.append(0.0)

    # --- Combined assessment ---
    avg_risk = sum(risk_signals) / len(risk_signals) if risk_signals else 0.0
    high_signals = sum(1 for s in risk_signals if s > 0.5)

    if high_signals >= 2 or avg_risk > 0.6:
        risk_level = RiskLevel.HIGH if avg_risk < 0.8 else RiskLevel.CRITICAL
        action = "decline"
        confidence = min(0.95, 0.7 + high_signals * 0.1)
    elif high_signals >= 1 or avg_risk > 0.3:
        risk_level = RiskLevel.MEDIUM
        action = "review"
        confidence = 0.7
    else:
        risk_level = RiskLevel.LOW
        action = "approve"
        confidence = min(0.95, 0.8 + (1.0 - avg_risk) * 0.15)

    # Add combination reasoning
    reasoning.append(ReasoningStep(
        signal="Combined Signal Analysis",
        observation=f"{high_signals} of 3 tools flagged elevated risk. Average risk signal: {avg_risk:.2f}",
        assessment=f"Overall assessment is {risk_level.value} risk. "
                   f"{'Multiple independent signals corroborate elevated risk.' if high_signals >= 2 else 'Risk signals are isolated or within acceptable range.'}",
        risk_impact="increases" if risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL) else "neutral",
    ))

    summary_parts = []
    if risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL):
        summary_parts.append(f"Transaction flagged as {risk_level.value} risk with {confidence:.0%} confidence.")
        summary_parts.append(f"{high_signals} of 3 analysis dimensions raised concerns.")
        summary_parts.append(f"Recommended action: {action}.")
    elif risk_level == RiskLevel.MEDIUM:
        summary_parts.append(f"Transaction shows mixed signals warranting human review ({confidence:.0%} confidence).")
        summary_parts.append("Some risk indicators present but not conclusive enough for automated decline.")
    else:
        summary_parts.append(f"Transaction appears legitimate ({confidence:.0%} confidence).")
        summary_parts.append("All analysis dimensions within normal parameters. Approved for processing.")

    return RiskAssessment(
        transaction_id=transaction_id,
        risk_level=risk_level,
        confidence=round(confidence, 2),
        reasoning_chain=reasoning,
        recommended_action=action,
        summary=" ".join(summary_parts),
        tool_results=ToolResults(
            velocity=velocity,
            geo=geo,
            device=device,
        ),
        assessed_at=datetime.utcnow(),
    )
