"""Mock LLM for the Fraud Detection Swarm.

Produces deterministic specialist verdicts and adjudicator decisions
without API calls. Each specialist has its own mock reasoning function
that mirrors what the real LLM would reason.

Used when no API key is configured — great for:
- Development iteration without burning tokens
- Unit testing with predictable outputs
- Demo mode showing the debate pattern
"""

from __future__ import annotations

from .models import (
    BehavioralSignals,
    DebateAnalysis,
    DeviceFingerprintResult,
    GeoResult,
    IdentitySignals,
    ReasoningStep,
    RiskLevel,
    SpecialistVerdict,
    VelocityResult,
)


# ============================================================
# Velocity specialist mock
# ============================================================

def mock_velocity_assess(
    velocity: VelocityResult,
) -> SpecialistVerdict:
    """Deterministic velocity pattern analysis."""
    reasoning: list[ReasoningStep] = []
    key_findings: list[str] = []

    # Frequency analysis
    if velocity.transactions_last_hour > 4:
        reasoning.append(ReasoningStep(
            signal="Transaction Frequency",
            observation=f"{velocity.transactions_last_hour} transactions in last hour, "
                        f"{velocity.transactions_last_24h} in last 24h",
            assessment="Unusually high frequency suggests card testing or burst fraud activity",
            risk_impact="increases",
        ))
        key_findings.append(f"High frequency: {velocity.transactions_last_hour} txns/hour")
    else:
        reasoning.append(ReasoningStep(
            signal="Transaction Frequency",
            observation=f"{velocity.transactions_last_hour} transactions in last hour",
            assessment="Normal transaction frequency within expected range",
            risk_impact="decreases",
        ))

    # Amount deviation
    if velocity.amount_deviation_factor > 3.0:
        reasoning.append(ReasoningStep(
            signal="Amount Deviation",
            observation=f"Amount deviates {velocity.amount_deviation_factor:.1f}x from "
                        f"30-day average of ${velocity.avg_transaction_amount_30d:.2f}",
            assessment="Significant departure from spending baseline — possible unauthorized use",
            risk_impact="increases",
        ))
        key_findings.append(f"Amount {velocity.amount_deviation_factor:.1f}x above average")
    elif velocity.amount_deviation_factor > 1.5:
        reasoning.append(ReasoningStep(
            signal="Amount Deviation",
            observation=f"Amount deviates {velocity.amount_deviation_factor:.1f}x from average",
            assessment="Moderate deviation — could be a legitimate larger purchase",
            risk_impact="neutral",
        ))
    else:
        reasoning.append(ReasoningStep(
            signal="Amount Deviation",
            observation=f"Amount within {velocity.amount_deviation_factor:.1f}x of average",
            assessment="Consistent with established spending pattern",
            risk_impact="decreases",
        ))

    # Rapid succession
    if velocity.rapid_succession_flag:
        reasoning.append(ReasoningStep(
            signal="Rapid Succession",
            observation="Transactions occurring in rapid succession detected",
            assessment="Rapid-fire pattern often associated with automated card testing",
            risk_impact="increases",
        ))
        key_findings.append("Rapid succession flag triggered")

    # Overall verdict
    score = velocity.velocity_risk_score
    if score > 0.6:
        risk_level = RiskLevel.HIGH
        action = "decline"
        confidence = 0.85
    elif score > 0.3:
        risk_level = RiskLevel.MEDIUM
        action = "review"
        confidence = 0.70
    else:
        risk_level = RiskLevel.LOW
        action = "approve"
        confidence = 0.85

    if not key_findings:
        key_findings.append("Normal velocity pattern — no anomalies detected")

    return SpecialistVerdict(
        agent_name="velocity",
        risk_score=score,
        risk_level=risk_level,
        confidence=confidence,
        reasoning_chain=reasoning,
        key_findings=key_findings,
        recommended_action=action,
    )


# ============================================================
# Identity specialist mock
# ============================================================

