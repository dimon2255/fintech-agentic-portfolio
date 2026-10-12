# Project 3: KYC/AML Compliance Platform

**Supervisor-orchestrated KYC/AML compliance pipeline with conditional routing, skip logic, and human-in-the-loop escalation.**

## The Problem

KYC (Know Your Customer) and AML (Anti-Money Laundering) compliance is a major cost center for financial institutions. Manual review costs $15-50 per application, takes 2-5 business days, and suffers from inconsistent rule application and analyst fatigue. Meanwhile, regulators demand comprehensive audit trails and explainable decisions.

Existing automation tools (ComplyAdvantage, Refinitiv World-Check) handle screening but don't orchestrate the end-to-end compliance workflow — the sequencing, conditional logic, and escalation decisions still require human judgment.

## The Approach

A supervisor-orchestrated multi-agent system where a central **supervisor** dynamically routes applications through four specialist agents:

1. **Document Intake** — Extracts, classifies, and validates submitted identity documents
2. **Identity Verification** — Cross-references applicant data against document data, screens for PEPs
3. **Sanctions Screening** — Screens against OFAC SDN, EU, and UN sanctions lists plus adverse media
4. **Risk Assessment** — Computes composite risk score from country, industry, transaction, PEP, and sanctions factors

The supervisor uses LangGraph's `add_conditional_edges` to make runtime routing decisions:
- **Skip logic:** Low-risk domestic individuals skip sanctions screening (~20% cost savings)
- **Escalation:** Document failures, identity failures, or strong sanctions matches trigger human review
- **Auto-reject:** Prohibited risk tier is automatically rejected

```
START → supervisor ──[conditional]──→ document_intake ──→ supervisor
                    ├──→ identity_verification ──→ supervisor
                    ├──→ sanctions_screening ──→ supervisor  (may be SKIPPED)
                    ├──→ risk_assessment ──→ supervisor
                    ├──→ human_review ──→ final_decision ──→ END
                    └──→ final_decision ──→ END
```

## Portfolio Progression

This is Project 3 of 3, showing the architectural journey:

| Project | Topology | Key Feature |
|---------|----------|-------------|
| [P1: Risk Classifier](../project-1-risk-classifier/) | Linear (2 nodes) | Single agent, async tools |
| [P2: Fraud Swarm](../project-2-fraud-swarm/) | Fan-out/fan-in (5 nodes) | Parallel specialists + adjudicator debate |
| **P3: KYC/AML Platform** | **Supervisor hub-and-spoke (7 nodes)** | **Conditional routing, skip logic, escalation** |

The key insight: P2's adjudicator is a **terminal reducer** (runs once after all agents). P3's supervisor is a **cyclic orchestrator** (runs after each agent, dynamically deciding what comes next).

## Quick Start

```bash
# From repo root
pip install -e ".[dev]"

# Copy env file
cp project-3-kyc-platform/.env.example project-3-kyc-platform/.env

# Run CLI demo (5 application profiles)
cd project-3-kyc-platform
python -m src.main

# Run Streamlit dashboard
streamlit run project-3-kyc-platform/app.py
```

No API key needed — runs with deterministic mock LLM by default.

## Sample Output

```
Clean (US Individual):     APPROVED  | tier=low        | sanctions=skipped
High-Risk (PEP + Crypto): APPROVED  | tier=high       | EDD conditions applied
Sanctions Hit:             REJECTED  | tier=prohibited | escalated, then rejected
Document Issues:           ESCALATED | tier=high       | identity not confirmed
Borderline:                APPROVED  | tier=low        | all steps completed
```

**Measured decision quality:** the repository-level [golden-set evaluation](../docs/evals/golden-set-report.md)
replays 14 labeled applications (built on the five profiles above plus nine new cases) through this pipeline and grades the decision,
risk tier, escalation, sanctions screening and EDD conditions against compliance-analyst labels.

## Trade-offs

### Why supervisor hub-and-spoke over fan-out?
KYC has **stage dependencies** — you can't verify identity until documents are processed. Fan-out (P2's pattern) can't express this. The supervisor pattern adds complexity (cyclic graph, more LLM calls) but correctly models real compliance workflows.

### Why conditional routing over static edges?
Static routing means every application runs every agent. With conditional routing, low-risk domestic applicants skip sanctions screening (saves ~20% of cost), and problematic applications escalate early (saves 60-75% when documents fail).

### Why mock LLM by default?
Zero-cost development and deterministic demo output. Real LLM mode activates by adding an API key to `.env`. The mock functions implement the same business logic the LLM would produce, validated through extensive testing.

## What I'd Do Differently

1. **Parallel where possible** — Some stages could run in parallel (sanctions screening doesn't actually depend on identity verification). A hybrid topology with selective parallelism would reduce latency.
2. **LangGraph interrupt()** — The human review node currently auto-resolves. In production, `interrupt()` would pause the graph and wait for real human input via a web form.
3. **Streaming** — Stream supervisor routing decisions to the UI as they happen, rather than waiting for the full pipeline to complete.
4. **Confidence calibration** — The mock functions produce well-calibrated scores. Real LLM mode would need prompt engineering to achieve similar calibration.
5. **Batch sanctions screening** — In production, screen multiple applicants against sanctions lists in a single API call for efficiency.

## Architecture

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for diagrams and design decisions.

## Costs

See [docs/costs.md](docs/costs.md) for per-application cost breakdown and scaling projections.

## Compliance

See [docs/compliance-mapping.md](docs/compliance-mapping.md) for mapping to BSA/AML, AMLD6, and FATF requirements.

## Business Case

See [docs/business-case.md](docs/business-case.md) for TCO model and ROI projections.

## Tech Stack

- **Framework:** LangGraph (conditional routing via `add_conditional_edges`)
- **Language:** Python 3.11+ with async/await
- **Data Models:** Pydantic v2 (strict validation)
- **Dashboard:** Streamlit
- **LLM:** Model-agnostic (Anthropic Claude / OpenAI GPT via `DEFAULT_MODEL` env var)
