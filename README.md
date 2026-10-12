# Fintech Agentic AI Portfolio

**Solutions Architect Portfolio — Agentic AI for Financial Services**

A progressive 3-project portfolio demonstrating enterprise-grade agentic AI architecture for fintech fraud detection and compliance. Each project builds on the last, showing the journey from single-agent fundamentals to full multi-agent orchestration platforms.

## Projects

### 1. [Transaction Risk Classifier](./project-1-risk-classifier/)
Single LangGraph agent with async tool orchestration that produces **explainable risk assessments** — not just scores. Demonstrates why reasoning chains matter more than numbers in regulated fintech.

### 2. [Fraud Detection Swarm](./project-2-fraud-swarm/)
Multi-agent system in which three specialist agents (velocity, identity, behavioral) assess each transaction independently and in parallel. An adjudicator records where they agree and disagree; the final verdict is the unweighted mean of their risk scores, and low agreement turns an approval into a manual review. Inspired by the limitations of monolithic scoring engines like Kount's Omniscore.

### 3. [KYC/AML Compliance Platform](./project-3-kyc-platform/)
Compliance platform with a supervisor architecture, mandatory sanctions screening, a switch between Anthropic and OpenAI models, a Streamlit dashboard, a timestamped audit trail per decision, and business case documentation including TCO and ROI models.

## Evaluation

Each project explains its decisions; the golden-set evaluation ([`evals/`](evals/)) measures whether those
decisions are right. It replays 38 hand-labeled cases through the projects' production code (12 card transactions
for Project 1, 10 for Project 2, 16 onboarding applications for Project 3) and compares each decision with what a
fraud or compliance analyst would decide. Labels and their rationale are written before the pipeline runs on a case.
Each project is measured in its deterministic rules mode, which is a CI gate, and with Claude Haiku 4.5 in every
agent node.

The first measurement, on 2026-10-11, found that the KYC platform skipped sanctions screening for most applicants and
approved an exact UN sanctions-list name. Screening is now mandatory and enforced in code, and three cases were added
to test the fix. Results on 2026-10-12, with the 2026-10-11 baseline (35 cases) for comparison:

| Project | Measure | Rules (CI gate) | Claude Haiku 4.5 (1 run) | Baseline: rules / Claude (3 runs) |
|---|---|---|---|---|
| 1. Risk classifier | Recommended action correct | 92% (11 of 12) | 83% (10 of 12) | 10 of 11 / 9 of 11 |
| 2. Fraud swarm | Recommended action correct | 80% (8 of 10) | 80% (8 of 10) | 8 of 10 / 8 of 10 |
| 2. Fraud swarm | Specialist risk levels correct | 93% (27 of 29) | 90% (26 of 29) | 27 of 29 / 26 of 29 |
| 3. KYC/AML platform | Compliance decision correct | 62% (10 of 16) | 94% (15 of 16) | 7 of 14 / 12 of 14 |
| 3. KYC/AML platform | Applications approved that an analyst would stop | 6 of 10 | 1 of 10 | 7 of 9 / 1 of 9 |
| 3. KYC/AML platform | Sanctions screening ran (required for every applicant) | 100% (16 of 16) | 100% (16 of 16) | 5 of 14 / 6 of 14 |
| All | Legitimate cases approved (false-positive check) | 11 of 11 | 8 of 11 | 10 of 10 / 7 of 10 |
| All | Crashes, API failures or silent fallbacks to rules | 0 | 0 in 166 LLM calls | 0 / 0 in 381 LLM calls |

Every applicant is now screened, and the three exact sanctions-list matches in the set are rejected in both modes. The
KYC rules still approve 6 of the 10 applications an analyst would stop: a potential sanctions match, expired and
tampered passports, another person's proof of address and a foreign politically exposed person. Claude's one KYC miss
is a passport that expired before the application date, which the document tool checks against a fixed date; Claude
also still reports invented document problems. The fraud projects are unchanged. The three baseline Claude runs
returned identical decisions; the run after the fix matched them on every graded check outside the KYC changes, though
the reasoning text varies between runs. The [current report](docs/evals/golden-set-report.md) gives the status of every
finding; the [baseline report](docs/evals-baseline-2026-10-11/golden-set-report.md) traces each one to a code path and
proposes fixes. Per-scenario detail: [rules scorecard](docs/evals/scorecard.md) and
[Claude summary](docs/evals/scorecard-claude.md). Method and limits: [ADR-001](docs/adr/001-golden-set-evaluation.md).

```bash
pip install -r evals/requirements.txt
python -m evals                    # run the golden set (rules), write docs/evals/scorecard.md
python -m evals --check            # CI gate: fails if any passing check regresses or a scenario fails to run
python -m evals --tier llm --file-stem claude-run-5   # Claude in every agent node (needs ANTHROPIC_API_KEY)
```

How it scores:

- **Real pipeline, real tools.** Each scenario runs the project's own entrypoint, agents, prompts and simulated
  tools. The harness sets only the inputs (chosen so the deterministic tools return the scenario's stated
  evidence, which is re-checked on every run) and sets simulated latency to zero.
- **Failures are never passes.** Crashes, API errors and silent fallbacks to the rules are counted separately and
  excluded from accuracy.
- **Ratchet gate.** `evals/baseline.json` records which checks pass. CI fails if any regresses. Run against an
  unmerged threshold branch on 2026-10-11, the gate failed 8 checks, including an exact sanctions match the branch would
  approve.

## Architecture Philosophy

- **Explainability over black boxes** — every agent decision includes a reasoning chain
- **Human-in-the-loop by design** — autonomous agents with enterprise guardrails
- **Provider switch** — `DEFAULT_MODEL` selects an Anthropic or OpenAI chat model; only the Anthropic path has been evaluated
- **Audit-first** — every KYC decision carries a timestamped audit trail of each step and routing choice (kept in memory with the decision; this demo does not persist it or make it tamper-evident)
- **Production patterns** — async orchestration, state management, failure recovery

## Tech Stack

- **Framework:** LangGraph (production-hardened, used by Klarna, Uber, LinkedIn)
- **Language:** Python 3.11+ with async/await patterns
- **Data Models:** Pydantic v2
- **Dashboard:** Streamlit

## Author

**Dimitri Pankov** — Solutions Architect specializing in agentic AI for financial services.
