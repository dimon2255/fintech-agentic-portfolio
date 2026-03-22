"""Pydantic data models for transaction risk classification.

Defines the core data structures for transactions, tool results,
and explainable risk assessments.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class RiskLevel(str, Enum):
    """Risk classification levels for transactions."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


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


class ReasoningStep(BaseModel):
    """A single step in the agent's reasoning chain."""

    signal: str = Field(description="The signal or factor being evaluated")
    observation: str = Field(description="What the agent observed")
    assessment: str = Field(description="The agent's assessment of this signal")
    risk_impact: str = Field(description="How this impacts overall risk: increases, decreases, or neutral")


class RiskAssessment(BaseModel):
    """Complete explainable risk assessment — the final agent output.

    Unlike a traditional Omniscore (single number), this provides
    full reasoning transparency for regulatory compliance and audit.
    """

    transaction_id: str = Field(description="Transaction being assessed")
    risk_level: RiskLevel = Field(description="Overall risk classification")
    confidence: float = Field(
        ge=0.0, le=1.0, description="Agent confidence in this assessment"
    )
    reasoning_chain: list[ReasoningStep] = Field(
        description="Step-by-step reasoning that led to this assessment"
    )
    recommended_action: str = Field(
        description="Recommended action: approve, review, decline"
    )
    summary: str = Field(
        description="Human-readable summary of the risk assessment"
    )
    tool_results: ToolResults = Field(
        description="Raw results from all analysis tools"
    )
    assessed_at: datetime = Field(
        default_factory=datetime.utcnow, description="When the assessment was made"
    )


class ToolResults(BaseModel):
    """Aggregated results from all analysis tools."""

    velocity: VelocityResult
    geo: GeoResult
    device: DeviceFingerprintResult
