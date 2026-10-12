"""Deterministic mock LLM functions for zero-cost development.

Each agent and the supervisor have a corresponding mock function that
produces realistic, rule-based output without calling any LLM API.

Functions:
    mock_supervisor_route     — Determines next routing step
    mock_document_intake      — Assesses document quality
    mock_identity_verify      — Assesses identity match
    mock_sanctions_screen     — Assesses sanctions exposure
    mock_risk_assess          — Assesses overall risk
"""

from __future__ import annotations

from datetime import datetime, timezone

from .models import (
    ComplianceChecklist,
    DocumentClassificationResult,
    DocumentExtractionResult,
    DocumentIntakeResult,
    DocumentValidationResult,
    IdentityVerificationResult,
    NameMatchResult,
    AddressVerifyResult,
    DOBCrosscheckResult,
    PEPCheckResult,
    OFACScreenResult,
    EUSanctionsScreenResult,
    UNSanctionsScreenResult,
    AdverseMediaResult,
    CountryRiskResult,
    IndustryRiskResult,
    OverallRiskScoreResult,
    ReasoningStep,
    RiskAssessmentResult,
    RiskTier,
    SanctionsScreeningResult,
    SupervisorDecision,
    TransactionPatternResult,
    KYCState,
)


# ============================================================
# Low-risk country set (formerly used to skip sanctions screening; unused)
# ============================================================

LOW_RISK_COUNTRIES = {"US", "GB", "DE", "FR", "JP", "AU", "CA", "SG"}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ============================================================
# Mock supervisor routing
# ============================================================

def mock_supervisor_route(state: KYCState) -> SupervisorDecision:
    """Deterministic supervisor routing based on checklist state and agent results."""
    checklist = state.get("checklist") or ComplianceChecklist()
    application = state["application"]

    step_order = [
        "document_intake",
        "identity_verification",
        "sanctions_screening",
        "risk_assessment",
    ]

    # Check for escalation triggers from completed steps
    risk_flags: list[str] = []
    skipped: list[str] = []

    # Document quality check
    doc_result = state.get("document_intake_result")
    if doc_result and doc_result.overall_document_quality < 0.3:
        risk_flags.append("Document quality critically low")
        return SupervisorDecision(
            next_step="human_review",
            reasoning="Document quality below threshold (< 0.3). Escalating to human review.",
            skipped_steps=skipped,
            risk_flags_so_far=risk_flags,
        )

    # Identity confirmation check
    identity_result = state.get("identity_verification_result")
    if identity_result and not identity_result.identity_confirmed:
        risk_flags.append("Identity not confirmed")
        return SupervisorDecision(
            next_step="human_review",
            reasoning="Identity verification failed. Applicant identity could not be confirmed.",
            skipped_steps=skipped,
            risk_flags_so_far=risk_flags,
        )

    # Sanctions hit check
    sanctions_result = state.get("sanctions_screening_result")
    if sanctions_result and sanctions_result.any_hits:
        if sanctions_result.highest_match_score > 0.8:
            risk_flags.append(f"Strong sanctions match (score={sanctions_result.highest_match_score})")
            return SupervisorDecision(
                next_step="human_review",
                reasoning=f"Strong sanctions match detected (score={sanctions_result.highest_match_score}). Immediate escalation required.",
                skipped_steps=skipped,
                risk_flags_so_far=risk_flags,
            )

    # Risk assessment auto-reject check
    risk_result = state.get("risk_assessment_result")
    if risk_result and risk_result.risk_tier == RiskTier.PROHIBITED:
        risk_flags.append("Risk tier: PROHIBITED")
        return SupervisorDecision(
            next_step="final_decision",
            reasoning="Risk tier is PROHIBITED. Auto-rejecting application.",
            skipped_steps=skipped,
            risk_flags_so_far=risk_flags,
        )

    # Collect accumulated risk flags
    if doc_result and doc_result.issues_found:
        risk_flags.extend(doc_result.issues_found)
    if identity_result:
        risk_flags.extend(identity_result.discrepancies)
    if sanctions_result and sanctions_result.any_hits:
        risk_flags.append(f"Sanctions hits found (highest score: {sanctions_result.highest_match_score})")

    # Sanctions screening is never skipped (the low-risk skip was removed)
    should_skip_sanctions = False  # screening is mandatory for every applicant

    # Find next pending step
    for step in step_order:
        status = getattr(checklist, step, "pending")
        if status == "pending":
            # Apply skip logic
            if step == "sanctions_screening" and should_skip_sanctions:
                skipped.append("sanctions_screening: Low-risk domestic individual, volume < $10K")
                continue
            return SupervisorDecision(
                next_step=step,
                reasoning=f"Proceeding to {step.replace('_', ' ')}.",
                skipped_steps=skipped,
                risk_flags_so_far=risk_flags,
            )

    # All steps completed or skipped
    return SupervisorDecision(
        next_step="final_decision",
        reasoning="All compliance steps completed. Routing to final decision.",
        skipped_steps=skipped,
        risk_flags_so_far=risk_flags,
    )


