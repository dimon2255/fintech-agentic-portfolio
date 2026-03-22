# Project 1: Transaction Risk Classifier

**An explainable, single-agent fraud risk classifier built with LangGraph**

## Problem

Traditional fraud detection systems like Kount's Omniscore output a single number — a transaction safety rating. While fast and effective at scale, this approach creates a black box: when a transaction is flagged, compliance teams and regulators want to know *why*, not just *how much*.

In regulated fintech, explainability isn't a nice-to-have — it's a compliance requirement.

## Approach

This project builds a single LangGraph agent that:

1. **Receives** an incoming transaction
2. **Calls 3 analysis tools in parallel** (async) — velocity patterns, geolocation, device fingerprinting
3. **Reasons through** the combined signals using an LLM
4. **Produces** a structured, explainable risk assessment with a full reasoning chain

Every decision includes not just a risk level, but a step-by-step explanation of which signals contributed, how they interacted, and why the agent reached its conclusion.

### Why Reasoning Chains > Single Scores

| Aspect | Omniscore Approach | This Agent |
|--------|-------------------|------------|
| Output | Single number (0-100) | Risk level + reasoning chain |
| Explainability | Contributing factors list | Full narrative reasoning |
| Novel patterns | Needs retraining | LLM can reason about unseen patterns |
| Audit readiness | Score + weights | Complete decision trace |
| Regulatory response | "The model flagged it" | "Here's exactly why, step by step" |

## Architecture

See [ARCHITECTURE.md](docs/ARCHITECTURE.md) for detailed diagrams and data flow.

```
Transaction ──▶ [Gather Signals] ──▶ [Assess Risk] ──▶ RiskAssessment
                      │
          ┌───────────┼───────────┐
          ▼           ▼           ▼
     Velocity     Geo Lookup   Device FP
     (async)      (async)      (async)
```

**Key design decisions:**
- Async parallel tool execution (~0.3s vs ~0.9s sequential)
- Pydantic models enforce schema validation on all data
- Model-agnostic: supports OpenAI and Anthropic via env config
- Synthetic data only — zero real PII

## Quick Start

```bash
# Clone and install
cd project-1-risk-classifier
pip install -e ".[dev]"

# Configure (copy and fill in your API key)
cp .env.example .env

# Run the classifier
python -m src.main
```

## Tech Stack

- **LangGraph** — agent orchestration with explicit state management
- **Pydantic v2** — strict data validation for all inputs and outputs
- **asyncio** — parallel tool execution for real-time performance
- **LangChain** — LLM provider abstraction (OpenAI / Anthropic)

## Key Files

| File | Purpose |
|------|---------|
| `src/agent.py` | LangGraph agent definition and graph construction |
| `src/tools.py` | Async tool implementations (velocity, geo, device) |
| `src/models.py` | Pydantic data models for transactions and assessments |
| `src/data_generator.py` | Synthetic transaction data generator |
| `docs/ARCHITECTURE.md` | Architecture diagrams and data flow |
| `docs/adr/001-explainable-reasoning.md` | ADR: Why reasoning chains over scores |
| `docs/costs.md` | Token usage analysis per transaction |

## Trade-offs

- **LLM latency vs rule engines**: This agent takes ~1-2s per transaction (LLM inference). Production fraud systems need <200ms. This design is better suited for secondary review or batch analysis, not inline payment authorization.
- **Cost**: Each assessment costs ~$0.01-0.05 in API tokens. At 1M transactions/day, that's $10K-50K/month in LLM costs alone. See [costs.md](docs/costs.md) for detailed analysis.
- **Determinism**: LLM reasoning can vary between runs. The Pydantic output schema constrains the structure, but reasoning narratives may differ.

## What I'd Do Differently

- **Add caching**: Repeat customers with known devices could skip the full LLM reasoning and use cached assessments with a TTL
- **Hybrid approach**: Use a fast ML model (like Kount's) for the 80% of clearly safe/risky transactions, and route only ambiguous cases to the LLM agent. Best of both worlds
- **Streaming**: Stream the reasoning chain as it's generated so human reviewers can see the agent "thinking" in real-time
- **Evaluation framework**: Build a systematic eval pipeline with labeled transactions to measure precision/recall against known fraud patterns

## Next: Project 2

This single-agent classifier is the foundation. [Project 2: Fraud Detection Swarm](../project-2-fraud-swarm/) expands this into a multi-agent system where specialized agents debate and adjudicate — addressing the limitation of relying on a single reasoning perspective.
