# Token Usage & Cost Analysis

## Per-Transaction Cost Breakdown

| Component | Input Tokens | Output Tokens | Cost (GPT-4o-mini) |
|-----------|-------------|---------------|---------------------|
| Velocity Agent (prompt + data) | ~350 | ~300 | $0.0002 |
| Identity Agent (prompt + data) | ~650 | ~350 | $0.0003 |
| Behavioral Agent (prompt + data) | ~400 | ~300 | $0.0002 |
| Adjudicator (prompt + 3 verdicts) | ~1,250 | ~400 | $0.0004 |
| **Total per transaction** | **~2,650** | **~1,350** | **~$0.004** |

*Prices based on GPT-4o-mini ($0.15/1M input, $0.60/1M output) as of 2026.*

The adjudicator is the most expensive component because it ingests all three specialist verdicts as input context.

## Project 2 vs Project 1 Cost Comparison

| Metric | P1 (Single Agent) | P2 (Swarm) | Multiplier |
|--------|-------------------|------------|------------|
| LLM invocations | 1 | 4 | 4x |
| Input tokens | ~1,000 | ~2,650 | 2.7x |
| Output tokens | ~400 | ~1,350 | 3.4x |
| Cost per transaction | ~$0.001 | ~$0.004 | 4x |
| Unique signals | 3 tools | 5 tools + 3 perspectives | — |
| Audit depth | 1 reasoning chain | 3 chains + debate | — |

The cost multiplier is not simply 3x (for 3 agents) because the adjudicator consumes all three verdicts, adding significant input context.

## Scaling Projections

| Volume | Daily Cost | Monthly Cost | vs P1 Monthly | Notes |
|--------|-----------|-------------|---------------|-------|
| 100 txn/day | $0.40 | $12 | $3 | Development/testing |
| 10K txn/day | $40 | $1,200 | $300 | Small fintech |
| 100K txn/day | $400 | $12,000 | $3,000 | Mid-size processor |
| 1M txn/day | $4,000 | $120,000 | $30,000 | Enterprise scale |

## Cost Optimization Strategies

1. **Unanimous shortcut**: Skip the adjudicator when all 3 specialists agree on risk level. Expected hit rate: ~60% of transactions. Saves 25% of LLM costs ($0.003 instead of $0.004).

2. **Hybrid routing**: Use a fast ML classifier for clear-cut cases (80% of transactions). Only route ambiguous cases to the full swarm. Reduces effective cost by 5x.

3. **Specialist routing**: Not all transactions need all three specialists. Low-value purchases from known customers could skip identity analysis. Expected savings: 20-30%.

4. **Caching**: Cache specialist verdicts for repeat patterns (same customer, similar amount, same device). TTL: 30 minutes. Expected cache hit rate: 25-35%.

5. **Model tiering**: Use GPT-4o-mini for specialists (narrow focus, simpler reasoning) but GPT-4o or Claude Sonnet for the adjudicator (complex multi-verdict synthesis). Targets highest reasoning quality where it matters most.

## Comparison with Traditional Approaches

| Approach | Per-Txn Cost | Latency | Coverage | Explainability |
|----------|-------------|---------|----------|----------------|
| Rule engine | ~$0.00001 | <10ms | Rules only | Rules-based |
| ML scoring (Kount-style) | ~$0.0001 | <50ms | Trained patterns | Feature importance |
| P1 Single Agent | ~$0.001 | 1-2s | 3 signals, 1 view | One reasoning chain |
| **P2 Swarm** | **~$0.004** | **2-4s** | **5 signals, 3 views** | **Full debate trail** |

The swarm costs 4x more than the single agent but provides 3 independent perspectives plus documented disagreement resolution. The right architecture layers all four: rule engine for volume, ML for speed, single agent for explainability, swarm for high-stakes ambiguous cases.
