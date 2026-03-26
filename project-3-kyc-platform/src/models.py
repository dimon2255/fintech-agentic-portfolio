"""Pydantic data models for the KYC/AML Compliance Platform.

Extends the multi-agent patterns from Project 2 with supervisor-orchestrated
compliance workflow models. Each specialist agent writes to its own state key
(state isolation pattern from P2).

Model hierarchy:
    KYCApplication (input)
    ├── DocumentSubmission (submitted documents)
    │
    ├── Document Intake Tools
    │   ├── DocumentExtractionResult
    │   ├── DocumentClassificationResult
    │   └── DocumentValidationResult
    │
    ├── Identity Verification Tools
    │   ├── NameMatchResult
    │   ├── AddressVerifyResult
    │   ├── DOBCrosscheckResult
    │   └── PEPCheckResult
    │
    ├── Sanctions Screening Tools
    │   ├── SanctionsHit
    │   ├── OFACScreenResult
    │   ├── EUSanctionsScreenResult
    │   ├── UNSanctionsScreenResult
    │   └── AdverseMediaResult
    │
    ├── Risk Assessment Tools
    │   ├── CountryRiskResult
    │   ├── IndustryRiskResult
    │   ├── TransactionPatternResult
    │   └── OverallRiskScoreResult
    │
    ├── Agent Results
    │   ├── DocumentIntakeResult
    │   ├── IdentityVerificationResult
    │   ├── SanctionsScreenResult
    │   └── RiskAssessmentResult
    │
    ├── Supervisor
    │   ├── SupervisorDecision
    │   └── ComplianceChecklist
    │
    └── ComplianceDecision (final output with full audit trail)
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

class RiskTier(str, Enum):
    """Risk classification tiers for KYC/AML assessment."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    PROHIBITED = "prohibited"


