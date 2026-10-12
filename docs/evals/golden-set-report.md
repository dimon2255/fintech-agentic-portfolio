# Golden-Set Evaluation: Report After the Sanctions-Screening Fix

**Date:** 2026-10-12 · **Method:** [ADR-001](../adr/001-golden-set-evaluation.md) ·
**Generated results:** [scorecard.md](scorecard.md) (rules tier), [scorecard-claude.md](scorecard-claude.md) (Claude,
run 4) · **Baseline (2026-10-11):** [baseline report](../evals-baseline-2026-10-11/golden-set-report.md) and its
scorecards · **Run it:** `python -m evals`

## Overview

The first measurement on 2026-10-11 found that the KYC/AML platform (Project 3) skipped sanctions screening for most
applicants. With its deterministic rules it approved an applicant whose name exactly matches the UN sanctions list,
and with Claude it sent an exact OFAC and UN match to a reviewer as a document query, without the sanctions result.
Sanctions screening is now mandatory for every applicant and is enforced in code in both modes.

Three scenarios were added, bringing the set from 35 to 38. Their labels and rationale were written before the
pipeline ran on them:

- **P3-15**: an exact EU-list name on an applicant the removed skip rule would have exempted (resident in a low-risk
  country, $9,900 a month, just under the old $10,000 threshold). It checks that the fix holds beyond the case that
  exposed the defect.
- **P3-16**: a common Arabic name that is on no list. It is a false-positive control: screening every applicant must
  not hold people for sharing a naming convention with listed persons.
- **P1-12**: four ordinary purchases in an hour on a trusted phone, the exact point where the velocity tool's
  rapid-succession flag starts firing since that threshold changed after the baseline.

Sanctions screening now runs for every applicant in both modes (16 of 16). All three exact list matches (P3-03,
P3-04, P3-15) are rejected in both modes, and the control case P3-16 is approved at low risk in both. With rules, the
KYC decision is right on 10 of 16 applications, up from 7 of 14, but the rules still approve 6 of the 10 applications
an analyst would stop. Those are the open findings 2, 3 and 5 of the baseline report: a potential sanctions match, two
expired passports, a tampered passport, another person's proof of address and a foreign politically exposed person.
With Claude the decision is right on 15 of 16; the one miss is a passport that expired before the application date,
which the document tool checks against a fixed date. The fraud projects are unchanged.

## Results

Counts are shown because one scenario moves a percentage by six to ten points. "Should-stop" cases are those whose
label does not accept approval; "legitimate" cases are those whose label requires approval. The baseline columns cover
35 scenarios, the current columns 38.

| Project | Measure | Rules, 2026-10-11 | Rules, now | Claude, 2026-10-11 (3 runs) | Claude, now (1 run) |
|---|---|---|---|---|---|
| P1 Risk classifier | Recommended action correct | 91% (10 of 11) | 92% (11 of 12) | 82% (9 of 11) | 83% (10 of 12) |
| P2 Fraud swarm | Recommended action correct | 80% (8 of 10) | 80% (8 of 10) | 80% (8 of 10) | 80% (8 of 10) |
| P2 Fraud swarm | Specialist risk levels correct | 93% (27 of 29) | 93% (27 of 29) | 90% (26 of 29) | 90% (26 of 29) |
| P3 KYC/AML | Compliance decision correct | 50% (7 of 14) | 62% (10 of 16) | 86% (12 of 14) | 94% (15 of 16) |
| P3 KYC/AML | Should-stop applications approved | 7 of 9 | 6 of 10 | 1 of 9 | 1 of 10 |
| P3 KYC/AML | Legitimate applications approved | 4 of 4 | 5 of 5 | 4 of 4 | 5 of 5 |
| P3 KYC/AML | Sanctions screening ran (required for every applicant) | 36% (5 of 14) | 100% (16 of 16) | 43% (6 of 14) | 100% (16 of 16) |
| P3 KYC/AML | Escalated to a human when required | 50% (5 of 10) | 67% (8 of 12) | 100% (10 of 10) | 100% (12 of 12) |
| P3 KYC/AML | Risk tier correct | 67% (6 of 9) | 82% (9 of 11) | 67% (6 of 9) | 82% (9 of 11) |
| P3 KYC/AML | Every graded check correct | 14% (2 of 14) | 50% (8 of 16) | 21% (3 of 14) | 81% (13 of 16) |
| All | Runs that crashed, failed an API call or silently fell back to rules | 0 of 35 | 0 of 38 | 0 in 381 LLM calls | 0 in 166 LLM calls |