# ============================================================
# Mock Document Intake
# ============================================================

def mock_document_intake(
    extractions: list[DocumentExtractionResult],
    classifications: list[DocumentClassificationResult],
    validations: list[DocumentValidationResult],
) -> DocumentIntakeResult:
    """Deterministic document quality assessment."""
    reasoning: list[ReasoningStep] = []
    issues: list[str] = []

    # Assess each document
    for i, (ext, cls, val) in enumerate(zip(extractions, classifications, validations)):
        # Extraction quality
        if ext.extraction_confidence >= 0.85:
            reasoning.append(ReasoningStep(
                signal=f"Document {i+1} extraction",
                observation=f"Extraction confidence: {ext.extraction_confidence:.0%}",
                assessment="High-quality extraction, data is reliable",
                risk_impact="decreases",
            ))
        else:
            reasoning.append(ReasoningStep(
                signal=f"Document {i+1} extraction",
                observation=f"Low extraction confidence: {ext.extraction_confidence:.0%}",
                assessment="Poor quality extraction, data may be unreliable",
                risk_impact="increases",
            ))
            issues.append(f"Low extraction confidence on document {i+1}: {ext.extraction_confidence:.0%}")

        # Classification
        if not cls.is_correct_type:
            reasoning.append(ReasoningStep(
                signal=f"Document {i+1} classification",
                observation="Detected type does not match submitted type",
                assessment="Document type mismatch raises authenticity concerns",
                risk_impact="increases",
            ))
            issues.append(f"Document {i+1} type mismatch: submitted as {ext.document_type.value}")

        # Validation
        if val.is_expired:
            reasoning.append(ReasoningStep(
                signal=f"Document {i+1} expiry",
                observation="Document has expired",
                assessment="Expired document cannot be accepted for KYC verification",
                risk_impact="increases",
            ))
            issues.append(f"Document {i+1} ({ext.document_type.value}) is expired")

        if val.tampering_detected:
            reasoning.append(ReasoningStep(
                signal=f"Document {i+1} tampering",
                observation="Tampering indicators detected",
                assessment="Potential document fraud — critical risk flag",
                risk_impact="increases",
            ))
            issues.append(f"Tampering detected on document {i+1}")

        if not val.security_features_present:
            issues.append(f"Document {i+1} missing expected security features")

    # Overall quality
    avg_validation = sum(v.validation_score for v in validations) / len(validations) if validations else 0.0
    avg_extraction = sum(e.extraction_confidence for e in extractions) / len(extractions) if extractions else 0.0
    overall_quality = round((avg_validation * 0.6 + avg_extraction * 0.4), 3)

    return DocumentIntakeResult(
        documents_processed=len(extractions),
        extractions=extractions,
        classifications=classifications,
        validations=validations,
        overall_document_quality=overall_quality,
        issues_found=issues,
        reasoning_chain=reasoning,
    )


