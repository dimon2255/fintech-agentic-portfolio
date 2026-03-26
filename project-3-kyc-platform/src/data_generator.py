"""Synthetic KYC application generator.

Creates 5 application profiles with different risk characteristics:
    1. Clean application      — passes all checks, APPROVED
    2. High-risk application  — PEP + high-risk country + crypto, APPROVED with EDD or ESCALATED
    3. Sanctions hit           — name fuzzy-matches sanctions entry, ESCALATED
    4. Document issues         — expired passport + name mismatch, ESCALATED
    5. Borderline application — ambiguous signals, tests supervisor judgment

All data is synthetic — no real PII.
"""

from __future__ import annotations

import random
import uuid
from datetime import datetime

from .models import (
    DocumentSubmission,
    DocumentType,
    KYCApplication,
)


def _make_id() -> str:
    return f"KYC-{uuid.uuid4().hex[:8].upper()}"


# ============================================================
# Profile 1: Clean application
# ============================================================

def generate_clean_application(rng: random.Random | None = None) -> KYCApplication:
    """Low-risk domestic individual — should be APPROVED."""
    rng = rng or random.Random(42)

    return KYCApplication(
        application_id=_make_id(),
        applicant_name="Sarah Johnson",
        date_of_birth="1988-07-22",
        nationality="US",
        country_of_residence="US",
        address="742 Evergreen Terrace, Springfield, IL 62704",
        email="sarah.johnson@gmail.com",
        phone="+1-555-0123",
        business_type=None,
        industry=None,
        expected_monthly_volume=5000.0,
        source_of_funds="Employment salary",
        documents_submitted=[
            DocumentSubmission(
                document_type=DocumentType.PASSPORT,
                document_number="P98765432",
                issuing_country="US",
                expiry_date="2029-11-15",
                holder_name="Sarah Johnson",
                holder_dob="1988-07-22",
                holder_address=None,
            ),
            DocumentSubmission(
                document_type=DocumentType.UTILITY_BILL,
                document_number="UB-2025-44821",
                issuing_country="US",
                expiry_date=None,
                holder_name="Sarah Johnson",
                holder_dob=None,
                holder_address="742 Evergreen Terrace, Springfield, IL 62704",
            ),
        ],
        submitted_at=datetime(2026, 3, 25, 10, 30, 0),
    )


# ============================================================
# Profile 2: High-risk application
# ============================================================

def generate_high_risk_application(rng: random.Random | None = None) -> KYCApplication:
    """PEP family member, high-risk country, crypto industry — APPROVED with EDD or ESCALATED."""
    rng = rng or random.Random(101)

    return KYCApplication(
        application_id=_make_id(),
        applicant_name="Minister Fatima Al-Rashidi",
        date_of_birth="1975-03-12",
        nationality="NG",
        country_of_residence="NG",
        address="14 Victoria Island, Lagos, Nigeria",
        email="fatima.rashidi@outlook.com",
        phone="+234-801-555-0199",
        business_type="LLC",
        industry="cryptocurrency",
        expected_monthly_volume=250_000.0,
        source_of_funds="Business revenue from digital asset exchange",
        documents_submitted=[
            DocumentSubmission(
                document_type=DocumentType.PASSPORT,
                document_number="A08421573",
                issuing_country="NG",
                expiry_date="2030-02-28",
                holder_name="Minister Fatima Al-Rashidi",
                holder_dob="1975-03-12",
                holder_address=None,
            ),
            DocumentSubmission(
                document_type=DocumentType.BUSINESS_REGISTRATION,
                document_number="RC-2024-NG-88412",
                issuing_country="NG",
                expiry_date=None,
                holder_name="Minister Fatima Al-Rashidi",
                holder_dob=None,
                holder_address="14 Victoria Island, Lagos, Nigeria",
            ),
        ],
        submitted_at=datetime(2026, 3, 25, 11, 0, 0),
    )


# ============================================================
# Profile 3: Sanctions hit
# ============================================================

