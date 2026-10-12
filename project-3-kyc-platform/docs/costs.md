# Cost Analysis — KYC/AML Compliance Platform

## Per-Application Cost (measured)

| Path | Applications measured | LLM calls (mean) | Input tokens (mean) | Output tokens (mean) | Cost (Haiku 4.5) |
|------|----------------------|------------------|---------------------|----------------------|------------------|
| **Full pipeline** (all four agents, then final decision) | 7 | 9.0 | 4,790 | 2,794 | **$0.0188** |
| Escalated to human review | 9 | 5.7 | 3,028 | 1,982 | $0.0129 |
| All golden-set applications | 16 | 7.1 | 3,799 | 2,337 | $0.0155 |

*Measured with Claude Haiku 4.5 (`claude-haiku-4-5-20251001`, the default model) over the 16 golden-set applications
in [`docs/evals/claude-run-4.json`](../../docs/evals/claude-run-4.json), at list price ($1 per million input tokens,
$5 per million output tokens). A full pipeline is five supervisor calls plus one call for each of the four agents.
The golden set over-represents risky applications, so the full-pipeline cost is the better guide for production
volumes, where most applications are clean.*

## Portfolio Cost Comparison

| Project | LLM Calls | Cost per case (Haiku 4.5, measured) |
|---------|-----------|-------------------------------------|
| P1: Risk Classifier | 1 | $0.0040 |
| P2: Fraud Swarm | 4 | $0.0176 |
| **P3: KYC/AML Platform** | **5-9** | **$0.0188 full pipeline, $0.0129 escalated** |

P3 makes more LLM calls than P2 but each call carries a smaller context (about 530 input tokens per call against about
1,000 in P2), so a full P3 pipeline costs about the same as a P2 transaction.

## Mandatory Sanctions Screening

Sanctions screening runs for every applicant; there is no low-risk skip. An earlier version skipped screening for
individuals resident in low-risk countries to save cost, and the golden-set evaluation showed that it approved an
applicant whose name exactly matches the UN sanctions list
([baseline report](../../docs/evals-baseline-2026-10-11/golden-set-report.md), finding 1).

## Scaling Projections

Based on the measured full-pipeline cost of $0.0188 per application:

| Applications/Month | LLM Cost (Haiku 4.5) |
|-------------------|----------------------|
| 100 | $1.88 |
| 1,000 | $18.76 |
| 10,000 | $188 |
| 100,000 | $1,876 |

## Cost Optimization Strategies

1. **Model tiering** — Use Haiku for supervisor routing, a larger model for specialist agents
2. **Caching** — Repeat applicants, same-country risk lookups (30-40% cache hit rate possible)
3. **Batch processing** — Group sanctions screenings for bulk name matching
4. **Early escalation** — When documents or identity fail, the remaining agents after sanctions screening do not run; in the measured run an escalated application cost 31% less than a full pipeline

## Cost vs. Human Analyst

| Metric | Human Analyst | AI-Assisted (Haiku 4.5) |
|--------|--------------|--------------------|
| Per-application cost | $15-50 | $0.019 (measured) + $5 oversight |
| Processing time | 2-5 days | Seconds + review queue |
| Monthly volume capacity | 50-100/analyst | Unlimited + review staff |
| Consistency | Variable | Deterministic (mock) / identical decisions in three repeated runs at temperature 0 (LLM, measured 2026-10-11) |