# ============================================================
# Mock Identity Verification
# ============================================================

def mock_identity_verify(
    name_res: NameMatchResult,
    address_res: AddressVerifyResult,
    dob_res: DOBCrosscheckResult,
    pep_res: PEPCheckResult,
) -> IdentityVerificationResult:
    """Deterministic identity verification assessment."""
    reasoning: list[ReasoningStep] = []
    discrepancies: list[str] = []

    # Name match assessment
    if name_res.match_score >= 0.95:
        reasoning.append(ReasoningStep(
            signal="Name verification",
            observation=f"Name match score: {name_res.match_score:.0%} ({name_res.match_method})",
            assessment="Strong name match confirms applicant identity",
            risk_impact="decreases",
        ))
    elif name_res.match_score >= 0.70:
        reasoning.append(ReasoningStep(
            signal="Name verification",
            observation=f"Name match score: {name_res.match_score:.0%} ({name_res.match_method})",
            assessment="Partial name match — minor discrepancies detected",
            risk_impact="neutral",
        ))
        discrepancies.extend(name_res.discrepancies)
    else:
        reasoning.append(ReasoningStep(
            signal="Name verification",
            observation=f"Name match score: {name_res.match_score:.0%}",
            assessment="Significant name mismatch — identity cannot be confirmed",
            risk_impact="increases",
        ))
        discrepancies.append(f"Name mismatch: '{name_res.application_name}' vs '{name_res.document_name}'")
        discrepancies.extend(name_res.discrepancies)

    # Address verification
    if address_res.match_status == "match":
        reasoning.append(ReasoningStep(
            signal="Address verification",
            observation="Application address matches document address",
            assessment="Address confirmed",
            risk_impact="decreases",
        ))
    elif address_res.match_status == "partial":
        reasoning.append(ReasoningStep(
            signal="Address verification",
            observation="Partial address match",
            assessment="Address partially matches — may need clarification",
            risk_impact="neutral",
        ))
        discrepancies.append("Partial address match between application and document")
    elif address_res.match_status == "mismatch":
        reasoning.append(ReasoningStep(
            signal="Address verification",
            observation="Address does not match",
            assessment="Address mismatch — potential identity concern",
            risk_impact="increases",
        ))
        discrepancies.append("Address mismatch between application and document")
    else:
        reasoning.append(ReasoningStep(
            signal="Address verification",
            observation="Address not available on document",
            assessment="Cannot verify address from this document type",
            risk_impact="neutral",
        ))

    # DOB cross-check
    if dob_res.match:
        reasoning.append(ReasoningStep(
            signal="Date of birth verification",
            observation=f"DOB matches: {dob_res.application_dob} (age: {dob_res.age_years})",
            assessment="DOB confirmed across application and document",
            risk_impact="decreases",
        ))
    elif dob_res.document_dob is None:
        reasoning.append(ReasoningStep(
            signal="Date of birth verification",
            observation="DOB not present on document",
            assessment="Cannot cross-check DOB from this document",
            risk_impact="neutral",
        ))
    else:
        reasoning.append(ReasoningStep(
            signal="Date of birth verification",
            observation=f"DOB mismatch: app={dob_res.application_dob}, doc={dob_res.document_dob}",
            assessment="DOB mismatch is a critical identity red flag",
            risk_impact="increases",
        ))
        discrepancies.append(f"DOB mismatch: {dob_res.application_dob} vs {dob_res.document_dob}")

    # PEP check
    if pep_res.is_pep:
        reasoning.append(ReasoningStep(
            signal="PEP screening",
            observation=f"PEP match: tier={pep_res.pep_tier}, confidence={pep_res.match_confidence:.0%}",
            assessment="Politically Exposed Person — Enhanced Due Diligence required",
            risk_impact="increases",
        ))
        discrepancies.append(f"PEP flag: {pep_res.pep_tier} (confidence: {pep_res.match_confidence:.0%})")
    else:
        reasoning.append(ReasoningStep(
            signal="PEP screening",
            observation="No PEP match found",
            assessment="Applicant is not a Politically Exposed Person",
            risk_impact="decreases",
        ))

    # Compute identity confirmed
    critical_failures = (
        name_res.match_score < 0.50
        or (dob_res.document_dob is not None and not dob_res.match)
    )
    identity_confirmed = not critical_failures

    # Confidence
    score_factors = [name_res.match_score]
    if dob_res.match:
        score_factors.append(1.0)
    elif dob_res.document_dob is not None:
        score_factors.append(0.2)
    if address_res.match_status == "match":
        score_factors.append(0.9)
    elif address_res.match_status == "partial":
        score_factors.append(0.6)
    elif address_res.match_status == "mismatch":
        score_factors.append(0.2)
    else:
        score_factors.append(0.5)

    confidence = round(sum(score_factors) / len(score_factors), 3)

    return IdentityVerificationResult(
        name_match=name_res,
        address_verify=address_res,
        dob_crosscheck=dob_res,
        pep_check=pep_res,
        identity_confirmed=identity_confirmed,
        confidence=confidence,
        discrepancies=discrepancies,
        reasoning_chain=reasoning,
    )


