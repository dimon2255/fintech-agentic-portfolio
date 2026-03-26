"""CLI entry point for the KYC/AML Compliance Platform.

Runs all 5 sample KYC applications through the supervisor-orchestrated
compliance pipeline and pretty-prints the results.
"""

from __future__ import annotations

import time

from .data_generator import (
    generate_borderline_application,
    generate_clean_application,
    generate_document_issues_application,
    generate_high_risk_application,
    generate_sanctions_hit_application,
)
from .graph import run_kyc_application
from .models import ComplianceDecision, RiskTier


# ============================================================
# Display helpers
# ============================================================

RISK_COLORS = {
    RiskTier.LOW: "\033[92m",       # green
    RiskTier.MEDIUM: "\033[93m",    # yellow
    RiskTier.HIGH: "\033[91m",      # red
    RiskTier.PROHIBITED: "\033[95m",  # magenta
}
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"


def _print_decision(decision: ComplianceDecision, elapsed: float) -> None:
    """Pretty-print a compliance decision."""
    color = RISK_COLORS.get(decision.risk_tier, "")

    print(f"\n{'=' * 70}")
    print(f"{BOLD}Application:{RESET} {decision.application_id}")
    print(f"{BOLD}Decision:{RESET}    {color}{decision.decision.upper()}{RESET}")
    print(f"{BOLD}Risk Tier:{RESET}   {color}{decision.risk_tier.value}{RESET}")
    print(f"{BOLD}Reasoning:{RESET}   {decision.reasoning}")

    if decision.conditions:
        print(f"{BOLD}Conditions:{RESET}")
        for c in decision.conditions:
            print(f"  - {c}")

    # Checklist
    cl = decision.checklist
    status_icons = {
        "completed": "\033[92m[done]\033[0m",
        "skipped": "\033[90m[skip]\033[0m",
        "pending": "\033[93m[----]\033[0m",
        "failed": "\033[91m[FAIL]\033[0m",
    }

    print(f"\n{BOLD}Compliance Checklist:{RESET}")
    for step_name, step_label in [
        ("document_intake", "Document Intake"),
        ("identity_verification", "Identity Verification"),
        ("sanctions_screening", "Sanctions Screening"),
        ("risk_assessment", "Risk Assessment"),
    ]:
        status = getattr(cl, step_name, "pending")
        icon = status_icons.get(status, "[??]")
        print(f"  {icon} {step_label}")

    # Supervisor decisions
    print(f"\n{BOLD}Supervisor Routing ({len(decision.supervisor_decisions)} decisions):{RESET}")
    for i, sd in enumerate(decision.supervisor_decisions, 1):
        print(f"  {DIM}{i}.{RESET} -> {sd.next_step}: {sd.reasoning}")
        if sd.skipped_steps:
            for skip in sd.skipped_steps:
                print(f"     {DIM}(skipped: {skip}){RESET}")

    # Key findings from agents
    if decision.document_intake_result and decision.document_intake_result.issues_found:
        print(f"\n{BOLD}Document Issues:{RESET}")
        for issue in decision.document_intake_result.issues_found:
            print(f"  - {issue}")

    if decision.identity_verification_result:
        iv = decision.identity_verification_result
        confirmed = "\033[92mconfirmed\033[0m" if iv.identity_confirmed else "\033[91mNOT confirmed\033[0m"
        print(f"\n{BOLD}Identity:{RESET} {confirmed} (confidence: {iv.confidence:.0%})")
        if iv.discrepancies:
            for d in iv.discrepancies:
                print(f"  - {d}")

    if decision.sanctions_screening_result:
        ss = decision.sanctions_screening_result
        if ss.any_hits:
            print(f"\n{BOLD}Sanctions:{RESET} \033[91mHITS FOUND\033[0m (highest: {ss.highest_match_score:.0%})")
        else:
            print(f"\n{BOLD}Sanctions:{RESET} \033[92mClear\033[0m")

    if decision.risk_assessment_result:
        ra = decision.risk_assessment_result
        print(f"\n{BOLD}Risk Score:{RESET} {ra.overall_risk.composite_score:.3f} -> {ra.risk_tier.value}")
        if ra.edd_recommended:
            print("  \033[93mEnhanced Due Diligence recommended\033[0m")

    print(f"\n{DIM}Processed in {elapsed:.2f}s | Audit trail: {len(decision.audit_trail)} entries{RESET}")
    print(f"{'=' * 70}")


# ============================================================
# Main
# ============================================================

async def main() -> None:
    """Run 5 sample KYC applications through the compliance pipeline."""
    print(f"\n{BOLD}{'=' * 70}")
    print("  KYC/AML Compliance Platform — Supervisor Architecture Demo")
    print("  Project 3: Agentic AI for Financial Services")
    print(f"{'=' * 70}{RESET}\n")

    profiles = [
        ("Clean Application (US Individual)", generate_clean_application),
        ("High-Risk Application (PEP + Crypto)", generate_high_risk_application),
        ("Sanctions Hit (Name Match)", generate_sanctions_hit_application),
        ("Document Issues (Expired + Mismatch)", generate_document_issues_application),
        ("Borderline Application (Ambiguous)", generate_borderline_application),
    ]

    for label, generator in profiles:
        app = generator()
        print(f"\n{BOLD}>>> Processing: {label}{RESET}")
        print(f"    Applicant: {app.applicant_name} | {app.nationality} | {app.country_of_residence}")
        if app.business_type:
            print(f"    Business: {app.business_type} ({app.industry}) | Volume: ${app.expected_monthly_volume:,.0f}/month")

        start = time.monotonic()
        result = await run_kyc_application(app)
        elapsed = time.monotonic() - start

        _print_decision(result["compliance_decision"], elapsed)

    print(f"\n{BOLD}All 5 applications processed.{RESET}\n")
