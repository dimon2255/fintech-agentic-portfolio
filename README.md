# Fintech Agentic AI Portfolio

**Solutions Architect Portfolio — Agentic AI for Financial Services**

A progressive 3-project portfolio demonstrating enterprise-grade agentic AI architecture for fintech fraud detection and compliance. Each project builds on the last, showing the journey from single-agent fundamentals to full multi-agent orchestration platforms.

## Projects

### 1. [Transaction Risk Classifier](./project-1-risk-classifier/)
Single LangGraph agent with async tool orchestration that produces **explainable risk assessments** — not just scores. Demonstrates why reasoning chains matter more than numbers in regulated fintech.

### 2. [Fraud Detection Swarm](./project-2-fraud-swarm/)
Multi-agent system with specialized fraud detection agents (velocity, identity, behavioral) that debate, disagree, and escalate — inspired by the limitations of monolithic scoring engines like Kount's Omniscore.

### 3. [KYC/AML Compliance Platform](./project-3-kyc-platform/)
Full enterprise compliance platform with supervisor architecture, model-agnostic design, Streamlit dashboard, audit trails, and complete business case documentation including TCO and ROI models.

## Architecture Philosophy

- **Explainability over black boxes** — every agent decision includes a reasoning chain
- **Human-in-the-loop by design** — autonomous agents with enterprise guardrails
- **Model-agnostic** — swap LLM providers without architectural changes
- **Audit-first** — immutable decision logs for regulatory compliance
- **Production patterns** — async orchestration, state management, failure recovery

## Tech Stack

- **Framework:** LangGraph (production-hardened, used by Klarna, Uber, LinkedIn)
- **Language:** Python 3.11+ with async/await patterns
- **Data Models:** Pydantic v2
- **Dashboard:** Streamlit
- **Deployment:** HuggingFace Spaces / Docker

## Author

**Dimitri Pankov** — Solutions Architect specializing in agentic AI for financial services.