# ============================================================
# Mock Sanctions Screening
# ============================================================

def mock_sanctions_screen(
    ofac: OFACScreenResult,
    eu: EUSanctionsScreenResult,
    un: UNSanctionsScreenResult,
    adverse_media: AdverseMediaResult,
) -> SanctionsScreeningResult:
    """Deterministic sanctions screening assessment."""
    reasoning: list[ReasoningStep] = []

    # Collect all hits
    all_hits = ofac.hits + eu.hits + un.hits
    any_hits = len(all_hits) > 0
    highest_score = max((h.match_score for h in all_hits), default=0.0)

    # OFAC
    if ofac.is_clear:
        reasoning.append(ReasoningStep(
            signal="OFAC SDN screening",
            observation="No matches found on OFAC Specially Designated Nationals list",
            assessment="Clear on OFAC",
            risk_impact="decreases",
        ))
    else:
        for hit in ofac.hits:
            reasoning.append(ReasoningStep(
                signal="OFAC SDN screening",
                observation=f"Match: '{hit.matched_name}' (score: {hit.match_score:.0%}, program: {hit.program})",
                assessment="OFAC hit requires immediate escalation" if hit.match_score > 0.8 else "Potential OFAC match — requires review",
                risk_impact="increases",
            ))

    # EU
    if eu.is_clear:
        reasoning.append(ReasoningStep(
            signal="EU sanctions screening",
            observation="No matches on EU Consolidated sanctions list",
            assessment="Clear on EU sanctions",
            risk_impact="decreases",
        ))
    else:
        for hit in eu.hits:
            reasoning.append(ReasoningStep(
                signal="EU sanctions screening",
                observation=f"Match: '{hit.matched_name}' (score: {hit.match_score:.0%})",
                assessment="EU sanctions hit detected",
                risk_impact="increases",
            ))

    # UN
    if un.is_clear:
        reasoning.append(ReasoningStep(
            signal="UN sanctions screening",
            observation="No matches on UN Consolidated sanctions list",
            assessment="Clear on UN sanctions",
            risk_impact="decreases",
        ))
    else:
        for hit in un.hits:
            reasoning.append(ReasoningStep(
                signal="UN sanctions screening",
                observation=f"Match: '{hit.matched_name}' (score: {hit.match_score:.0%})",
                assessment="UN sanctions hit detected",
                risk_impact="increases",
            ))

    # Adverse media
    if adverse_media.highest_severity == "none":
        reasoning.append(ReasoningStep(
            signal="Adverse media check",
            observation="No adverse media found",
            assessment="Clean media profile",
            risk_impact="decreases",
        ))
    else:
        reasoning.append(ReasoningStep(
            signal="Adverse media check",
            observation=f"{adverse_media.articles_found} articles found, severity: {adverse_media.highest_severity}",
            assessment=adverse_media.summary,
            risk_impact="increases",
        ))

    return SanctionsScreeningResult(
        ofac_result=ofac,
        eu_result=eu,
        un_result=un,
        adverse_media=adverse_media,
        any_hits=any_hits,
        highest_match_score=round(highest_score, 3),
        reasoning_chain=reasoning,
    )


