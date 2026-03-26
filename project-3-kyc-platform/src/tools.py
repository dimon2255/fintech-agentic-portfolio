"""KYC/AML analysis tools — synthetic implementations.

15 async tools grouped by agent, all following the P1/P2 pattern:
- Seeded RNG via hashlib.md5 for deterministic, reproducible output
- Simulated latency via asyncio.sleep(0.3) to mimic real API calls
- Pydantic return types for type safety at node boundaries

Tool groups:
    Document Intake (3):  document_extract, document_classify, document_validate
    Identity (4):         name_match, address_verify, dob_crosscheck, pep_check
    Sanctions (4):        ofac_screen, eu_sanctions_screen, un_sanctions_screen, adverse_media_check
    Risk (4):             country_risk_lookup, industry_risk_check, transaction_pattern_analysis, overall_risk_score

Orchestration helpers:
    run_document_intake_tools, run_identity_tools, run_sanctions_tools, run_risk_tools
"""

from __future__ import annotations

import asyncio
import hashlib
import random

from .models import (
    AddressVerifyResult,
    AdverseMediaResult,
    CountryRiskResult,
    DOBCrosscheckResult,
    DocumentClassificationResult,
    DocumentExtractionResult,
    DocumentSubmission,
    DocumentValidationResult,
    EUSanctionsScreenResult,
    IndustryRiskResult,
    KYCApplication,
    NameMatchResult,
    OFACScreenResult,
    OverallRiskScoreResult,
    PEPCheckResult,
    RiskTier,
    SanctionsHit,
    SanctionsScreeningResult,
    TransactionPatternResult,
    UNSanctionsScreenResult,
)

SIMULATED_LATENCY_SECONDS = 0.3


def _seed_rng(seed_str: str) -> random.Random:
    """Create a deterministic RNG from a string seed."""
    h = hashlib.md5(seed_str.encode()).hexdigest()
    return random.Random(int(h, 16))


# ============================================================
# Document Intake tools (3)
# ============================================================

async def document_extract(doc: DocumentSubmission) -> DocumentExtractionResult:
    """Extract key fields from a submitted document (OCR simulation)."""
    await asyncio.sleep(SIMULATED_LATENCY_SECONDS)
    rng = _seed_rng(f"extract_{doc.document_number}")

    # Simulate OCR quality — most docs extract well, some are poor
    base_confidence = rng.uniform(0.85, 0.99)
    # Expired or problematic docs have lower confidence
    if doc.expiry_date and doc.expiry_date < "2026-01-01":
        base_confidence = rng.uniform(0.40, 0.70)

    return DocumentExtractionResult(
        document_type=doc.document_type,
        extracted_name=doc.holder_name,
        extracted_dob=doc.holder_dob,
        extracted_address=doc.holder_address,
        extracted_document_number=doc.document_number,
        extracted_expiry=doc.expiry_date,
        extraction_confidence=round(base_confidence, 3),
    )


async def document_classify(doc: DocumentSubmission) -> DocumentClassificationResult:
    """Classify document type and verify it matches the submitted type."""
    await asyncio.sleep(SIMULATED_LATENCY_SECONDS)
    rng = _seed_rng(f"classify_{doc.document_type.value}_{doc.document_number}")

    confidence = rng.uniform(0.90, 0.99)
    is_correct = rng.random() > 0.05  # 95% correct classification

    return DocumentClassificationResult(
        detected_type=doc.document_type,
        classification_confidence=round(confidence, 3),
        is_correct_type=is_correct,
    )


