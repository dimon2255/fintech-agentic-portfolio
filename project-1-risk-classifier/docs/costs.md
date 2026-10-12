# Token Usage & Cost Analysis

## Per-Transaction Cost (measured)

| Measure | Value |
|---------|-------|
| LLM calls | 1 |
| Input tokens | 845 (mean) |
| Output tokens | 637 (mean) |
| **Cost per transaction** | **$0.0040** |

*Measured with Claude Haiku 4.5 (`claude-haiku-4-5-20251001`, the default model) over the 12 golden-set transactions
in [`docs/evals/claude-run-4.json`](../../docs/evals/claude-run-4.json), at list price ($1 per million input tokens,
$5 per million output tokens). The split between system prompt, transaction data and tool results is not measured.*

## Scaling Projections

| Volume | Daily Cost | Monthly Cost (30 days) | Notes |
|--------|-----------|-------------|-------|
| 100 txn/day | $0.40 | $12 | Development/testing |
| 10K txn/day | $40 | $1,209 | Small fintech |
| 100K txn/day | $403 | $12,091 | Mid-size processor |
| 1M txn/day | $4,031 | $120,908 | Enterprise scale |

## Cost Optimization Strategies

1. **Hybrid routing**: Use a fast ML classifier for clear-cut cases (80% of transactions). Only route ambiguous cases to the LLM agent. Reduces effective cost by 5x.

2. **Caching**: Repeat customers on known devices with typical amounts can reuse cached assessments (TTL: 1 hour). Expected cache hit rate: 30-40%.

3. **Model selection**: Claude Haiku 4.5 is the default for cost efficiency. For complex edge cases only, a larger model could be used for deeper reasoning at a higher cost per transaction.

4. **Batch processing**: For non-real-time use cases (compliance review, daily audit), batch transactions to reduce per-request overhead.

## Comparison with Traditional Approaches

| Approach | Per-Transaction Cost | Latency | Explainability |
|----------|---------------------|---------|----------------|
| Rule engine | ~$0.00001 | <10ms | Rules-based |
| ML scoring (Kount-style) | ~$0.0001 | <50ms | Feature importance |
| **This LLM agent** | **$0.0040 (measured)** | **1-2s** | **Full reasoning chain** |

At these estimates the LLM agent costs about 40 times more per transaction than ML scoring, in exchange for a full reasoning chain. The right architecture uses both — fast scoring for volume, agent reasoning for depth.
