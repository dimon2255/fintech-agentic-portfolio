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

## Evaluation

Each project explains its decisions; the golden-set evaluation ([`evals/`](evals/)) measures whether those
decisions are right. It replays 35 hand-labeled cases through the projects' production code (11 card transactions
for Project 1, 10 for Project 2, 14 onboarding applications for Project 3) and compares each decision with what a
fraud or compliance analyst would decide. Labels and their rationale were written before the pipeline ran. Each
project is measured in its deterministic rules mode, which is a CI gate, and with Claude Haiku 4.5 in every agent
node, three times.

Baseline, 2026-10-11:

| Project | Measure | Rules (CI gate) | Claude Haiku 4.5 (3 runs, identical) |
|---|---|---|---|
| 1. Risk classifier | Recommended action correct | 91% (10 of 11) | 82% (9 of 11) |
| 2. Fraud swarm | Recommended action correct | 80% (8 of 10) | 80% (8 of 10) |
| 2. Fraud swarm | Specialist risk levels correct | 93% (27 of 29) | 90% (26 of 29) |
| 3. KYC/AML platform | Compliance decision correct | 50% (7 of 14) | 86% (12 of 14) |
| 3. KYC/AML platform | Applications approved that an analyst would stop | 7 of 9 | 1 of 9 |
| 3. KYC/AML platform | Sanctions screening ran (required for every applicant) | 36% (5 of 14) | 43% (6 of 14) |
| All | Legitimate cases approved (false-positive check) | 10 of 10 | 7 of 10 |
| All | Crashes, API failures or silent fallbacks to rules | 0 | 0 in 381 LLM calls |

The fraud projects make the right call on most transactions. The KYC rules approve cases a compliance analyst
would stop, including an exact UN sanctions-list name that was never screened. Claude's KYC decisions are far
better but sometimes right for the wrong reason: it escalates on invented document problems before sanctions
screening runs. The [baseline report](docs/evals/golden-set-report.md) traces every miss to a code path and
proposes fixes; the [rules scorecard](docs/evals/scorecard.md) and [Claude summary](docs/evals/scorecard-claude.md)
have per-scenario detail. Method and limits: [ADR-001](docs/adr/001-golden-set-evaluation.md).

```bash
pip install -r evals/requirements.txt
python -m evals                    # run the golden set (rules), write docs/evals/scorecard.md
python -m evals --check            # CI gate: fails if any passing check regresses or a scenario fails to run
python -m evals --tier llm --file-stem claude-run-1   # Claude in every agent node (needs ANTHROPIC_API_KEY)
```

How it scores:

- **Real pipeline, real tools.** Each scenario runs the project's own entrypoint, agents, prompts and simulated
  tools. The harness sets only the inputs (chosen so the deterministic tools return the scenario's stated
  evidence, which is re-checked on every run) and sets simulated latency to zero.
- **Failures are never passes.** Crashes, API errors and silent fallbacks to the rules are counted separately and
  excluded from accuracy.
- **Ratchet gate.** `evals/baseline.json` records which checks pass. CI fails if any regresses. Run against an
  unmerged threshold branch, the gate failed 8 checks, including an exact sanctions match the branch would approve.

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