async def document_validate(doc: DocumentSubmission) -> DocumentValidationResult:
    """Validate document authenticity — expiry, format, security features, tampering."""
    await asyncio.sleep(SIMULATED_LATENCY_SECONDS)
    rng = _seed_rng(f"validate_{doc.document_number}")

    is_expired = False
    if doc.expiry_date:
        is_expired = doc.expiry_date < "2026-03-26"

    format_valid = rng.random() > 0.05
    security_present = rng.random() > 0.10
    tampering = rng.random() < 0.03  # 3% tampering detection rate

    # Compute validation score
    score = 1.0
    if is_expired:
        score -= 0.4
    if not format_valid:
        score -= 0.2
    if not security_present:
        score -= 0.2
    if tampering:
        score -= 0.5
    score = max(0.0, min(1.0, score))

    return DocumentValidationResult(
        is_expired=is_expired,
        format_valid=format_valid,
        security_features_present=security_present,
        tampering_detected=tampering,
        validation_score=round(score, 3),
    )


# ============================================================
# Identity Verification tools (4)
# ============================================================

async def name_match(
    app: KYCApplication, extraction: DocumentExtractionResult
) -> NameMatchResult:
    """Cross-reference applicant name against extracted document name."""
    await asyncio.sleep(SIMULATED_LATENCY_SECONDS)
    rng = _seed_rng(f"name_{app.applicant_name}_{extraction.extracted_name}")

    app_name = app.applicant_name.strip().lower()
    doc_name = extraction.extracted_name.strip().lower()

    if app_name == doc_name:
        score = 1.0
        method = "exact"
        discrepancies = []
    else:
        # Check for common variations
        app_parts = set(app_name.split())
        doc_parts = set(doc_name.split())
        overlap = len(app_parts & doc_parts)
        total = max(len(app_parts), len(doc_parts))
        score = overlap / total if total > 0 else 0.0
        # Add some noise
        score = min(1.0, score + rng.uniform(-0.05, 0.10))
        score = max(0.0, score)
        method = "fuzzy"
        discrepancies = []
        if app_parts - doc_parts:
            discrepancies.append(
                f"Application has names not in document: {app_parts - doc_parts}"
            )
        if doc_parts - app_parts:
            discrepancies.append(
                f"Document has names not in application: {doc_parts - app_parts}"
            )

    return NameMatchResult(
        application_name=app.applicant_name,
        document_name=extraction.extracted_name,
        match_score=round(score, 3),
        match_method=method,
        discrepancies=discrepancies,
    )


async def address_verify(
    app: KYCApplication, extraction: DocumentExtractionResult
) -> AddressVerifyResult:
    """Verify applicant address against document address."""
    await asyncio.sleep(SIMULATED_LATENCY_SECONDS)
    rng = _seed_rng(f"addr_{app.address}_{extraction.extracted_address or 'none'}")

    doc_addr = extraction.extracted_address
    if not doc_addr:
        return AddressVerifyResult(
            application_address=app.address,
            document_address=None,
            match_status="not_available",
            standardized_address=None,
        )

    app_lower = app.address.strip().lower()
    doc_lower = doc_addr.strip().lower()

    if app_lower == doc_lower:
        status = "match"
    elif any(part in doc_lower for part in app_lower.split(",")[:2]):
        status = "partial"
    else:
        status = rng.choice(["partial", "mismatch"])

    return AddressVerifyResult(
        application_address=app.address,
        document_address=doc_addr,
        match_status=status,
        standardized_address=app.address.title(),
    )


async def dob_crosscheck(
    app: KYCApplication, extraction: DocumentExtractionResult
) -> DOBCrosscheckResult:
    """Cross-check date of birth between application and document."""
    await asyncio.sleep(SIMULATED_LATENCY_SECONDS)

    doc_dob = extraction.extracted_dob
    match = doc_dob is not None and app.date_of_birth == doc_dob

    # Calculate age from application DOB
    try:
        birth_parts = app.date_of_birth.split("-")
        birth_year = int(birth_parts[0])
        age = 2026 - birth_year
    except (ValueError, IndexError):
        age = 0

    return DOBCrosscheckResult(
        application_dob=app.date_of_birth,
        document_dob=doc_dob,
        match=match,
        age_years=age,
    )


