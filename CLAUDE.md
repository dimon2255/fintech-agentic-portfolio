# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

A 3-project fintech portfolio demonstrating agentic AI for fraud detection and compliance, progressing from single-agent to multi-agent orchestration:

- **Project 1** (`project-1-risk-classifier/`): Single LangGraph agent — async parallel tool execution → LLM reasoning → explainable risk assessment
- **Project 2** (`project-2-fraud-swarm/`): Multi-agent swarm — 3 specialist agents (velocity, identity, behavioral) fan-out in parallel → adjudicator debate/resolution → final verdict
- **Project 3** (`project-3-kyc-platform/`): Supervisor hub-and-spoke — 4 specialist agents (document intake, identity, sanctions, risk) orchestrated by a supervisor with conditional routing, mandatory sanctions screening, and human-in-the-loop escalation

## Commands

```bash
# Install (from repo root)
pip install -e ".[dev]"

# Each project has its own .env (copy from .env.example)
cp project-1-risk-classifier/.env.example project-1-risk-classifier/.env

# Run Project 1 classifier
python -m src.main                    # from project-1-risk-classifier/
# Run Project 2 swarm
python -m src.main                    # from project-2-fraud-swarm/
# Run Project 3 KYC platform
python -m src.main                    # from project-3-kyc-platform/

# Streamlit demos
streamlit run project-1-risk-classifier/app.py
streamlit run project-2-fraud-swarm/app.py
streamlit run project-3-kyc-platform/app.py

# Tests
pytest                                # from repo root
# Lint
ruff check .
```

## Architecture

### Shared Patterns Across Projects
- **Mock LLM fallback**: Every agent checks `_has_api_key()` — if no API key is set, uses deterministic mock functions (`mock_llm.py`) for zero-cost dev/demo. Real LLM mode activates when `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` is in `.env`.
- **Model selection**: `DEFAULT_MODEL` env var controls which LLM is used. `"claude"` in the name routes to `ChatAnthropic`, otherwise `ChatOpenAI`.
- **Pydantic v2 everywhere**: All data models use strict Pydantic v2 validation. Tool results, agent state, and final outputs are all typed models.
- **Async-first**: All graph nodes are `async def`. Tools run via `asyncio.gather()` for parallel execution.

### Project 1 Graph
Two-node linear graph: `gather_signals` → `assess_risk` → END. State is `AgentState` (TypedDict). Entry point: `classify_transaction()` in `agent.py`.

### Project 2 Graph
Fan-out/fan-in topology in `graph.py`: `gather_all_signals` → [velocity_agent | identity_agent | behavioral_agent] (parallel) → `adjudicator` → END. State is `SwarmState` (TypedDict with separate verdict keys per specialist). Entry point: `analyze_transaction()` in `graph.py`. Each specialist agent lives in `src/agents/` and writes to its own state key to avoid merge conflicts.

### Project 3 Graph
Supervisor hub-and-spoke topology in `graph.py`: `supervisor` → [conditional routing to document_intake | identity_verification | sanctions_screening | risk_assessment | human_review | final_decision]. Uses `add_conditional_edges` for dynamic routing. State is `KYCState` (TypedDict with separate result keys per agent). Entry point: `run_kyc_application()` in `graph.py`. Supervisor returns to hub after each agent to decide the next step.

### Data Flow
Each project's `tools.py` contains synthetic analysis functions (velocity, geo, device fingerprint; P2 adds identity and behavioral; P3 adds document, sanctions, and risk tools). `data_generator.py` creates synthetic inputs with different risk profiles (P1/P2: transactions; P3: KYC applications with 5 profiles including sanctions hits and document issues).

## Key Conventions
- Each project is self-contained with its own `src/`, `docs/`, `.env.example`, and models (P2 duplicates P1 models and extends them rather than importing cross-project)
- ADRs live in `docs/adr/` within each project
- All data is synthetic — no real PII anywhere
