# ADR 001: Supervisor Hub-and-Spoke Over Fan-Out Adjudicator

**Status:** Accepted
**Date:** 2026-03-26
**Decision Maker:** Architecture team

## Context

Project 2 uses a fan-out/fan-in topology where three specialist agents run in parallel, then an adjudicator synthesizes their verdicts. This works well for fraud detection where all perspectives are equally valid and independent.

KYC/AML compliance workflows are fundamentally different:
- **Stage dependencies:** You can't verify identity until documents are processed. You can't assess risk until you know the sanctions status.
- **Skip logic:** Low-risk domestic individuals don't need full sanctions screening — running it wastes tokens and time.
- **Escalation at any stage:** If documents fail validation, there's no point running the remaining three agents.

The fan-out pattern can't express these constraints. We needed an architecture that supports sequential-with-branching workflows.

## Decision

Use a **supervisor hub-and-spoke** topology with LangGraph's `add_conditional_edges`:

```
START → supervisor → [conditional] → agent → supervisor → ... → final_decision → END
```

The supervisor acts as a central hub:
1. After each agent completes, control returns to the supervisor
2. The supervisor examines the current state (checklist, agent results, risk flags)
3. It dynamically routes to the next step: another agent, human review, or final decision
4. It can skip steps or escalate based on runtime conditions

This is implemented via `add_conditional_edges` — the key LangGraph feature that Projects 1 and 2 never use.

## Alternatives Considered

### Alternative 1: Extended Fan-Out (P2 pattern + conditional post-processing)
Run all 4 agents in parallel, then add conditional logic after the fan-in. Rejected because:
- Wastes compute running all agents when escalation happens at step 2
- Can't express stage dependencies (identity needs document results)
- Doesn't demonstrate architectural progression from P2

### Alternative 2: Linear Chain with Conditional Edges Between Agents
Direct edges from each agent to the next, with conditional branches. Rejected because:
- Leads to complex edge explosion (each agent needs edges to every possible next step)
- No centralized routing logic — harder to reason about
- No natural place for the compliance checklist

### Alternative 3: Nested Subgraphs
Each agent as a subgraph with its own conditional logic. Rejected because:
- Over-engineered for 4 agents
- Makes the overall flow harder to visualize and debug
- Doesn't clearly demonstrate supervisor pattern

## Consequences

### Positive
- **Clear architectural progression**: P1 (linear) → P2 (fan-out) → P3 (supervisor) tells a compelling story
- **Real-world mapping**: Supervisor pattern matches how actual compliance teams work
- **Efficiency**: Skip logic reduces average cost by 15-25% for low-risk applications
- **Explainability**: Every routing decision is logged with reasoning (audit trail)
- **Extensibility**: Adding a new compliance step = add one node + one edge pair

### Negative
- **Cyclic graph**: Supervisor loop is harder to reason about than linear or fan-out
- **Sequential bottleneck**: Agents run one at a time (can't parallelize when there are dependencies)
- **More supervisor invocations**: 4-5 LLM calls for the supervisor alone (vs. 0 in P2's static routing)

### Trade-offs Accepted
The sequential bottleneck is acceptable because KYC workflows are inherently sequential — you genuinely need document results before identity verification. The extra supervisor LLM calls are mitigated by skip logic (fewer total agent calls on average).