async def pep_check(app: KYCApplication) -> PEPCheckResult:
    """Screen applicant against Politically Exposed Persons database."""
    await asyncio.sleep(SIMULATED_LATENCY_SECONDS)
    rng = _seed_rng(f"pep_{app.applicant_name}")

    # Certain name patterns trigger PEP hits for demo purposes
    name_lower = app.applicant_name.lower()
    pep_triggers = {
        "minister": ("senior_official", 0.92),
        "senator": ("senior_official", 0.88),
        "ambassador": ("senior_official", 0.90),
        "al-rashidi": ("family_member", 0.85),
        "petrov": ("close_associate", 0.72),
    }

    for trigger, (tier, confidence) in pep_triggers.items():
        if trigger in name_lower:
            return PEPCheckResult(
                is_pep=True,
                pep_tier=tier,
                source="Global PEP Database v3.2",
                match_confidence=confidence,
            )

    # Random low-probability PEP hit
    if rng.random() < 0.03:
        return PEPCheckResult(
            is_pep=True,
            pep_tier="close_associate",
            source="Regional PEP Supplement",
            match_confidence=round(rng.uniform(0.60, 0.75), 3),
        )

    return PEPCheckResult(
        is_pep=False,
        pep_tier=None,
        source=None,
        match_confidence=0.0,
    )


# ============================================================
# Sanctions Screening tools (4)
# ============================================================

# Synthetic sanctions entries for demo
_SYNTHETIC_SANCTIONS = [
    {"name": "Ahmad Al-Rashid", "list": "OFAC_SDN", "program": "SDGT", "type": "individual"},
    {"name": "Ahmed Al-Rashidi", "list": "OFAC_SDN", "program": "IRAN", "type": "individual"},
    {"name": "Ahmad Al-Rashidi", "list": "UN_CONSOLIDATED", "program": "IRAN", "type": "individual"},
    {"name": "Viktor Petrov", "list": "EU_CONSOLIDATED", "program": "UKRAINE", "type": "individual"},
    {"name": "Global Trade Corp", "list": "OFAC_SDN", "program": "DPRK", "type": "entity"},
    {"name": "Ahmad Rashidi", "list": "UN_CONSOLIDATED", "program": "ISIL", "type": "individual"},
]


def _fuzzy_name_score(name1: str, name2: str) -> float:
    """Fuzzy name matching using character-level similarity + word overlap.

    Combines Jaccard word overlap with character-level similarity to handle
    transliteration variants like "Al-Rashidi" vs "Al-Rashid".
    """
    n1 = name1.lower().replace("-", " ").replace(".", " ")
    n2 = name2.lower().replace("-", " ").replace(".", " ")
    s1 = set(n1.split())
    s2 = set(n2.split())
    if not s1 or not s2:
        return 0.0

    # Word-level Jaccard
    word_intersection = len(s1 & s2)
    word_union = len(s1 | s2)
    word_score = word_intersection / word_union if word_union > 0 else 0.0

    # Character bigram similarity for partial matches (handles transliteration)
    def bigrams(s: str) -> set:
        return {s[i:i+2] for i in range(len(s) - 1)} if len(s) > 1 else {s}

    b1 = bigrams(n1.replace(" ", ""))
    b2 = bigrams(n2.replace(" ", ""))
    char_intersection = len(b1 & b2)
    char_union = len(b1 | b2)
    char_score = char_intersection / char_union if char_union > 0 else 0.0

    # Weighted combination: character similarity matters more for transliteration
    return word_score * 0.4 + char_score * 0.6


def _screen_against_list(
    name: str, list_name: str, threshold: float = 0.4
) -> list[SanctionsHit]:
    """Screen a name against a specific sanctions list."""
    hits = []
    for entry in _SYNTHETIC_SANCTIONS:
        if entry["list"] != list_name:
            continue
        score = _fuzzy_name_score(name, entry["name"])
        if score >= threshold:
            hits.append(SanctionsHit(
                list_name=entry["list"],
                matched_name=entry["name"],
                match_score=round(score, 3),
                entity_type=entry["type"],
                program=entry["program"],
            ))
    return hits