Claude run 4 cost $0.47 (110,853 input and 72,321 output tokens at list price, $1 and $5 per million).

## Business impact

| Dimension | Now | Evidence |
|---|---|---|
| Regulatory exposure (sanctions) | Every applicant is screened in both modes, and exact list matches are rejected with a human involved. A potential match (a transliteration scoring 0.6) is still approved by the rules; Claude escalates it. | P3-03, P3-04, P3-15; P3-05 (open) |
| Onboarding fraud | Unchanged with rules: two expired passports, a tampered passport and another person's proof of address are approved. Claude escalates all of them except the passport that expired before the application date. | P3-06, P3-07, P3-09, P3-10 |
| Governance | Unchanged with rules: a foreign politically exposed person is approved automatically. Claude escalates. | P3-12 |
| Fairness and false positives | Mandatory screening did not create a false alert on the control case; legitimate applications are approved 5 of 5 in both modes. | P3-16 |
| Reliability | No crashes, API failures or silent fallbacks in 166 LLM calls. | Run 4 |

All data is synthetic and the projects are a portfolio, so no real customer was affected.

## Stability between runs

The three baseline runs returned identical decisions and identical reasoning text. Run 4, after the fix, matches
baseline run 1 on every graded check of the 35 original scenarios except the Project 3 checks the fix changed, all of
them improvements. Its reasoning text differs from run 1 (9 of 11 P1 and 0 of 10 P2 scenarios have identical text),
so at temperature 0 the Claude tier is reproducible at the decision level, not word for word. Run 4 is a single run;
its run-to-run spread has not been measured.

## Status of the baseline findings

| # | Baseline finding | Status |
|---|---|---|
| 1 | KYC rules skip sanctions screening for low-risk individuals | Fixed: screening is mandatory in both modes and enforced in `src/supervisor.py` |
| 2 | KYC rules approve potential sanctions matches without review | Open (P3-05) |
| 3 | KYC rules record document defects and then ignore them; expiry checked against a fixed date | Open (P3-06, P3-07, P3-09, P3-10) |
| 4 | With Claude, the supervisor escalates on invented document problems and defers screening | Partly fixed: screening now runs before any escalation; the document agent still reports invented issues such as "passport missing address field" |
| 5 | A foreign PEP is approved automatically (rules) | Open (P3-12) |
| 6 to 9 | Fraud swarm and P1 findings (Tor and VPN ignored, averaging, Claude friction, smaller findings) | Open, unchanged |

The baseline report describes each finding, its code path and a proposed fix.

## What is verified, inferred and not yet checked

- **Verified:** every number above is generated by the harness (`scorecard.json`, `claude-run-4.json`,
  `scorecard-claude.json`, and the baseline files). The 30 harness tests pass, and the CI gate passes with no
  regressions against the new `evals/baseline.json`, which `--write-baseline` refuses to record when any check
  regresses. All 166 calls of run 4 were answered by `claude-haiku-4-5-20251001`.
- **Inferred:** that the labels are what most analysts would decide. They are written by one author, as before.
- **Not yet checked:** run-to-run variance after the fix (one Claude run); other models and the OpenAI path; whether
  the matcher holds for names other than the one in P3-16.

## How to reproduce

```text
pip install -r evals/requirements.txt          # pinned, as in CI
python -m pytest                                # harness unit tests and the gate
python -m evals                                 # rules tier; writes docs/evals/scorecard.*
python -m evals --check                         # the CI gate
python -m evals --tier llm --file-stem claude-run-5   # Claude in every agent node (needs ANTHROPIC_API_KEY)
python -m evals --summarize-runs                # combine docs/evals/claude-run-*.json into scorecard-claude.*
```

## Technical reference

| Item | Location |
|---|---|
| Fix | `project-3-kyc-platform/src/supervisor.py` (guard), `project-3-kyc-platform/src/mock_llm.py` (skip removed) |
| New scenarios | `evals/golden/p1-risk-classifier/P1-12-*.json`, `evals/golden/p3-kyc-platform/P3-15-*.json`, `P3-16-*.json` |
| Ratchet baseline | `evals/baseline.json` |
| Current results | `docs/evals/` |
| Baseline results and report (2026-10-11) | `docs/evals-baseline-2026-10-11/` |
