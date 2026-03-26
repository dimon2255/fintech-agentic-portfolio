# Cost Analysis — KYC/AML Compliance Platform

## Per-Application Cost Breakdown

| Component | Input Tokens | Output Tokens | Cost (Haiku) | Cost (Sonnet) |
|-----------|-------------|---------------|-------------|--------------|
| Supervisor (×4-5 calls) | ~200 each | ~150 each | $0.0004 | $0.006 |
| Document Intake Agent | ~500 | ~400 | $0.0002 | $0.003 |
| Identity Verification Agent | ~600 | ~350 | $0.0002 | $0.003 |
| Sanctions Screening Agent | ~500 | ~300 | $0.0002 | $0.003 |
| Risk Assessment Agent | ~800 | ~400 | $0.0003 | $0.004 |
| **Total (full pipeline)** | **~4,500** | **~2,200** | **~$0.0013** | **~$0.019** |

## Portfolio Cost Comparison

| Project | LLM Calls | Approx. Cost (Haiku) | Approx. Cost (Sonnet) |
|---------|-----------|---------------------|----------------------|
| P1: Risk Classifier | 1 | ~$0.001 | ~$0.004 |
| P2: Fraud Swarm | 4 | ~$0.004 | ~$0.016 |
| **P3: KYC/AML Platform** | **8-9** | **~$0.0013** | **~$0.019** |

Note: P3 has more LLM calls (supervisor + 4 agents) but each call is more focused with smaller context windows than P2's specialists which receive broader transaction data.

## Skip Logic Cost Savings

For low-risk domestic individual applications:
- Sanctions screening is **skipped** (supervisor routing)
- Saves 1 agent call + 4 tool calls
- ~15-25% cost reduction on eligible applications

Estimated eligible rate: 40-50% of applications in a typical US/EU bank.

## Scaling Projections

| Applications/Month | LLM Cost (Haiku) | LLM Cost (Sonnet) |
|-------------------|------------------|--------------------|
| 100 | $0.13 | $1.90 |
| 1,000 | $1.30 | $19.00 |
| 10,000 | $13.00 | $190.00 |
| 100,000 | $130.00 | $1,900.00 |

## Cost Optimization Strategies

1. **Skip logic** — Already implemented. Low-risk profiles skip sanctions screening (~20% savings)
2. **Model tiering** — Use Haiku for supervisor routing, Sonnet for specialist agents
3. **Caching** — Repeat applicants, same-country risk lookups (30-40% cache hit rate possible)
4. **Batch processing** — Group sanctions screenings for bulk name matching
5. **Early termination** — If document validation fails, remaining agents don't run (saves 60-75%)

## Cost vs. Human Analyst

| Metric | Human Analyst | AI-Assisted (Haiku) | AI-Assisted (Sonnet) |
|--------|--------------|--------------------|--------------------|
| Per-application cost | $15-50 | ~$0.001 + $5 oversight | ~$0.02 + $5 oversight |
| Processing time | 2-5 days | Seconds + review queue | Seconds + review queue |
| Monthly volume capacity | 50-100/analyst | Unlimited + review staff | Unlimited + review staff |
| Consistency | Variable | Deterministic (mock) / Consistent (LLM) | Deterministic (mock) / Consistent (LLM) |