class ApplicationStatus(str, Enum):
    """Status of a KYC application through the compliance pipeline."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    APPROVED = "approved"
    REJECTED = "rejected"
    ESCALATED = "escalated"


class DocumentType(str, Enum):
    """Types of identity and address verification documents."""

    PASSPORT = "passport"
    DRIVERS_LICENSE = "drivers_license"
    NATIONAL_ID = "national_id"
    UTILITY_BILL = "utility_bill"
    BANK_STATEMENT = "bank_statement"
    BUSINESS_REGISTRATION = "business_registration"


class ChecklistStep(str, Enum):
    """Compliance pipeline steps tracked by the supervisor."""

    DOCUMENT_INTAKE = "document_intake"
    IDENTITY_VERIFICATION = "identity_verification"
    SANCTIONS_SCREENING = "sanctions_screening"
    RISK_ASSESSMENT = "risk_assessment"


# ============================================================
# Application input
# ============================================================

class DocumentSubmission(BaseModel):
    """A single submitted identity or address document."""

    document_type: DocumentType = Field(description="Type of document submitted")
    document_number: str = Field(description="Document number or identifier")
    issuing_country: str = Field(description="ISO country code of issuing authority")
    expiry_date: str | None = Field(
        default=None, description="ISO date string, None if document has no expiry"
    )
    holder_name: str = Field(description="Name as it appears on the document")
    holder_dob: str | None = Field(
        default=None, description="Date of birth on document, if present"
    )
    holder_address: str | None = Field(
        default=None, description="Address on document, if present"
    )


class KYCApplication(BaseModel):
    """Incoming KYC/AML application to evaluate."""

    application_id: str = Field(description="Unique application identifier")
    applicant_name: str = Field(description="Full legal name of the applicant")
    date_of_birth: str = Field(description="ISO date string for applicant DOB")
    nationality: str = Field(description="ISO country code of nationality")
    country_of_residence: str = Field(description="ISO country code of residence")
    address: str = Field(description="Full residential or business address")
    email: str = Field(description="Contact email address")
    phone: str = Field(description="Contact phone number")
    business_type: str | None = Field(
        default=None, description="Business type, None for individual applicants"
    )
    industry: str | None = Field(
        default=None, description="Industry sector, None for individuals"
    )
    expected_monthly_volume: float | None = Field(
        default=None, description="Expected monthly transaction volume in USD"
    )
    source_of_funds: str = Field(description="Declared source of funds")
    documents_submitted: list[DocumentSubmission] = Field(
        description="List of submitted identity/address documents"
    )
    submitted_at: datetime = Field(description="When the application was submitted")


# ============================================================
# Document Intake tool results
# ============================================================

class DocumentExtractionResult(BaseModel):
    """Result from document data extraction (OCR simulation)."""

    document_type: DocumentType = Field(description="Type of document processed")
    extracted_name: str = Field(description="Name extracted from the document")
    extracted_dob: str | None = Field(
        default=None, description="Date of birth extracted, if present"
    )
    extracted_address: str | None = Field(
        default=None, description="Address extracted, if present"
    )
    extracted_document_number: str = Field(
        description="Document number extracted"
    )
    extracted_expiry: str | None = Field(
        default=None, description="Expiry date extracted, if present"
    )
    extraction_confidence: float = Field(
        ge=0.0, le=1.0, description="OCR extraction confidence score"
    )


class DocumentClassificationResult(BaseModel):
    """Result from document type classification."""

    detected_type: DocumentType = Field(description="Detected document type")
    classification_confidence: float = Field(
        ge=0.0, le=1.0, description="Classification confidence score"
    )
    is_correct_type: bool = Field(
        description="Whether detected type matches submitted type"
    )


class DocumentValidationResult(BaseModel):
    """Result from document authenticity validation."""

    is_expired: bool = Field(description="Whether the document has expired")
    format_valid: bool = Field(description="Whether document format is valid")
    security_features_present: bool = Field(
        description="Whether expected security features are detected"
    )
    tampering_detected: bool = Field(
        description="Whether signs of document tampering are detected"
    )
    validation_score: float = Field(
        ge=0.0, le=1.0, description="Overall document validation score"
    )


# ============================================================
# Identity Verification tool results
# ============================================================

class NameMatchResult(BaseModel):
    """Result from name cross-reference matching."""

    application_name: str = Field(description="Name from the application")
    document_name: str = Field(description="Name from the document")
    match_score: float = Field(
        ge=0.0, le=1.0, description="Name match score (1.0 = exact match)"
    )
    match_method: str = Field(
        description="Matching method used: exact, fuzzy, or transliteration"
    )
    discrepancies: list[str] = Field(
        description="List of name discrepancies found"
    )


class AddressVerifyResult(BaseModel):
    """Result from address verification."""

    application_address: str = Field(description="Address from the application")
    document_address: str | None = Field(
        default=None, description="Address from the document, if available"
    )
    match_status: str = Field(
        description="Verification status: match, partial, mismatch, or not_available"
    )
    standardized_address: str | None = Field(
        default=None, description="Standardized version of the address"
    )


class DOBCrosscheckResult(BaseModel):
    """Result from date of birth cross-reference check."""

    application_dob: str = Field(description="DOB from the application")
    document_dob: str | None = Field(
        default=None, description="DOB from the document, if available"
    )
    match: bool = Field(description="Whether the DOB matches")
    age_years: int = Field(description="Calculated age in years")


class PEPCheckResult(BaseModel):
    """Result from Politically Exposed Person screening."""

    is_pep: bool = Field(description="Whether the applicant is flagged as a PEP")
    pep_tier: str | None = Field(
        default=None,
        description="PEP tier: head_of_state, senior_official, family_member, close_associate",
    )
    source: str | None = Field(
        default=None, description="Source of the PEP match"
    )
    match_confidence: float = Field(
        ge=0.0, le=1.0, description="PEP match confidence score"
    )


# ============================================================
# Sanctions Screening tool results
# ============================================================

class SanctionsHit(BaseModel):
    """A single match against a sanctions list."""

    list_name: str = Field(
        description="Sanctions list: OFAC_SDN, EU_CONSOLIDATED, or UN_CONSOLIDATED"
    )
    matched_name: str = Field(description="Name on the sanctions list that matched")
    match_score: float = Field(
        ge=0.0, le=1.0, description="Fuzzy match score"
    )
    entity_type: str = Field(description="Entity type: individual or entity")
    program: str | None = Field(
        default=None, description="Sanctions program, e.g. IRAN, SDGT, UKRAINE-EO13662"
    )


class OFACScreenResult(BaseModel):
    """Result from OFAC SDN list screening."""

    screened_name: str = Field(description="Name that was screened")
    hits: list[SanctionsHit] = Field(description="Matching entries found")
    is_clear: bool = Field(description="True if no significant matches found")


class EUSanctionsScreenResult(BaseModel):
    """Result from EU Consolidated sanctions list screening."""

    screened_name: str = Field(description="Name that was screened")
    hits: list[SanctionsHit] = Field(description="Matching entries found")
    is_clear: bool = Field(description="True if no significant matches found")


class UNSanctionsScreenResult(BaseModel):
    """Result from UN Consolidated sanctions list screening."""

    screened_name: str = Field(description="Name that was screened")
    hits: list[SanctionsHit] = Field(description="Matching entries found")
    is_clear: bool = Field(description="True if no significant matches found")


class AdverseMediaResult(BaseModel):
    """Result from adverse media screening."""

    screened_name: str = Field(description="Name that was screened")
    articles_found: int = Field(description="Number of adverse articles found")
    risk_categories: list[str] = Field(
        description="Risk categories found: fraud, corruption, money_laundering, etc."
    )
    highest_severity: str = Field(
        description="Highest severity level: none, low, medium, or high"
    )
    summary: str = Field(description="Brief summary of adverse media findings")


# ============================================================
# Risk Assessment tool results
# ============================================================

class CountryRiskResult(BaseModel):
    """Result from country risk lookup."""

    country_code: str = Field(description="ISO country code assessed")
    risk_tier: str = Field(
        description="Country risk tier: low, medium, high, or very_high"
    )
    fatf_status: str = Field(
        description="FATF status: member, monitored, blacklisted, or none"
    )
    corruption_index: float = Field(
        ge=0.0, le=100.0,
        description="Corruption perception index (0=highly corrupt, 100=very clean)",
    )


class IndustryRiskResult(BaseModel):
    """Result from industry risk assessment."""

    industry: str = Field(description="Industry assessed")
    risk_tier: str = Field(description="Industry risk tier: low, medium, or high")
    aml_exposure: str = Field(
        description="AML exposure level: minimal, moderate, or significant"
    )
    reasoning: str = Field(description="Why this industry has this risk level")


class TransactionPatternResult(BaseModel):
    """Result from expected transaction pattern analysis."""

    expected_monthly_volume: float = Field(
        description="Declared expected monthly volume in USD"
    )
    risk_tier: str = Field(
        description="Volume risk tier: normal, elevated, or suspicious"
    )
    structuring_risk: bool = Field(
        description="Whether volume suggests potential structuring"
    )
    volume_percentile: float = Field(
        ge=0.0, le=100.0,
        description="Volume percentile vs. similar businesses",
    )


class OverallRiskScoreResult(BaseModel):
    """Composite risk score aggregating all risk factors."""

    composite_score: float = Field(
        ge=0.0, le=1.0, description="Weighted composite risk score"
    )
    factor_breakdown: dict[str, float] = Field(
        description="Risk contribution per factor (factor_name -> score)"
    )
    risk_tier: RiskTier = Field(description="Derived risk tier from composite score")
    recommended_edd: bool = Field(
        description="Whether Enhanced Due Diligence is recommended"
    )


# ============================================================
# Reasoning (shared pattern from P1/P2)
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
# Agent result models
# ============================================================

class DocumentIntakeResult(BaseModel):
    """Output from the Document Intake agent."""

    agent_name: str = Field(default="document_intake")
    documents_processed: int = Field(description="Number of documents processed")
    extractions: list[DocumentExtractionResult] = Field(
        description="Extraction results per document"
    )
    classifications: list[DocumentClassificationResult] = Field(
        description="Classification results per document"
    )
    validations: list[DocumentValidationResult] = Field(
        description="Validation results per document"
    )
    overall_document_quality: float = Field(
        ge=0.0, le=1.0, description="Aggregate document quality score"
    )
    issues_found: list[str] = Field(description="List of document issues found")
    reasoning_chain: list[ReasoningStep] = Field(
        description="Step-by-step reasoning for document assessment"
    )


class IdentityVerificationResult(BaseModel):
    """Output from the Identity Verification agent."""

    agent_name: str = Field(default="identity_verification")
    name_match: NameMatchResult = Field(description="Name matching result")
    address_verify: AddressVerifyResult = Field(description="Address verification result")
    dob_crosscheck: DOBCrosscheckResult = Field(description="DOB cross-check result")
    pep_check: PEPCheckResult = Field(description="PEP screening result")
    identity_confirmed: bool = Field(
        description="Whether the applicant's identity is confirmed"
    )
    confidence: float = Field(
        ge=0.0, le=1.0, description="Overall identity verification confidence"
    )
    discrepancies: list[str] = Field(
        description="All discrepancies found across checks"
    )
    reasoning_chain: list[ReasoningStep] = Field(
        description="Step-by-step reasoning for identity assessment"
    )


class SanctionsScreeningResult(BaseModel):
    """Output from the Sanctions Screening agent."""

    agent_name: str = Field(default="sanctions_screening")
    ofac_result: OFACScreenResult = Field(description="OFAC SDN screening result")
    eu_result: EUSanctionsScreenResult = Field(description="EU sanctions result")
    un_result: UNSanctionsScreenResult = Field(description="UN sanctions result")
    adverse_media: AdverseMediaResult = Field(description="Adverse media result")
    any_hits: bool = Field(description="Whether any sanctions hits were found")
    highest_match_score: float = Field(
        ge=0.0, le=1.0, description="Highest match score across all lists"
    )
    reasoning_chain: list[ReasoningStep] = Field(
        description="Step-by-step reasoning for sanctions assessment"
    )


class RiskAssessmentResult(BaseModel):
    """Output from the Risk Assessment agent."""

    agent_name: str = Field(default="risk_assessment")
    country_risk: CountryRiskResult = Field(description="Country risk assessment")
    industry_risk: IndustryRiskResult = Field(description="Industry risk assessment")
    transaction_pattern: TransactionPatternResult = Field(
        description="Transaction pattern assessment"
    )
    overall_risk: OverallRiskScoreResult = Field(
        description="Composite risk score"
    )
    risk_tier: RiskTier = Field(description="Final risk tier")
    edd_recommended: bool = Field(
        description="Whether Enhanced Due Diligence is recommended"
    )
    reasoning_chain: list[ReasoningStep] = Field(
        description="Step-by-step reasoning for risk assessment"
    )


# ============================================================
# Supervisor models
# ============================================================

class SupervisorDecision(BaseModel):
    """Routing decision made by the supervisor after each agent completes."""

    next_step: str = Field(
        description="Next node to route to: a ChecklistStep value, final_decision, or human_review"
    )
    reasoning: str = Field(description="Why the supervisor chose this routing")
    skipped_steps: list[str] = Field(
        default_factory=list, description="Steps being skipped and why"
    )
    risk_flags_so_far: list[str] = Field(
        default_factory=list, description="Accumulated risk flags from completed steps"
    )


class ComplianceChecklist(BaseModel):
    """Tracks completion status of each compliance step."""

    document_intake: str = Field(
        default="pending",
        description="Status: pending, completed, skipped, or failed",
    )
    identity_verification: str = Field(
        default="pending",
        description="Status: pending, completed, skipped, or failed",
    )
    sanctions_screening: str = Field(
        default="pending",
        description="Status: pending, completed, skipped, or failed",
    )
    risk_assessment: str = Field(
        default="pending",
        description="Status: pending, completed, skipped, or failed",
    )
    completed_at: dict[str, str] = Field(
        default_factory=dict,
        description="Step -> ISO timestamp of completion",
    )


# ============================================================
# Audit trail
# ============================================================

class AuditEntry(BaseModel):
    """A single entry in the compliance audit trail."""

    timestamp: str = Field(description="ISO timestamp of this audit event")
    step: str = Field(description="Pipeline step this entry relates to")
    action: str = Field(description="Action taken: started, completed, skipped, escalated, etc.")
    details: str = Field(description="Human-readable details of what happened")
    agent_name: str | None = Field(
        default=None, description="Agent that produced this entry"
    )


# ============================================================
# Final compliance decision
# ============================================================

class ComplianceDecision(BaseModel):
    """Final KYC/AML compliance decision with full audit trail.

    This is the top-level output of Project 3. Unlike P2's SwarmAssessment
    (parallel specialists + debate), this captures a supervised sequential
    workflow: the supervisor's routing decisions, per-step results, and a
    regulatory-grade audit trail.
    """

    application_id: str = Field(description="Application being assessed")
    decision: str = Field(
        description="Final decision: approved, rejected, or escalated"
    )
    risk_tier: RiskTier = Field(description="Final risk tier")
    reasoning: str = Field(description="Human-readable summary of the decision")
    conditions: list[str] = Field(
        default_factory=list,
        description="Conditions attached to approval, e.g. Enhanced monitoring required",
    )

    # Full audit trail
    checklist: ComplianceChecklist = Field(
        description="Completion status of each pipeline step"
    )
    audit_trail: list[AuditEntry] = Field(
        description="Chronological audit trail of all events"
    )
    document_intake_result: DocumentIntakeResult | None = Field(
        default=None, description="Document Intake agent output"
    )
    identity_verification_result: IdentityVerificationResult | None = Field(
        default=None, description="Identity Verification agent output"
    )
    sanctions_screening_result: SanctionsScreeningResult | None = Field(
        default=None, description="Sanctions Screening agent output"
    )
    risk_assessment_result: RiskAssessmentResult | None = Field(
        default=None, description="Risk Assessment agent output"
    )
    supervisor_decisions: list[SupervisorDecision] = Field(
        default_factory=list,
        description="Log of all supervisor routing decisions",
    )

    # Metadata
    was_escalated: bool = Field(
        default=False, description="Whether this case was escalated to human review"
    )
    human_review_notes: str | None = Field(
        default=None, description="Human reviewer notes if escalated"
    )
    processing_time_ms: float | None = Field(
        default=None, description="End-to-end processing time in milliseconds"
    )
    decided_at: str = Field(description="ISO timestamp of when the decision was made")


# ============================================================
# LangGraph state
# ============================================================

class KYCState(TypedDict):
    """State that flows through the KYC compliance graph.

    The supervisor reads the current state and decides which agent to
    route to next. Each agent writes to its own result key (state
    isolation pattern from P2 — no merge conflicts).
    """

    messages: Annotated[list, add_messages]
    application: KYCApplication | None

    # Supervisor tracking
    checklist: ComplianceChecklist | None
    supervisor_decisions: list[SupervisorDecision]
    current_step: str | None
    audit_trail: list[AuditEntry]

    # Agent results (each agent writes exclusively to its own key)
    document_intake_result: DocumentIntakeResult | None
    identity_verification_result: IdentityVerificationResult | None
    sanctions_screening_result: SanctionsScreeningResult | None
    risk_assessment_result: RiskAssessmentResult | None

    # Final output
    compliance_decision: ComplianceDecision | None