async def ofac_screen(name: str, nationality: str) -> OFACScreenResult:
    """Screen against OFAC Specially Designated Nationals list."""
    await asyncio.sleep(SIMULATED_LATENCY_SECONDS)
    hits = _screen_against_list(name, "OFAC_SDN")
    return OFACScreenResult(
        screened_name=name,
        hits=hits,
        is_clear=len(hits) == 0,
    )


async def eu_sanctions_screen(name: str, nationality: str) -> EUSanctionsScreenResult:
    """Screen against EU Consolidated sanctions list."""
    await asyncio.sleep(SIMULATED_LATENCY_SECONDS)
    hits = _screen_against_list(name, "EU_CONSOLIDATED")
    return EUSanctionsScreenResult(
        screened_name=name,
        hits=hits,
        is_clear=len(hits) == 0,
    )


async def un_sanctions_screen(name: str, nationality: str) -> UNSanctionsScreenResult:
    """Screen against UN Consolidated sanctions list."""
    await asyncio.sleep(SIMULATED_LATENCY_SECONDS)
    hits = _screen_against_list(name, "UN_CONSOLIDATED")
    return UNSanctionsScreenResult(
        screened_name=name,
        hits=hits,
        is_clear=len(hits) == 0,
    )


async def adverse_media_check(name: str) -> AdverseMediaResult:
    """Screen for adverse media coverage."""
    await asyncio.sleep(SIMULATED_LATENCY_SECONDS)
    rng = _seed_rng(f"media_{name}")

    name_lower = name.lower()
    # Certain names trigger adverse media hits
    if "rashidi" in name_lower or "rashid" in name_lower:
        return AdverseMediaResult(
            screened_name=name,
            articles_found=rng.randint(3, 8),
            risk_categories=["money_laundering", "sanctions_evasion"],
            highest_severity="high",
            summary=f"Multiple articles found linking {name} to financial crime investigations.",
        )
    if "petrov" in name_lower:
        return AdverseMediaResult(
            screened_name=name,
            articles_found=rng.randint(1, 3),
            risk_categories=["corruption"],
            highest_severity="medium",
            summary=f"Articles found mentioning {name} in connection with government contracts.",
        )

    # Default: clean
    return AdverseMediaResult(
        screened_name=name,
        articles_found=0,
        risk_categories=[],
        highest_severity="none",
        summary=f"No adverse media found for {name}.",
    )


# ============================================================
# Risk Assessment tools (4)
# ============================================================

_COUNTRY_RISK_MAP = {
    # Low risk — FATF members, high CPI
    "US": ("low", "member", 69.0),
    "GB": ("low", "member", 73.0),
    "DE": ("low", "member", 79.0),
    "FR": ("low", "member", 72.0),
    "JP": ("low", "member", 73.0),
    "AU": ("low", "member", 75.0),
    "CA": ("low", "member", 74.0),
    "SG": ("low", "member", 83.0),
    # Medium risk
    "BR": ("medium", "member", 38.0),
    "MX": ("medium", "member", 31.0),
    "TR": ("medium", "monitored", 36.0),
    "IN": ("medium", "member", 40.0),
    "CN": ("medium", "member", 45.0),
    "SA": ("medium", "member", 53.0),
    # High risk — FATF monitored/blacklisted
    "NG": ("high", "monitored", 25.0),
    "PK": ("high", "monitored", 28.0),
    "MM": ("high", "monitored", 23.0),
    "YE": ("high", "none", 16.0),
    # Very high risk
    "IR": ("very_high", "blacklisted", 24.0),
    "KP": ("very_high", "blacklisted", 17.0),
    "SY": ("very_high", "blacklisted", 14.0),
    "AF": ("very_high", "blacklisted", 24.0),
}


async def country_risk_lookup(country_code: str) -> CountryRiskResult:
    """Look up country risk tier and FATF status."""
    await asyncio.sleep(SIMULATED_LATENCY_SECONDS)

    risk_tier, fatf, cpi = _COUNTRY_RISK_MAP.get(
        country_code.upper(), ("medium", "none", 50.0)
    )

    return CountryRiskResult(
        country_code=country_code.upper(),
        risk_tier=risk_tier,
        fatf_status=fatf,
        corruption_index=cpi,
    )