def mock_identity_assess(
    geo: GeoResult,
    device: DeviceFingerprintResult,
    identity: IdentitySignals,
) -> SpecialistVerdict:
    """Deterministic identity graph analysis."""
    reasoning: list[ReasoningStep] = []
    key_findings: list[str] = []
    risk_signals: list[float] = []

    # Email analysis
    if identity.email_domain_reputation == "disposable":
        reasoning.append(ReasoningStep(
            signal="Email Intelligence",
            observation=f"Disposable email domain, account age: {identity.email_age_days} days",
            assessment="Disposable email is a strong synthetic identity indicator",
            risk_impact="increases",
        ))
        key_findings.append(f"Disposable email, {identity.email_age_days} days old")
        risk_signals.append(0.8)
    elif identity.email_domain_reputation == "suspicious":
        reasoning.append(ReasoningStep(
            signal="Email Intelligence",
            observation=f"Suspicious email domain, age: {identity.email_age_days} days",
            assessment="Uncommon email domain warrants additional scrutiny",
            risk_impact="increases",
        ))
        key_findings.append("Suspicious email domain")
        risk_signals.append(0.5)
    else:
        reasoning.append(ReasoningStep(
            signal="Email Intelligence",
            observation=f"Trusted email domain, age: {identity.email_age_days} days, "
                        f"name match: {identity.name_email_match_score:.0%}",
            assessment="Established email with good domain reputation",
            risk_impact="decreases",
        ))
        risk_signals.append(0.1)

    # Address verification
    if identity.address_verification_status == "mismatch":
        reasoning.append(ReasoningStep(
            signal="Address Verification",
            observation=f"AVS status: {identity.address_verification_status}",
            assessment="Billing address does not match records — possible account takeover",
            risk_impact="increases",
        ))
        key_findings.append("Address verification mismatch")
        risk_signals.append(0.7)
    elif identity.address_verification_status == "match":
        reasoning.append(ReasoningStep(
            signal="Address Verification",
            observation="AVS status: full match",
            assessment="Billing address confirmed — consistent with account holder",
            risk_impact="decreases",
        ))
        risk_signals.append(0.1)

    # Linked accounts & chargebacks
    if identity.previous_chargebacks > 0:
        reasoning.append(ReasoningStep(
            signal="Chargeback History",
            observation=f"{identity.previous_chargebacks} previous chargeback(s), "
                        f"{identity.linked_accounts_count} linked accounts",
            assessment="Chargeback history is a strong predictor of future fraud",
            risk_impact="increases",
        ))
        key_findings.append(f"{identity.previous_chargebacks} prior chargeback(s)")
        risk_signals.append(min(0.9, 0.4 + identity.previous_chargebacks * 0.15))

    # Device-identity correlation
    if not device.device_known and identity.account_age_days < 14:
        reasoning.append(ReasoningStep(
            signal="Device-Identity Correlation",
            observation=f"New device + new account ({identity.account_age_days} days old)",
            assessment="New device on a new account is a classic synthetic identity pattern",
            risk_impact="increases",
        ))
        key_findings.append("New device + new account combination")
        risk_signals.append(0.7)

    # Overall verdict
    score = identity.identity_risk_score
    avg_signal = sum(risk_signals) / len(risk_signals) if risk_signals else score
    final_score = (score + avg_signal) / 2

    if final_score > 0.6:
        risk_level = RiskLevel.HIGH
        action = "decline"
        confidence = 0.80
    elif final_score > 0.3:
        risk_level = RiskLevel.MEDIUM
        action = "review"
        confidence = 0.70
    else:
        risk_level = RiskLevel.LOW
        action = "approve"
        confidence = 0.85

    if not key_findings:
        key_findings.append("Identity profile is consistent and established")

    return SpecialistVerdict(
        agent_name="identity",
        risk_score=round(final_score, 3),
        risk_level=risk_level,
        confidence=confidence,
        reasoning_chain=reasoning,
        key_findings=key_findings,
        recommended_action=action,
    )


# ============================================================
# Behavioral specialist mock
# ============================================================

