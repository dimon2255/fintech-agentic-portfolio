"""Pydantic data models for the Fraud Detection Swarm.

Extends Project 1's models with multi-agent verdict structures,
debate analysis, escalation context, and the complete swarm assessment.

Model hierarchy:
    Transaction (input)
    ├── VelocityResult, GeoResult, DeviceFingerprintResult (P1 tools)
    ├── IdentitySignals, BehavioralSignals (new P2 tools)
    ├── SpecialistVerdict (each agent's output)
    ├── DebateAnalysis (adjudicator's disagreement analysis)
    ├── EscalationContext (what the human reviewer sees)
    ├── HumanDecision (human reviewer's response)
    └── SwarmAssessment (final output with full audit trail)
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Annotated, TypedDict

from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field


# ============================================================
# Core enums
# ============================================================

class RiskLevel(str, Enum):
    """Risk classification levels for transactions."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# ============================================================
# Transaction input (copied from P1)
# ============================================================

class Transaction(BaseModel):
    """Incoming transaction to evaluate."""

    transaction_id: str = Field(description="Unique transaction identifier")
    amount: float = Field(description="Transaction amount in USD")
    currency: str = Field(default="USD", description="Transaction currency")
    merchant_category: str = Field(description="Merchant category code or name")
    customer_id: str = Field(description="Customer identifier")
    customer_email: str = Field(description="Customer email address")
    ip_address: str = Field(description="IP address of the transaction origin")
    device_id: str = Field(description="Device fingerprint identifier")
    timestamp: datetime = Field(description="Transaction timestamp")
    card_last_four: str = Field(description="Last four digits of payment card")
    billing_country: str = Field(description="Billing address country code")
    shipping_country: str | None = Field(
        default=None, description="Shipping address country code"
    )


# ============================================================
# Tool results — P1 tools (copied)
# ============================================================

class VelocityResult(BaseModel):
    """Result from velocity pattern analysis tool."""

    transactions_last_hour: int = Field(description="Number of transactions in last hour")
    transactions_last_24h: int = Field(description="Number of transactions in last 24 hours")
    avg_transaction_amount_30d: float = Field(
        description="Average transaction amount over 30 days"
    )
    amount_deviation_factor: float = Field(
        description="How many standard deviations from the mean this amount is"
    )
    rapid_succession_flag: bool = Field(
        description="Whether transactions are happening in rapid succession"
    )
    velocity_risk_score: float = Field(
        ge=0.0, le=1.0, description="Velocity-based risk score (0=safe, 1=high risk)"
    )


class GeoResult(BaseModel):
    """Result from geolocation analysis tool."""

    ip_country: str = Field(description="Country resolved from IP address")
    ip_city: str = Field(description="City resolved from IP address")
    is_vpn: bool = Field(description="Whether the IP is a known VPN/proxy")
    is_tor: bool = Field(description="Whether the IP is a known Tor exit node")
    billing_geo_match: bool = Field(
        description="Whether IP geo matches billing country"
    )
    distance_from_usual_km: float = Field(
        description="Distance from customer's usual transaction location"
    )
    geo_risk_score: float = Field(
        ge=0.0, le=1.0, description="Geo-based risk score (0=safe, 1=high risk)"
    )


class DeviceFingerprintResult(BaseModel):
    """Result from device fingerprint analysis tool."""

    device_known: bool = Field(
        description="Whether this device has been seen before for this customer"
    )
    device_age_days: int = Field(
        description="How many days since this device was first seen"
    )
    device_trust_score: float = Field(
        ge=0.0, le=1.0, description="Device trust score (0=untrusted, 1=fully trusted)"
    )
    multiple_accounts_on_device: bool = Field(
        description="Whether multiple customer accounts use this device"
    )
    os_fingerprint_changed: bool = Field(
        description="Whether the OS/browser fingerprint changed since last seen"
    )
    device_risk_score: float = Field(
        ge=0.0, le=1.0, description="Device-based risk score (0=safe, 1=high risk)"
    )