_INDUSTRY_RISK_MAP = {
    "cryptocurrency": ("high", "significant", "High AML exposure due to pseudonymous transactions and cross-border flows"),
    "gambling": ("high", "significant", "Cash-intensive industry with high money laundering risk"),
    "real_estate": ("medium", "moderate", "Used for money laundering through property purchases"),
    "precious_metals": ("medium", "moderate", "High-value portable assets attractive for laundering"),
    "import_export": ("medium", "moderate", "Trade-based money laundering risk"),
    "technology": ("low", "minimal", "Generally low AML risk with standard compliance needs"),
    "healthcare": ("low", "minimal", "Regulated industry with low laundering exposure"),
    "retail": ("low", "minimal", "Standard retail operations with normal transaction patterns"),
    "consulting": ("low", "minimal", "Professional services with traceable revenue streams"),
    "financial_services": ("medium", "moderate", "Inherent AML exposure as money service business"),
}


async def industry_risk_check(industry: str) -> IndustryRiskResult:
    """Assess industry-specific AML risk."""
    await asyncio.sleep(SIMULATED_LATENCY_SECONDS)

    risk_tier, exposure, reasoning = _INDUSTRY_RISK_MAP.get(
        industry.lower(),
        ("medium", "moderate", f"Industry '{industry}' assessed at moderate baseline risk"),
    )

    return IndustryRiskResult(
        industry=industry,
        risk_tier=risk_tier,
        aml_exposure=exposure,
        reasoning=reasoning,
    )


async def transaction_pattern_analysis(
    expected_volume: float, business_type: str | None
) -> TransactionPatternResult:
    """Analyze expected transaction patterns for risk signals."""
    await asyncio.sleep(SIMULATED_LATENCY_SECONDS)
    rng = _seed_rng(f"txn_{expected_volume}_{business_type}")

    # Structuring risk: volumes near reporting thresholds
    structuring_risk = 8000 <= expected_volume <= 12000

    # Volume risk tiers
    if expected_volume > 500_000:
        risk_tier = "suspicious"
        percentile = 98.0
    elif expected_volume > 100_000:
        risk_tier = "elevated"
        percentile = rng.uniform(85.0, 95.0)
    elif expected_volume > 50_000:
        risk_tier = "elevated" if business_type is None else "normal"
        percentile = rng.uniform(60.0, 80.0)
    else:
        risk_tier = "normal"
        percentile = rng.uniform(20.0, 60.0)

    return TransactionPatternResult(
        expected_monthly_volume=expected_volume,
        risk_tier=risk_tier,
        structuring_risk=structuring_risk,
        volume_percentile=round(percentile, 1),
    )


