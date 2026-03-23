# ADR-001: Multi-Agent Debate Pattern Over Single-Agent Classification

## Status

Accepted

## Context

Project 1 demonstrated that a single LLM agent can produce explainable fraud assessments. However, single-agent classification has structural limitations:

1. **Blind spots**: A single agent may weight one signal category over others depending on prompt phrasing or model tendencies — velocity patterns could dominate while identity red flags are underweighted
2. **Regulatory direction**: Financial regulators and frameworks (EU AI Act, BSA/AML) increasingly favor multi-perspective analysis with documented disagreement resolution over single-model decisions
3. **Fraud diversity**: Different fraud types require different expertise — card testing looks different from synthetic identity fraud, which looks different from bot-driven account takeover
4. **Real-world analog**: Institutional fraud review panels use multiple analysts with different specializations, not a single reviewer

## Decision

The swarm uses three specialist agents with an adjudicator debate pattern:

- **Velocity Agent** focuses on transaction frequency, amount deviation, and rapid succession patterns
- **Identity Agent** cross-references email reputation, address verification, device history, and chargeback patterns
- **Behavioral Agent** analyzes session dynamics, checkout speed, typing/mouse anomalies, and navigation patterns

Each specialist runs in parallel via LangGraph fan-out edges and writes to its own state key to avoid merge conflicts. An **adjudicator** receives all three verdicts, identifies agreement/disagreement, and synthesizes a final verdict with debate analysis.

When agreement is low, the system conservatively routes toward human review — in fintech, a false negative (missed fraud) is worse than a false positive (flagged legitimate transaction).

## Consequences

### Positive
- Multi-perspective analysis catches fraud patterns that any single agent would miss (e.g., clean velocity + dirty identity = synthetic identity fraud)
- Disagreement itself is a risk signal — high specialist disagreement indicates genuinely ambiguous cases that warrant human review
- Full audit trail includes not just the final decision but each specialist's reasoning and how disagreements were resolved
- Each specialist can be independently evaluated, tuned, or replaced without rewriting the system

### Negative
- 4 LLM invocations per transaction vs 1 in Project 1 (3 specialists + 1 adjudicator) — roughly 4x token cost
- Added latency from the sequential adjudicator step (~1-2s on top of parallel specialist execution)
- More complex failure modes: any specialist can fail independently; the adjudicator must handle partial verdicts
- State management complexity: SwarmState has 12 fields vs P1's 4

### Mitigation
- Skip the adjudicator on unanimous specialist agreement — saves 1 LLM call on ~60% of transactions
- Each specialist has independent mock fallback — system degrades gracefully if one agent fails
- LangGraph's typed state and Pydantic validation catch structural errors at node boundaries
- State isolation pattern (separate verdict keys) prevents the merge conflicts that plague shared-state parallel systems
