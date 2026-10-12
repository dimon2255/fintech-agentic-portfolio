# Business Case — AI-Assisted KYC/AML Compliance

## Problem Statement

Manual KYC/AML compliance review is a significant cost center for financial institutions:

- **$15-50 per application** for manual review (analyst time, tool licenses, overhead)
- **2-5 business days** average processing time
- **50-100 applications per analyst per month** capacity
- **High error rates** due to analyst fatigue, inconsistent application of rules
- **Regulatory risk** from missed sanctions hits or incomplete due diligence

## Proposed Solution

An AI-assisted compliance pipeline that automates the structured assessment steps while preserving human oversight for complex cases.

| Step | Current (Manual) | Proposed (AI-Assisted) |
|------|-----------------|----------------------|
| Document verification | Analyst reviews documents manually | AI extracts, classifies, validates automatically |
| Identity cross-reference | Analyst checks name/address/DOB | AI runs fuzzy matching with confidence scores |
| Sanctions screening | Analyst uses screening tool | AI screens 3 lists + adverse media in parallel |
| Risk assessment | Analyst applies judgment | AI computes composite score from 5 weighted factors |
| Decision | Analyst decides | AI decides for clear cases, escalates ambiguous ones |

## Total Cost of Ownership (TCO) Model

### Current State (10,000 applications/month)

| Cost Component | Monthly | Annual |
|---------------|---------|--------|
| Analyst salaries (20 analysts × $6K) | $120,000 | $1,440,000 |
| Screening tool licenses | $5,000 | $60,000 |
| Training and compliance | $3,000 | $36,000 |
| **Total** | **$128,000** | **$1,536,000** |

### Future State (AI-Assisted, same volume)

| Cost Component | Monthly | Annual |
|---------------|---------|--------|
| LLM API costs (Haiku 4.5, 10K apps at a measured $0.0188 each) | $188 | $2,256 |
| Analyst salaries (5 analysts for escalations/oversight) | $30,000 | $360,000 |
| Infrastructure (hosting, monitoring) | $2,000 | $24,000 |
| Screening tool licenses (same) | $5,000 | $60,000 |
| **Total** | **$37,188** | **$446,256** |

### Savings

| Metric | Value |
|--------|-------|
| Monthly savings | $90,812 |
| Annual savings | $1,089,744 |
| **Cost reduction** | **71%** |
| **Payback period** | ~2 months (development + deployment costs) |

## ROI Projections

| Volume (apps/month) | Annual Manual Cost | Annual AI-Assisted | Annual Savings | ROI |
|---------------------|-------------------|--------------------|---------------|-----|
| 1,000 | $154K | $60K | $94K | 157% |
| 5,000 | $768K | $181K | $587K | 324% |
| 10,000 | $1,536K | $446K | $1,090K | 244% |
| 50,000 | $7,680K | $1,870K | $5,810K | 311% |

## Qualitative Benefits

### Speed
- Processing time reduced from **2-5 days to seconds** for automated cases
- Escalated cases still get human review but with full AI-prepared context
- Faster onboarding improves customer experience and reduces abandonment

### Consistency
- Deterministic application of compliance rules (no analyst variability)
- Every decision includes reasoning chain for auditor review
- Compliance checklist records which steps ran, were skipped or are pending; sanctions screening always runs

### Audit Trail
- Timestamped record of every decision and routing choice, returned with the decision (kept in memory; this demo does not persist it or make it tamper-evident)
- Full reasoning chain per agent (explainable AI requirement)
- Supervisor routing decisions logged with reasoning

### Scalability
- Handles volume spikes without hiring (seasonal, market events)
- Linear cost scaling vs. step-function scaling for human analysts
- Global 24/7 availability vs. business hours

## Risk Mitigation

| Risk | Mitigation |
|------|-----------|
| False negatives (missed sanctions) | Every applicant is screened. Hits at or above the 0.4 fuzzy-match alert threshold are reported; matches above 0.8 go to human review and are rejected. A potential match between 0.4 and 0.8 is approved at a higher risk score by the rules (a known gap that Claude mode escalates) |
| Model hallucination | Mock LLM fallback, structured JSON output, Pydantic validation |
| Regulatory acceptance | Full audit trail, explainable reasoning, human-in-the-loop for all escalations |
| Vendor lock-in | Provider switch between Anthropic and OpenAI models via env var (only Anthropic has been evaluated) |

## Implementation Timeline

| Phase | Duration | Deliverable |
|-------|----------|-------------|
| MVP (this demo) | 4 weeks | Working prototype with synthetic data |
| Production integration | 8-12 weeks | Real document OCR, live sanctions feeds, database integration |
| Pilot deployment | 4-8 weeks | 100-application pilot with parallel manual review |
| Full rollout | 4-8 weeks | Production deployment with monitoring and alerting |