class ToolResults(BaseModel):
    """Aggregated results from P1 analysis tools."""

    velocity: VelocityResult
    geo: GeoResult
    device: DeviceFingerprintResult


# ============================================================
# Tool results — P2 new tools
# ============================================================

class IdentitySignals(BaseModel):
    """Results from identity graph analysis."""

    email_age_days: int = Field(description="How old the email address is")
    email_domain_reputation: str = Field(
        description="Email domain reputation: trusted, suspicious, or disposable"
    )
    name_email_match_score: float = Field(
        ge=0.0, le=1.0, description="How well the name matches the email pattern"
    )
    phone_verified: bool = Field(description="Whether phone number has been verified")
    address_verification_status: str = Field(
        description="Address verification: match, partial, mismatch, or unknown"
    )
    linked_accounts_count: int = Field(
        description="Number of accounts linked to this identity"
    )
    previous_chargebacks: int = Field(
        description="Number of previous chargebacks on this identity"
    )
    account_age_days: int = Field(description="Age of the customer account in days")
    identity_risk_score: float = Field(
        ge=0.0, le=1.0, description="Identity-based risk score (0=safe, 1=high risk)"
    )


class BehavioralSignals(BaseModel):
    """Results from behavioral anomaly detection."""

    session_duration_seconds: int = Field(
        description="How long the user has been in this session"
    )
    pages_visited: int = Field(description="Number of pages visited in this session")
    checkout_speed_seconds: int = Field(
        description="Time from adding to cart to payment submission"
    )
    typing_pattern_anomaly: bool = Field(
        description="Whether typing cadence deviates from normal human patterns"
    )
    mouse_movement_anomaly: bool = Field(
        description="Whether mouse movement looks bot-like or scripted"
    )
    time_of_day_unusual: bool = Field(
        description="Whether this transaction time is unusual for the customer"
    )
    navigation_pattern: str = Field(
        description="Navigation pattern: normal, direct_to_checkout, or erratic"
    )
    behavioral_risk_score: float = Field(
        ge=0.0, le=1.0, description="Behavioral risk score (0=safe, 1=high risk)"
    )


# ============================================================
# Reasoning (shared by P1 and P2)
# ============================================================

class ReasoningStep(BaseModel):
    """A single step in an agent's reasoning chain."""

    signal: str = Field(description="The signal or factor being evaluated")
    observation: str = Field(description="What the agent observed")
    assessment: str = Field(description="The agent's assessment of this signal")
    risk_impact: str = Field(
        description="How this impacts overall risk: increases, decreases, or neutral"
    )


# ============================================================
# Specialist agent output
# ============================================================

class SpecialistVerdict(BaseModel):
    """Output from a single specialist agent's analysis."""

    agent_name: str = Field(description="Specialist agent identifier")
    risk_score: float = Field(ge=0.0, le=1.0, description="Agent's risk assessment")
    risk_level: RiskLevel = Field(description="Categorical risk classification")
    confidence: float = Field(ge=0.0, le=1.0, description="How confident the agent is")
    reasoning_chain: list[ReasoningStep] = Field(
        description="Step-by-step reasoning that led to this verdict"
    )
    key_findings: list[str] = Field(
        description="Top bullet findings for debate context"
    )
    recommended_action: str = Field(
        description="Recommended action: approve, review, or decline"
    )


# ============================================================
# Adjudicator / debate models
# ============================================================

class DebateAnalysis(BaseModel):
    """Adjudicator's analysis of specialist agreement/disagreement."""

    agreement_score: float = Field(
        ge=0.0, le=1.0,
        description="1.0 = unanimous, 0.0 = total disagreement",
    )
    agreeing_agents: list[str] = Field(description="Which agents agree on risk level")
    dissenting_agents: list[str] = Field(description="Which agents disagree")
    points_of_contention: list[str] = Field(
        description="What the agents disagree about"
    )
    resolution_reasoning: str = Field(
        description="How the adjudicator resolved the disagreement"
    )
    confidence_adjustment: float = Field(
        description="How disagreement affected confidence (negative = lowered)"
    )