def generate_sanctions_hit_application(rng: random.Random | None = None) -> KYCApplication:
    """Name fuzzy-matches sanctions list entries — should be ESCALATED."""
    rng = rng or random.Random(202)

    return KYCApplication(
        application_id=_make_id(),
        applicant_name="Ahmad Al-Rashidi",
        date_of_birth="1982-11-05",
        nationality="IR",
        country_of_residence="TR",
        address="Ataturk Caddesi 55, Ankara, Turkey",
        email="a.rashidi@protonmail.com",
        phone="+90-312-555-0177",
        business_type=None,
        industry="import_export",
        expected_monthly_volume=75_000.0,
        source_of_funds="International trade profits",
        documents_submitted=[
            DocumentSubmission(
                document_type=DocumentType.PASSPORT,
                document_number="IR-7743219",
                issuing_country="IR",
                expiry_date="2028-08-20",
                holder_name="Ahmad Al-Rashidi",
                holder_dob="1982-11-05",
                holder_address=None,
            ),
            DocumentSubmission(
                document_type=DocumentType.UTILITY_BILL,
                document_number="TR-UTIL-2026-3321",
                issuing_country="TR",
                expiry_date=None,
                holder_name="Ahmad Al-Rashidi",
                holder_dob=None,
                holder_address="Ataturk Caddesi 55, Ankara, Turkey",
            ),
        ],
        submitted_at=datetime(2026, 3, 25, 12, 15, 0),
    )


# ============================================================
# Profile 4: Document issues
# ============================================================

def generate_document_issues_application(rng: random.Random | None = None) -> KYCApplication:
    """Expired passport + name mismatch between documents — should be ESCALATED."""
    rng = rng or random.Random(303)

    return KYCApplication(
        application_id=_make_id(),
        applicant_name="James Robert Thompson",
        date_of_birth="1990-01-30",
        nationality="GB",
        country_of_residence="GB",
        address="17 Baker Street, London, W1U 3BN",
        email="j.thompson@company.co.uk",
        phone="+44-20-7946-0958",
        business_type=None,
        industry=None,
        expected_monthly_volume=8000.0,
        source_of_funds="Employment salary",
        documents_submitted=[
            DocumentSubmission(
                document_type=DocumentType.PASSPORT,
                document_number="GB-5590128",
                issuing_country="GB",
                expiry_date="2024-06-30",  # EXPIRED
                holder_name="Jamie Robertson-Thompson",  # Significant name mismatch
                holder_dob="1990-01-30",
                holder_address=None,
            ),
            DocumentSubmission(
                document_type=DocumentType.BANK_STATEMENT,
                document_number="HSBC-2026-03-4412",
                issuing_country="GB",
                expiry_date=None,
                holder_name="James Robert Thompson",
                holder_dob=None,
                holder_address="17 Baker Street, London, W1U 3BN",
            ),
        ],
        submitted_at=datetime(2026, 3, 25, 14, 0, 0),
    )


# ============================================================
# Profile 5: Borderline application
# ============================================================

def generate_borderline_application(rng: random.Random | None = None) -> KYCApplication:
    """Ambiguous signals — partial address match, medium-risk country, borderline volume."""
    rng = rng or random.Random(404)

    return KYCApplication(
        application_id=_make_id(),
        applicant_name="Carlos Eduardo Silva",
        date_of_birth="1979-09-14",
        nationality="BR",
        country_of_residence="BR",
        address="Rua Augusta 1200, Sao Paulo, SP 01304-001",
        email="carlos.silva@empresa.com.br",
        phone="+55-11-9876-5432",
        business_type="Ltd",
        industry="real_estate",
        expected_monthly_volume=45_000.0,
        source_of_funds="Property management revenue",
        documents_submitted=[
            DocumentSubmission(
                document_type=DocumentType.NATIONAL_ID,
                document_number="BR-CPF-33298471055",
                issuing_country="BR",
                expiry_date="2031-12-31",
                holder_name="Carlos Eduardo Silva",
                holder_dob="1979-09-14",
                holder_address="Rua Augusta 1200, Apt 42, Sao Paulo",  # Slight address diff
            ),
            DocumentSubmission(
                document_type=DocumentType.UTILITY_BILL,
                document_number="CPFL-2026-SP-88123",
                issuing_country="BR",
                expiry_date=None,
                holder_name="Carlos E. Silva",  # Abbreviated middle name
                holder_dob=None,
                holder_address="Rua Augusta 1200, Sao Paulo, SP 01304-001",
            ),
        ],
        submitted_at=datetime(2026, 3, 25, 15, 30, 0),
    )


# ============================================================
# Batch generator
# ============================================================

def generate_test_batch() -> list[KYCApplication]:
    """Generate one of each profile for testing."""
    return [
        generate_clean_application(),
        generate_high_risk_application(),
        generate_sanctions_hit_application(),
        generate_document_issues_application(),
        generate_borderline_application(),
    ]
