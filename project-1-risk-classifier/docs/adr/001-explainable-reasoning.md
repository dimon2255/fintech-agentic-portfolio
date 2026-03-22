# ADR-001: Explainable Reasoning Chains Over Single-Score Output

## Status

Accepted

## Context

Traditional fraud detection systems (e.g., Kount Omniscore, Stripe Radar) produce a single composite risk score. This works well for high-volume automated decisioning but creates challenges:

1. **Regulatory scrutiny**: Financial regulators increasingly require explainability in automated decision systems (EU AI Act, CFPB guidance on automated lending)
2. **Analyst efficiency**: When a transaction is flagged for manual review, analysts need to understand *why* — a score of 0.73 doesn't tell them where to look
3. **Model debugging**: When false positives spike, teams need to trace which signals are misfiring

## Decision

The agent produces a `RiskAssessment` that includes a `reasoning_chain` — an ordered list of `ReasoningStep` objects, each documenting:
- The signal being evaluated
- What was observed
- The agent's assessment
- How it impacts overall risk

This reasoning chain is the primary output; the risk level and confidence score are derived from it.

## Consequences

### Positive
- Every decision is auditable and traceable end-to-end
- Compliance teams can explain decisions to regulators in plain language
- Analysts reviewing flagged transactions see exactly which signals triggered the flag
- Easier to identify systematic errors (e.g., "the agent is over-weighting VPN usage")

### Negative
- Higher latency: LLM reasoning takes 1-2s vs <10ms for a scoring model
- Higher cost: ~$0.01-0.05 per assessment vs negligible for a local model
- Non-deterministic: same transaction may produce slightly different reasoning narratives

### Mitigation
- Use this approach for secondary review, not inline authorization
- Cache assessments for repeat patterns
- Pydantic schema constrains output structure even if narrative varies