# ============================================================
# Mock Risk Assessment
# ============================================================

def mock_risk_assess(
    country: CountryRiskResult,
    industry: IndustryRiskResult,
    pattern: TransactionPatternResult,
    overall: OverallRiskScoreResult,
) -> RiskAssessmentResult:
    """Deterministic risk assessment."""
    reasoning: list[ReasoningStep] = []

    # Country risk
    reasoning.append(ReasoningStep(
        signal="Country risk",
        observation=f"{country.country_code}: tier={country.risk_tier}, FATF={country.fatf_status}, CPI={country.corruption_index}",
        assessment=f"Country risk is {country.risk_tier}" + (
            " — FATF blacklisted country" if country.fatf_status == "blacklisted"
            else " — FATF monitored" if country.fatf_status == "monitored"
            else ""
        ),
        risk_impact="increases" if country.risk_tier in ("high", "very_high") else "neutral" if country.risk_tier == "medium" else "decreases",
    ))

    # Industry risk
    reasoning.append(ReasoningStep(
        signal="Industry risk",
        observation=f"{industry.industry}: tier={industry.risk_tier}, AML exposure={industry.aml_exposure}",
        assessment=industry.reasoning,
        risk_impact="increases" if industry.risk_tier == "high" else "neutral" if industry.risk_tier == "medium" else "decreases",
    ))

    # Transaction patterns
    if pattern.structuring_risk:
        reasoning.append(ReasoningStep(
            signal="Transaction patterns",
            observation=f"Expected volume ${pattern.expected_monthly_volume:,.0f}/month (percentile: {pattern.volume_percentile:.0f}th)",
            assessment="Volume near reporting threshold — potential structuring risk",
            risk_impact="increases",
        ))
    elif pattern.risk_tier == "suspicious":
        reasoning.append(ReasoningStep(
            signal="Transaction patterns",
            observation=f"Expected volume ${pattern.expected_monthly_volume:,.0f}/month (percentile: {pattern.volume_percentile:.0f}th)",
            assessment="Unusually high expected volume for this profile",
            risk_impact="increases",
        ))
    else:
        reasoning.append(ReasoningStep(
            signal="Transaction patterns",
            observation=f"Expected volume ${pattern.expected_monthly_volume:,.0f}/month (percentile: {pattern.volume_percentile:.0f}th)",
            assessment=f"Transaction volume is {pattern.risk_tier} for this profile",
            risk_impact="decreases" if pattern.risk_tier == "normal" else "neutral",
        ))

    # Overall composite
    reasoning.append(ReasoningStep(
        signal="Composite risk score",
        observation=f"Score: {overall.composite_score:.3f}, Tier: {overall.risk_tier.value}",
        assessment=f"Overall risk tier: {overall.risk_tier.value}" + (
            " — Enhanced Due Diligence recommended" if overall.recommended_edd else ""
        ),
        risk_impact="increases" if overall.risk_tier in (RiskTier.HIGH, RiskTier.PROHIBITED) else "neutral" if overall.risk_tier == RiskTier.MEDIUM else "decreases",
    ))

    return RiskAssessmentResult(
        country_risk=country,
        industry_risk=industry,
        transaction_pattern=pattern,
        overall_risk=overall,
        risk_tier=overall.risk_tier,
        edd_recommended=overall.recommended_edd,
        reasoning_chain=reasoning,
    )
