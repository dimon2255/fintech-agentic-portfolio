# Token Usage & Cost Analysis

## Per-Transaction Cost (measured)

| Measure | Value |
|---------|-------|
| LLM calls | 4 (3 specialists + 1 adjudicator) |
| Input tokens | 3,993 (mean) |
| Output tokens | 2,728 (mean) |
| **Cost per transaction** | **$0.0176** |

*Measured with Claude Haiku 4.5 (`claude-haiku-4-5-20251001`, the default model) over the 10 golden-set transactions
in [`docs/evals/claude-run-4.json`](../../docs/evals/claude-run-4.json), at list price ($1 per million input tokens,
$5 per million output tokens).*

The adjudicator's prompt includes all three specialist verdicts as input context; the split of cost between the four
calls is not measured.

## Project 2 vs Project 1 Cost Comparison

| Metric | P1 (Single Agent) | P2 (Swarm) | Multiplier |
|--------|-------------------|------------|------------|
| LLM invocations | 1 | 4 | 4x |
| Input tokens | 845 | 3,993 | 4.7x |
| Output tokens | 637 | 2,728 | 4.3x |
| Cost per transaction | $0.0040 | $0.0176 | 4.4x |
| Unique signals | 3 tools | 5 tools + 3 perspectives | — |
| Audit depth | 1 reasoning chain | 3 chains + agreement analysis | — |

The cost multiplier is above 3x (for 3 agents) because the adjudicator's call adds a fourth prompt that carries all three verdicts.

## Scaling Projections

| Volume | Daily Cost | Monthly Cost (30 days) | vs P1 Monthly | Notes |
|--------|-----------|-------------|---------------|-------|
| 100 txn/day | $1.76 | $53 | $12 | Development/testing |
| 10K txn/day | $176 | $5,290 | $1,209 | Small fintech |
| 100K txn/day | $1,763 | $52,897 | $12,091 | Mid-size processor |
| 1M txn/day | $17,632 | $528,969 | $120,908 | Enterprise scale |

## Cost Optimization Strategies

1. **Unanimous shortcut**: Skip the adjudicator when all 3 specialists agree on risk level. Expected hit rate: ~60% of transactions. Saves one of the four LLM calls on those transactions.

2. **Hybrid routing**: Use a fast ML classifier for clear-cut cases (80% of transactions). Only route ambiguous cases to the full swarm. Reduces effective cost by 5x.

3. **Specialist routing**: Not all transactions need all three specialists. Low-value purchases from known customers could skip identity analysis. Expected savings: 20-30%.

4. **Caching**: Cache specialist verdicts for repeat patterns (same customer, similar amount, same device). TTL: 30 minutes. Expected cache hit rate: 25-35%.

5. **Model tiering**: Keep a small model (the default Claude Haiku 4.5) for the specialists (narrow focus, simpler reasoning) and use a larger model for the adjudicator. Targets the highest reasoning quality where it matters most.

## Comparison with Traditional Approaches

| Approach | Per-Txn Cost | Latency | Coverage | Explainability |
|----------|-------------|---------|----------|----------------|
| Rule engine | ~$0.00001 | <10ms | Rules only | Rules-based |
| ML scoring (Kount-style) | ~$0.0001 | <50ms | Trained patterns | Feature importance |
| P1 Single Agent | $0.0040 (measured) | 1-2s | 3 signals, 1 view | One reasoning chain |
| **P2 Swarm** | **$0.0176 (measured)** | **2-4s** | **5 signals, 3 views** | **Three reasoning chains + agreement analysis** |

The swarm costs about 4.4 times more than the single agent but provides 3 independent perspectives plus a recorded analysis of where they agree and disagree. The right architecture layers all four: rule engine for volume, ML for speed, single agent for explainability, swarm for high-stakes ambiguous cases.
