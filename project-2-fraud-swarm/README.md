# Project 2: Fraud Detection Swarm

**A multi-agent fraud detection system with specialist debate and adjudicator resolution, built with LangGraph**

## Problem

Project 1's single-agent classifier provides explainability, but it relies on one reasoning perspective. In practice, different fraud patterns require different expertise: velocity analysis catches card testing, identity analysis catches synthetic identities, behavioral analysis catches bots. A single agent may weight one signal over others depending on prompt phrasing or model tendencies.

In regulated fintech, multi-perspective analysis with documented disagreement resolution is increasingly expected (EU AI Act, BSA/AML). When three experts disagree about a transaction, that disagreement itself is a risk signal.

## Approach

This project builds a 3-agent swarm with an adjudicator:

1. **Five analysis tools** run in parallel — velocity, geo, device, identity graph, behavioral anomaly
2. **Three specialist agents** independently reason about the signals from their area of expertise
3. **An adjudicator** receives all three verdicts, identifies agreement/disagreement, and weights expertise by context
4. **A synthesized verdict** captures the full debate trail — not just the decision, but how disagreements were resolved

### Why Multi-Agent > Single Agent

| Aspect | Single Agent (P1) | This Swarm (P2) |
|--------|-------------------|-----------------|
| Perspectives | One reasoning path | Three independent specialist views |
| Blind spots | Single model may miss patterns | Cross-validated signals catch more |
| Disagreement | N/A | Debate analysis surfaces ambiguity |
| Audit trail | One reasoning chain | Three chains + debate resolution |
| Regulatory story | "The agent decided" | "Three specialists agreed/disagreed because..." |
| Novel fraud | One interpretation | Multiple interpretations of same data |

## Architecture

See [ARCHITECTURE.md](docs/ARCHITECTURE.md) for detailed Mermaid diagrams, sequence flows, and the state isolation pattern.

```
Transaction ──▶ [Gather Signals] ──▶ [Velocity Agent ] ──┐
                      │              [Identity Agent ] ───┼──▶ [Adjudicator] ──▶ SwarmAssessment
                      │              [Behavioral Agent] ──┘
                5 tools (parallel)    3 agents (parallel)    debate + resolve
```

**Key design decisions:**
- Fan-out/fan-in topology — 3 specialists execute in parallel via LangGraph edges
- Each specialist writes to its own state key — no merge conflicts
- Adjudicator debate pattern — context-dependent weighting, not simple majority vote
- Conservative disagreement handling — low agreement bumps toward human review

## Quick Start

```bash
# From repo root
cd project-2-fraud-swarm
pip install -e ".[dev]"

# Configure (copy and fill in API key, or run in mock mode)
cp .env.example .env

# Run the swarm (CLI)
python -m src.main

# Run Streamlit demo
streamlit run app.py
```

## Tech Stack

- **LangGraph** — fan-out/fan-in graph with parallel agent execution
- **Pydantic v2** — strict validation for all verdicts, debate analysis, and final output
- **asyncio** — 5 tools execute in parallel (~0.3s vs ~1.5s sequential)
- **LangChain** — LLM provider abstraction (OpenAI / Anthropic)

## Key Files

| File | Purpose |
|------|---------|
| `src/graph.py` | LangGraph fan-out/fan-in graph definition |
| `src/agents/velocity_agent.py` | Velocity pattern specialist |
| `src/agents/identity_agent.py` | Identity graph specialist |
| `src/agents/behavioral_agent.py` | Behavioral anomaly specialist |
| `src/adjudicator.py` | Debate resolution and final verdict synthesis |
| `src/tools.py` | 5 async analysis tools (3 from P1 + 2 new) |
| `src/models.py` | Pydantic models (SwarmState, SpecialistVerdict, DebateAnalysis, SwarmAssessment) |
| `src/data_generator.py` | Synthetic data with disagreement triggers |
| `app.py` | Streamlit interactive demo |
| `docs/ARCHITECTURE.md` | Architecture diagrams and data flow |
| `docs/adr/001-multi-agent-debate-pattern.md` | ADR: Why multi-agent debate |
| `docs/costs.md` | Token usage and cost analysis |

## Trade-offs

- **Cost**: 4 LLM invocations per transaction (3 specialists + 1 adjudicator) vs Project 1's 1. Roughly 4x the token cost. At scale, this premium is offset by fewer false positives reaching human review. See [costs.md](docs/costs.md).
- **Latency**: Specialists run in parallel, but the adjudicator adds a sequential step. Total ~2-4s vs P1's ~1-2s. Still suited for secondary review, not inline authorization.
- **Complexity**: More moving parts means more failure modes. Each specialist has independent mock fallback to degrade gracefully. The state isolation pattern prevents merge conflicts but adds 12 state fields vs P1's 4.

## What I'd Do Differently

- **Conditional adjudication**: Skip the adjudicator when all three specialists agree unanimously — saves one LLM call on ~60% of transactions
- **Dynamic specialist routing**: Not all transactions need all three specialists. Low-amount purchases from known customers could skip identity analysis entirely
- **Streaming debate**: Stream the adjudicator's reasoning in real-time so reviewers can watch the debate unfold, building trust in the process
- **Calibration framework**: Measure each specialist's precision/recall independently to identify which agents need tuning and on what fraud types

## Next: Project 3

This swarm demonstrates multi-agent debate for a single decision point. [Project 3: KYC/AML Compliance Platform](../project-3-kyc-platform/) expands into a full compliance platform with supervisor architecture across multiple workflow stages — document intake, identity verification, sanctions screening, and risk assessment.