# ============================================================
# Human-in-the-loop models
# ============================================================

class EscalationContext(BaseModel):
    """Context provided to human reviewer during escalation."""

    escalation_reason: str = Field(description="Why this case was escalated")
    transaction_summary: str = Field(description="Human-readable transaction summary")
    specialist_verdicts: list[SpecialistVerdict] = Field(
        description="All specialist verdicts for review"
    )
    debate_analysis: DebateAnalysis = Field(
        description="The adjudicator's debate analysis"
    )
    adjudicator_preliminary: str = Field(
        description="What the adjudicator was leaning toward"
    )
    suggested_action: str = Field(
        description="Suggested action: approve, decline, or investigate_further"
    )


class HumanDecision(BaseModel):
    """Human reviewer's decision after escalation."""

    action: str = Field(description="Decision: approve, decline, or investigate_further")
    override_reason: str | None = Field(
        default=None, description="Reason if overriding the adjudicator"
    )
    reviewer_id: str = Field(default="human_reviewer", description="Reviewer identifier")
    reviewed_at: datetime = Field(
        default_factory=datetime.utcnow, description="When the review was completed"
    )


# ============================================================
# Final swarm output
# ============================================================

class SwarmAssessment(BaseModel):
    """Complete multi-agent fraud assessment with full audit trail.

    This is the top-level output of Project 2. Unlike P1's RiskAssessment
    (single agent reasoning), this captures the full multi-agent debate:
    specialist verdicts, disagreement analysis, and optional human override.
    """

    transaction_id: str = Field(description="Transaction being assessed")
    risk_level: RiskLevel = Field(description="Final risk classification")
    confidence: float = Field(
        ge=0.0, le=1.0, description="Final confidence after debate adjustment"
    )
    recommended_action: str = Field(
        description="Final action: approve, review, or decline"
    )
    summary: str = Field(description="Human-readable summary of the swarm assessment")

    # Multi-agent audit trail
    specialist_verdicts: list[SpecialistVerdict] = Field(
        description="Each specialist agent's independent verdict"
    )
    debate_analysis: DebateAnalysis = Field(
        description="Adjudicator's analysis of agent agreement/disagreement"
    )
    was_escalated: bool = Field(
        default=False, description="Whether this case was escalated to a human"
    )
    human_decision: HumanDecision | None = Field(
        default=None, description="Human decision if escalated"
    )

    # Raw data
    tool_results: ToolResults = Field(description="Raw P1 tool results")
    identity_signals: IdentitySignals = Field(description="Identity graph signals")
    behavioral_signals: BehavioralSignals = Field(description="Behavioral signals")
    assessed_at: datetime = Field(
        default_factory=datetime.utcnow, description="When the assessment completed"
    )
    processing_time_ms: float | None = Field(
        default=None, description="End-to-end processing time in milliseconds"
    )


# ============================================================
# LangGraph state
# ============================================================

class SwarmState(TypedDict):
    """State that flows through the fraud detection swarm graph.

    Each specialist writes to its own verdict key — no merge conflicts.
    The adjudicator reads all three, then routes to human or final decision.
    """

    messages: Annotated[list, add_messages]
    transaction: Transaction | None

    # Tool results (populated by gather_all_signals node)
    tool_results: ToolResults | None
    identity_signals: IdentitySignals | None
    behavioral_signals: BehavioralSignals | None

    # Specialist verdicts (each specialist writes exactly one)
    velocity_verdict: SpecialistVerdict | None
    identity_verdict: SpecialistVerdict | None
    behavioral_verdict: SpecialistVerdict | None

    # Adjudicator output
    debate_analysis: DebateAnalysis | None

    # Escalation
    escalation_context: EscalationContext | None
    human_decision: HumanDecision | None

    # Final output
    final_assessment: SwarmAssessment | None