def mock_behavioral_assess(
    behavioral: BehavioralSignals,
) -> SpecialistVerdict:
    """Deterministic behavioral anomaly analysis."""
    reasoning: list[ReasoningStep] = []
    key_findings: list[str] = []

    # Navigation pattern
    if behavioral.navigation_pattern == "direct_to_checkout":
        reasoning.append(ReasoningStep(
            signal="Navigation Pattern",
            observation=f"Direct-to-checkout: {behavioral.pages_visited} pages, "
                        f"checkout in {behavioral.checkout_speed_seconds}s",
            assessment="Skipping browsing and rushing to checkout is common in bot-driven fraud",
            risk_impact="increases",
        ))
        key_findings.append(f"Direct-to-checkout in {behavioral.checkout_speed_seconds}s")
    elif behavioral.navigation_pattern == "erratic":
        reasoning.append(ReasoningStep(
            signal="Navigation Pattern",
            observation=f"Erratic: {behavioral.pages_visited} pages in "
                        f"{behavioral.session_duration_seconds}s session",
            assessment="Erratic navigation may indicate unfamiliarity with the account",
            risk_impact="increases",
        ))
        key_findings.append("Erratic navigation pattern")
    else:
        reasoning.append(ReasoningStep(
            signal="Navigation Pattern",
            observation=f"Normal browsing: {behavioral.pages_visited} pages, "
                        f"{behavioral.session_duration_seconds}s session",
            assessment="Natural browsing behavior consistent with legitimate shopping",
            risk_impact="decreases",
        ))

    # Bot indicators
    bot_flags = []
    if behavioral.typing_pattern_anomaly:
        bot_flags.append("typing anomaly")
    if behavioral.mouse_movement_anomaly:
        bot_flags.append("mouse anomaly")

    if bot_flags:
        reasoning.append(ReasoningStep(
            signal="Bot Detection",
            observation=f"Anomalies detected: {', '.join(bot_flags)}",
            assessment="Input pattern anomalies suggest automated or scripted interaction",
            risk_impact="increases",
        ))
        key_findings.append(f"Bot indicators: {', '.join(bot_flags)}")

    # Time of day
    if behavioral.time_of_day_unusual:
        reasoning.append(ReasoningStep(
            signal="Temporal Analysis",
            observation="Transaction at unusual time for this customer",
            assessment="Off-pattern timing may indicate unauthorized access",
            risk_impact="increases",
        ))
        key_findings.append("Unusual time-of-day for customer")

    # Overall verdict
    score = behavioral.behavioral_risk_score
    if score > 0.5:
        risk_level = RiskLevel.HIGH
        action = "decline"
        confidence = 0.75
    elif score > 0.25:
        risk_level = RiskLevel.MEDIUM
        action = "review"
        confidence = 0.65
    else:
        risk_level = RiskLevel.LOW
        action = "approve"
        confidence = 0.80

    if not key_findings:
        key_findings.append("Normal behavioral pattern — no anomalies detected")

    return SpecialistVerdict(
        agent_name="behavioral",
        risk_score=score,
        risk_level=risk_level,
        confidence=confidence,
        reasoning_chain=reasoning,
        key_findings=key_findings,
        recommended_action=action,
    )


# ============================================================
# Adjudicator mock
# ============================================================

def mock_adjudicate(
    verdicts: list[SpecialistVerdict],
) -> DebateAnalysis:
    """Deterministic debate analysis across specialist verdicts.

    Detects agreement/disagreement, identifies contention points,
    and produces a resolution reasoning.
    """
    # Compare risk levels pairwise
    levels = [v.risk_level for v in verdicts]
    names = [v.agent_name for v in verdicts]

    # Calculate agreement score
    pairwise_scores = []
    level_order = [RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.CRITICAL]
    for i in range(len(levels)):
        for j in range(i + 1, len(levels)):
            dist = abs(level_order.index(levels[i]) - level_order.index(levels[j]))
            if dist == 0:
                pairwise_scores.append(1.0)
            elif dist == 1:
                pairwise_scores.append(0.5)
            else:
                pairwise_scores.append(0.0)

    agreement_score = sum(pairwise_scores) / len(pairwise_scores) if pairwise_scores else 1.0

    # Find majority and dissent
    from collections import Counter
    level_counts = Counter(levels)
    majority_level = level_counts.most_common(1)[0][0]

    agreeing = [n for n, l in zip(names, levels) if l == majority_level]
    dissenting = [n for n, l in zip(names, levels) if l != majority_level]

    # Points of contention
    contention = []
    for v in verdicts:
        if v.agent_name in dissenting:
            contention.extend([
                f"{v.agent_name} agent says {v.risk_level.value} "
                f"(score: {v.risk_score:.2f}): {finding}"
                for finding in v.key_findings[:2]
            ])

    # Resolution reasoning
    if not dissenting:
        resolution = (
            f"All {len(verdicts)} specialists agree on {majority_level.value} risk. "
            f"Unanimous consensus increases confidence in the assessment."
        )
        confidence_adj = 0.1
    elif len(dissenting) == 1:
        dissenter = next(v for v in verdicts if v.agent_name == dissenting[0])
        resolution = (
            f"Majority ({', '.join(agreeing)}) assess {majority_level.value} risk. "
            f"{dissenting[0]} dissents with {dissenter.risk_level.value} risk. "
            f"Leaning toward majority view but noting dissent for audit trail."
        )
        confidence_adj = -0.1
    else:
        resolution = (
            f"No clear consensus — agents are split across risk levels. "
            f"This ambiguity itself is a risk signal warranting human review."
        )
        confidence_adj = -0.25

    return DebateAnalysis(
        agreement_score=round(agreement_score, 3),
        agreeing_agents=agreeing,
        dissenting_agents=dissenting,
        points_of_contention=contention,
        resolution_reasoning=resolution,
        confidence_adjustment=confidence_adj,
    )