async def overall_risk_score(
    country: CountryRiskResult,
    industry: IndustryRiskResult,
    pattern: TransactionPatternResult,
    pep: PEPCheckResult,
    sanctions: SanctionsScreeningResult | None,
) -> OverallRiskScoreResult:
    """Compute weighted composite risk score from all factors."""
    await asyncio.sleep(SIMULATED_LATENCY_SECONDS)

    # Factor scores (0.0 = no risk, 1.0 = max risk)
    country_score = {"low": 0.1, "medium": 0.4, "high": 0.7, "very_high": 0.95}.get(
        country.risk_tier, 0.5
    )
    industry_score = {"low": 0.1, "medium": 0.4, "high": 0.75}.get(
        industry.risk_tier, 0.4
    )
    pattern_score = {"normal": 0.1, "elevated": 0.5, "suspicious": 0.85}.get(
        pattern.risk_tier, 0.4
    )
    pep_score = pep.match_confidence if pep.is_pep else 0.0

    sanctions_score = 0.0
    if sanctions and sanctions.any_hits:
        sanctions_score = sanctions.highest_match_score

    # Weighted formula
    weights = {
        "country": 0.25,
        "industry": 0.15,
        "transaction_pattern": 0.15,
        "pep": 0.20,
        "sanctions": 0.25,
    }
    factor_breakdown = {
        "country": round(country_score * weights["country"], 4),
        "industry": round(industry_score * weights["industry"], 4),
        "transaction_pattern": round(pattern_score * weights["transaction_pattern"], 4),
        "pep": round(pep_score * weights["pep"], 4),
        "sanctions": round(sanctions_score * weights["sanctions"], 4),
    }
    composite = sum(factor_breakdown.values())
    composite = round(min(1.0, composite), 4)

    # Derive risk tier
    if composite > 0.7 or sanctions_score > 0.8:
        tier = RiskTier.PROHIBITED
    elif composite > 0.45:
        tier = RiskTier.HIGH
    elif composite > 0.25:
        tier = RiskTier.MEDIUM
    else:
        tier = RiskTier.LOW

    # EDD recommendation
    recommended_edd = (
        tier in (RiskTier.HIGH, RiskTier.PROHIBITED)
        or pep.is_pep
        or (sanctions is not None and sanctions.any_hits)
    )

    return OverallRiskScoreResult(
        composite_score=composite,
        factor_breakdown=factor_breakdown,
        risk_tier=tier,
        recommended_edd=recommended_edd,
    )


# ============================================================
# Orchestration helpers — per-agent parallel tool execution
# ============================================================

async def run_document_intake_tools(
    documents: list[DocumentSubmission],
) -> dict:
    """Run document tools for all submitted documents in parallel."""
    extract_tasks = [document_extract(doc) for doc in documents]
    classify_tasks = [document_classify(doc) for doc in documents]
    validate_tasks = [document_validate(doc) for doc in documents]

    extractions, classifications, validations = await asyncio.gather(
        asyncio.gather(*extract_tasks),
        asyncio.gather(*classify_tasks),
        asyncio.gather(*validate_tasks),
    )

    return {
        "extractions": list(extractions),
        "classifications": list(classifications),
        "validations": list(validations),
    }


async def run_identity_tools(
    app: KYCApplication, primary_extraction: DocumentExtractionResult
) -> dict:
    """Run identity verification tools in parallel."""
    name_res, addr_res, dob_res, pep_res = await asyncio.gather(
        name_match(app, primary_extraction),
        address_verify(app, primary_extraction),
        dob_crosscheck(app, primary_extraction),
        pep_check(app),
    )

    return {
        "name_match": name_res,
        "address_verify": addr_res,
        "dob_crosscheck": dob_res,
        "pep_check": pep_res,
    }


async def run_sanctions_tools(name: str, nationality: str) -> dict:
    """Run all 4 sanctions screening tools in parallel."""
    ofac_res, eu_res, un_res, media_res = await asyncio.gather(
        ofac_screen(name, nationality),
        eu_sanctions_screen(name, nationality),
        un_sanctions_screen(name, nationality),
        adverse_media_check(name),
    )

    return {
        "ofac": ofac_res,
        "eu": eu_res,
        "un": un_res,
        "adverse_media": media_res,
    }


async def run_risk_tools(
    app: KYCApplication,
    pep: PEPCheckResult,
    sanctions: SanctionsScreeningResult | None,
) -> dict:
    """Run risk assessment tools in parallel, then compute overall score."""
    country_res, industry_res, pattern_res = await asyncio.gather(
        country_risk_lookup(app.country_of_residence),
        industry_risk_check(app.industry or "other"),
        transaction_pattern_analysis(
            app.expected_monthly_volume or 0.0, app.business_type
        ),
    )

    # Overall score depends on the parallel results
    overall_res = await overall_risk_score(
        country_res, industry_res, pattern_res, pep, sanctions
    )

    return {
        "country": country_res,
        "industry": industry_res,
        "pattern": pattern_res,
        "overall": overall_res,
    }
