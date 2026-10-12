# Compliance Mapping — KYC/AML Regulations

This document maps the platform's capabilities to real-world compliance requirements.

## Bank Secrecy Act / AML (US)

| Requirement | Platform Coverage | Agent |
|------------|-------------------|-------|
| Customer Identification Program (CIP) | Document extraction + validation | Document Intake |
| Customer Due Diligence (CDD) | Identity verification, name matching, address verification | Identity Verification |
| Enhanced Due Diligence (EDD) | PEP screening, high-risk triggers, conditional EDD flag | Identity + Risk Assessment |
| Sanctions screening (OFAC SDN) | OFAC list screening with fuzzy matching | Sanctions Screening |
| Suspicious Activity Reporting (SAR) triggers | Risk flags, escalation to human review | Supervisor + Risk Assessment |
| Recordkeeping / audit trail | ComplianceDecision with a timestamped audit trail (in memory; persistence and tamper evidence not implemented) | All (via supervisor) |

## EU Anti-Money Laundering Directive (AMLD6)

| Requirement | Platform Coverage | Agent |
|------------|-------------------|-------|
| Risk-based approach | Composite risk scoring, tiered decisions (low/medium/high/prohibited) | Risk Assessment |
| Customer due diligence measures | Full document + identity pipeline | Document Intake + Identity |
| Enhanced due diligence for high-risk | PEP screening, EDD flag, conditions on approval | Identity + Risk Assessment |
| Beneficial ownership identification | Business type analysis (placeholder for UBO lookup) | Risk Assessment |
| Politically Exposed Persons (PEP) | PEP database screening with tier classification | Identity Verification |
| Third-country screening | Country risk lookup with FATF status | Risk Assessment |
| Record retention | Full JSON audit trail per application, returned with the decision (retention storage not implemented) | Final Decision |

## FATF Recommendations

| Recommendation | Platform Coverage |
|---------------|-------------------|
| R.10: Customer due diligence | Document + Identity agents |
| R.12: Politically exposed persons | PEP screening in Identity agent |
| R.19: Higher-risk countries | Country risk lookup with FATF blacklist/greylist |
| R.20: Suspicious transaction reporting | Escalation triggers → human review |
| R.22: Customer due diligence for DNFBPs | Industry risk assessment |

## CDD vs. EDD Decision Criteria

| Criteria | CDD (Standard) | EDD (Enhanced) |
|----------|----------------|----------------|
| Risk tier | Low or Medium | High |
| Country | FATF member, low-risk | FATF monitored/blacklisted |
| PEP status | Not PEP | PEP or PEP associate |
| Sanctions | Clear | Not yet a trigger: hits below 0.8 add no EDD conditions (see note below) |
| Industry | Low/medium AML exposure | High AML exposure (crypto, gambling) |
| Volume | Under thresholds | Above thresholds |

The platform automatically applies EDD conditions when:
- `risk_tier` = HIGH and `edd_recommended` = True
- PEP flag is set (any tier)

Sanctions hits between the 0.4 alert threshold and 0.8 do not add EDD conditions: the rules approve them with a
higher risk score and no review (golden-set scenario P3-05; a known gap that Claude mode escalates).

## Sanctions List Coverage

| List | Source | Screening Tool | Threshold |
|------|--------|---------------|-----------|
| OFAC SDN | US Treasury | `ofac_screen()` | 0.4 (fuzzy match) |
| EU Consolidated | European Commission | `eu_sanctions_screen()` | 0.4 (fuzzy match) |
| UN Consolidated | UN Security Council | `un_sanctions_screen()` | 0.4 (fuzzy match) |
| Adverse Media | News sources | `adverse_media_check()` | Severity rating |

Escalation trigger: Any sanctions hit with match score > 0.8 → immediate human review.

## Limitations (Synthetic Demo)

This is a demonstration platform using synthetic data. In production:
- Document extraction would use real OCR (Tesseract, AWS Textract, Azure Form Recognizer)
- Sanctions lists would use live feeds (Dow Jones, Refinitiv, ComplyAdvantage)
- PEP databases would use commercial providers (World-Check, LexisNexis)
- Identity verification would integrate with government databases and credit bureaus
- Adverse media would use NLP-powered news screening services
