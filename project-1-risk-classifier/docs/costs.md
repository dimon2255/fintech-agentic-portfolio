# Token Usage & Cost Analysis

## Per-Transaction Cost Breakdown

| Component | Input Tokens | Output Tokens | Cost (GPT-4o-mini) |
|-----------|-------------|---------------|---------------------|
| System prompt | ~350 | — | $0.0001 |
| Transaction data | ~200 | — | $0.0001 |
| Tool results (3 tools) | ~450 | — | $0.0001 |
| Risk assessment output | — | ~400 | $0.0006 |
| **Total per transaction** | **~1,000** | **~400** | **~$0.001** |

*Prices based on GPT-4o-mini ($0.15/1M input, $0.60/1M output) as of 2026.*

## Scaling Projections

| Volume | Daily Cost | Monthly Cost | Notes |
|--------|-----------|-------------|-------|
| 100 txn/day | $0.10 | $3.00 | Development/testing |
| 10K txn/day | $10.00 | $300.00 | Small fintech |
| 100K txn/day | $100.00 | $3,000.00 | Mid-size processor |
| 1M txn/day | $1,000.00 | $30,000.00 | Enterprise scale |

## Cost Optimization Strategies

1. **Hybrid routing**: Use a fast ML classifier for clear-cut cases (80% of transactions). Only route ambiguous cases to the LLM agent. Reduces effective cost by 5x.

2. **Caching**: Repeat customers on known devices with typical amounts can reuse cached assessments (TTL: 1 hour). Expected cache hit rate: 30-40%.

3. **Model selection**: GPT-4o-mini is used for cost efficiency. For complex edge cases only, route to GPT-4o or Claude Sonnet for deeper reasoning at ~10x cost.

4. **Batch processing**: For non-real-time use cases (compliance review, daily audit), batch transactions to reduce per-request overhead.

## Comparison with Traditional Approaches

| Approach | Per-Transaction Cost | Latency | Explainability |
|----------|---------------------|---------|----------------|
| Rule engine | ~$0.00001 | <10ms | Rules-based |
| ML scoring (Kount-style) | ~$0.0001 | <50ms | Feature importance |
| **This LLM agent** | **~$0.001** | **1-2s** | **Full reasoning chain** |

The LLM agent costs 10x more than ML scoring but provides 10x more explainability. The right architecture uses both — fast scoring for volume, agent reasoning for depth.
