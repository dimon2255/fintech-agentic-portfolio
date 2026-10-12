# Golden-Set Evaluation: Baseline Report

**Date:** 2026-10-11 · **Method:** [ADR-001](../adr/001-golden-set-evaluation.md) ·
**Generated results:** [scorecard.md](scorecard.md) (rules tier), [scorecard-claude.md](scorecard-claude.md)
(three Claude runs) · **Data flow:** [eval-harness.md](../diagrams/eval-harness.md) · **Run it:** `python -m evals`

> **Baseline snapshot.** This report and the scorecards beside it record the first measurement, on 2026-10-11.
> Finding 1 was fixed on 2026-10-12 and three scenarios were added; current results are in the
> [current report](../evals/golden-set-report.md).

## Overview

The three projects explain every decision they make, but until now nothing measured whether those decisions are
right. This evaluation replays 35 hand-labeled cases through the projects' production code and compares each
decision with what a fraud analyst or compliance analyst would decide: 11 card transactions for the risk
classifier (Project 1), 10 for the fraud swarm (Project 2) and 14 customer onboarding applications for the KYC/AML
platform (Project 3). Each project was measured in its two modes: the deterministic rules it uses without an API
key, and Claude Haiku 4.5 in every agent node.

The two fraud projects make the right call on most transactions in both modes: 10 of 11 and 8 of 10 with rules,
9 of 11 and 8 of 10 with Claude. The KYC platform does not. With rules it reaches the right decision on 7 of 14
applications and approves 7 of the 9 applications an analyst would have stopped, including an applicant whose
name exactly matches the UN sanctions list, a passport flagged for tampering and an expired passport. It never
screened that applicant against sanctions lists at all, because a built-in rule skips screening for individual
applicants who live in low-risk countries. With Claude the KYC decision is right on 12 of 14 applications, but
several of those are right for the wrong reason: the model invents document problems (for example "the passport
has no address", which passports never do), escalates on them, and in 8 of 14 applications sanctions screening
never runs. An exact match on the OFAC and UN lists was escalated as a document problem instead of being rejected,
so the reviewer would receive the case without the sanctions hit.

The evaluation also runs in CI. Pointed at an unmerged branch that tunes two scoring thresholds, it failed 8
checks: on that branch the exact OFAC and UN match is approved. Every miss below traces to a specific code path,
with a proposed fix. Nothing is fixed in this change; this change measures.

## Headline results

Thirty-five scenarios: one scenario moves a percentage by seven to ten points, so counts are shown. "Should-stop"
cases are those whose label does not accept approval; "legitimate" cases are those whose label requires
approval. The three Claude runs produced identical decisions, so one figure stands for all three.

| Project | Measure | Rules (deterministic, CI gate) | Claude Haiku 4.5 (3 runs, identical) |
|---|---|---|---|
| P1 Risk classifier | Recommended action correct | 91% (10 of 11) | 82% (9 of 11) |
| P1 Risk classifier | Should-stop transactions approved | 1 of 6 | 0 of 6 |
| P1 Risk classifier | Legitimate transactions approved | 3 of 3 | 1 of 3 |
| P2 Fraud swarm | Recommended action correct | 80% (8 of 10) | 80% (8 of 10) |
| P2 Fraud swarm | Specialist risk levels correct (secondary) | 93% (27 of 29) | 90% (26 of 29) |
| P2 Fraud swarm | Should-stop transactions approved | 1 of 5 | 0 of 5 |
| P2 Fraud swarm | Legitimate transactions approved | 3 of 3 | 2 of 3 |
| P3 KYC/AML | Compliance decision correct | 50% (7 of 14) | 86% (12 of 14) |
| P3 KYC/AML | Should-stop applications approved | 7 of 9 | 1 of 9 |
| P3 KYC/AML | Legitimate applications approved | 4 of 4 | 4 of 4 |
| P3 KYC/AML | Sanctions screening ran (required for every applicant) | 36% (5 of 14) | 43% (6 of 14) |
| P3 KYC/AML | Escalated to a human when required | 50% (5 of 10) | 100% (10 of 10) |
| P3 KYC/AML | Risk tier correct | 67% (6 of 9) | 67% (6 of 9) |
| P3 KYC/AML | Every graded check correct | 14% (2 of 14) | 21% (3 of 14) |
| All | Runs that crashed, failed an API call or silently fell back to rules | 0 of 35 | 0 of 105 scenario runs (381 LLM calls) |

The specialist row counts one check per specialist per scenario where the label grades it (29 of 30). Claude
cost $1.15 for the three runs (267,885 input and 175,625 output tokens, list price).

## Business impact

| Dimension | Finding | Evidence |
|---|---|---|
| Regulatory exposure (sanctions) | With rules, an applicant whose name exactly matches the UN list is approved without screening, and a potential OFAC match is approved without review. With Claude, an exact OFAC and UN match reaches a reviewer as a document problem, with no sanctions result attached. | P3-04, P3-05 (rules); P3-03 (Claude) |
| Onboarding fraud | With rules, a tampered passport, an expired passport, a passport that expired five weeks before applying, and a proof of address in another person's name are all approved at low risk. | P3-06, P3-07, P3-09, P3-10 |
| Governance | A foreign politically exposed person running a crypto exchange is approved automatically with enhanced due diligence, where FATF Recommendation 12 requires senior-management approval. | P3-12 (rules) |
| Card fraud loss | The swarm's rules ignore Tor, VPN and location entirely, and its averaging turns a decisive synthetic-identity signal into a review instead of a decline. | P2-07 (rules), P2-04 (both modes) |
| Customer friction | Claude sends 2 of 3 legitimate P1 transactions and 1 of 3 legitimate P2 transactions to manual review (a traveler, a VPN user, a loyal customer reordering from a saved cart); the rules approve all six. | P1-04, P1-05, P2-02 (Claude) |
| Change safety | The CI gate fails an unmerged threshold change that would have approved an exact sanctions match and flagged a saved-cart reorder for review. | `fix/tune-risk-thresholds`, 8 failed checks |
| Reliability | No crashes, no API failures and no silent fallbacks in 381 LLM calls. Two crash paths visible in the code were never triggered, so they remain unverified rather than absent. | All runs |

All data is synthetic and the projects are a portfolio, so no real customer was affected. The dimensions describe
what each behavior would cost in a production onboarding or payments flow.

## Findings

Ranked by impact. Each finding is verified by the scenario results cited and by reading the code at the lines
given. Paths are relative to each project directory.

### 1. KYC rules skip sanctions screening for low-risk individuals, so a UN-listed name is approved

- **What happened.** An Iranian national living in the US, whose name exactly matches a UN Consolidated List entry,
  was approved at low risk (P3-04). Sanctions screening never ran. Under the rules, screening ran for only 5 of 14
  applicants: 8 were skipped by the rule and 1 was escalated before screening (P3-08).
- **Evidence.** `src/mock_llm.py:131` skips screening when the country of residence is in `LOW_RISK_COUNTRIES`
  (line 50), the applicant is an individual and expected volume is under $10,000 a month. Nationality is not
  considered. The supervisor prompt in `src/supervisor.py:42` offers the same skip to the LLM.
- **Why it matters.** Sanctions screening is a list check that applies to every customer; a risk-based approach
  varies the depth of due diligence, not whether a customer is screened. The README presents the skip as a cost
  saving (its own unmeasured estimate is about a fifth of the cost); the screening it skips is a simulated lookup
  against six names.

### 2. KYC rules approve potential sanctions matches without review

- **What happened.** "Ahmed Al Rasheed", a common transliteration of the OFAC-listed "Ahmed Al-Rashidi", scored a
  0.6 match and was approved at medium risk with an annual review (P3-05).
- **Evidence.** Only a match above 0.8 changes the outcome (`src/graph.py:233`, `src/mock_llm.py:102`). A hit
  between the 0.4 alert threshold and 0.8 only adds a quarter of its score to the composite risk.
- **Why it matters.** An alert above the matching threshold must be dispositioned by an analyst before the
  relationship starts. Most such alerts are false positives, which is exactly why a person, not software, clears
  them.

### 3. KYC rules record document defects and then ignore them

- **What happened.** An expired passport (P3-06) and a passport flagged for tampering (P3-10) were both approved at
  low risk. Both defects appear in the platform's own `issues_found` list ("Document 1 (passport) is expired",
  "Tampering detected on document 1"); the final decision never reads it.
- **Evidence.** The only document gate is `overall_document_quality < 0.3` (`src/mock_llm.py:79`). One expired
  passport alongside a valid utility bill scores 0.75; one tampered passport alongside a valid bill scores 0.82
  (P3-06 and P3-10 in `scorecard.json`). The final decision
  (`src/graph.py:213` onward) consults sanctions, risk tier, identity and escalation only.
- **Related defect (P3-07).** The document tool decides expiry against a fixed date, `"2026-03-26"`
  (`src/tools.py:104`), not the application date. A passport that expired on 2026-08-31, five weeks before the
  application, is treated as valid. This one also defeats Claude, because the document agent is never told the
  application date.
- **Why it matters.** A suspected forged identity document is a fraud indicator that calls for refusal and
  possibly a suspicious activity report, never an automatic approval.

### 4. With Claude, the KYC supervisor escalates on invented document problems and defers sanctions screening

- **What happened.** In 8 of 14 applications, in every run, the LLM supervisor routed to human review directly
  after document intake, so identity verification, sanctions screening and risk assessment never ran. In four of
  them the document problems were real (expired, tampered, mismatched names, another person's bill) and escalation
  was right. In the other four (P3-03, P3-04, P3-12, P3-13) the documents were genuine and the LLM document agent
  invented issues: "passport missing address field" (passports carry no address), "extraction confidence below
  0.90 threshold" (no such threshold exists; 0.85 is a normal reading), "business registration lacks expiry date".
- **Evidence.** For the exact OFAC and UN match (P3-03), the supervisor's recorded reason begins: "Document intake
  completed with quality score 0.94, but multiple critical issues identified: (1) Passport extraction confidence
  below threshold (0.854 vs 0.90 required), (2) Missing address field...". For the UN-listed applicant (P3-04) it
  adds that the issues "must be resolved before proceeding to identity verification and sanctions screening".
  Routes and document issues are in `claude-run-1.json` to `claude-run-3.json`; the supervisor's full reasoning was
  captured in a reproduction run (see How to reproduce).
- **Why it matters.** P3-04 and P3-12 count as correct escalations, but the reviewer receives a document-quality
  case. If they clear the invented issues, nothing in the case tells them the applicant matches a sanctions list.
  P3-03 is scored as a miss: an exact match should be rejected and reported, not left pending as a document query.
  The 86 percent (12 of 14) decision accuracy therefore overstates how safely the LLM mode would operate.

### 5. A foreign PEP is approved automatically (rules)

- **What happened.** A Nigerian minister applying for a $250,000-a-month crypto-exchange account was approved at
  high risk with enhanced due diligence, quarterly review and PEP monitoring (P3-12).
- **Evidence.** A high risk tier maps to "approved" with conditions (`src/graph.py:249`); PEP status adds
  conditions but never escalates.
- **Why it matters.** FATF Recommendation 12 requires senior-management approval before establishing a
  relationship with a foreign PEP. The conditions are right; the automatic approval is not. Claude escalated this
  case in every run.

### 6. The swarm's rules ignore Tor, VPN and location

- **What happened.** A purchase through a Tor exit node abroad, on a device never seen on an established account,
  was approved at low risk (P2-07). All three specialists rated it low.
- **Evidence.** `mock_identity_assess` (`src/mock_llm.py:125`) receives the geolocation result and never reads it;
  no other specialist receives it. Geolocation is collected on every transaction and has no effect on any rules
  decision. Claude's identity specialist, which is shown the same data, rated it high and the swarm sent it to
  review in every run.

### 7. Averaging lets one clean specialist dilute a decisive one (both modes)

- **What happened.** A synthetic identity (disposable email, account under a week old, unverified phone, failed
  address check, new device, $899 of electronics) went to review instead of decline in both modes (P2-04). The
  identity specialist rated it high (rules, 0.87) and critical (Claude, 0.92); the behavioral specialist correctly
  saw a human-paced session and rated it low, and the mean of the three scores landed in the review band.
- **Evidence.** The final level and action come from the mean of the three specialist scores
  (`src/adjudicator.py:70`). The LLM adjudicator is asked for a final risk level and action
  (`src/adjudicator.py:53`), but only its agreement score and confidence adjustment are kept (line 159); its
  verdict is discarded.
- **Why it matters.** A careful fraudster produces a normal-looking session. A design in which a clean behavioral
  view offsets a decisive identity view rewards exactly that.

### 8. Claude adds friction for legitimate customers in the fraud projects

- **What happened.** In every run, Claude sent a traveler paying for dinner in London on their usual phone (P1-04),
  a customer who always shops through a VPN (P1-05) and a loyal customer reordering pet food from a saved cart in 28
  seconds (P2-02) to manual review. The rules approved all three.
- **Evidence.** P1 summaries cite the location mismatch and VPN as needing verification. In P2-02 the behavioral
  specialist rated the fast checkout medium (0.62), which drops the agreement score below 0.5 and bumps the approval
  to review (`src/adjudicator.py:88`).
- **Why it matters.** Claude's caution also corrects two rules misses (P1-10 and P2-07, both caught in every run),
  so on decision accuracy the modes are close in P1 and equal in P2; the cost of the LLM mode is shifted onto
  legitimate customers rather than reduced.

### 9. Smaller findings

- **P1 rules approve an unrecognized device behind a VPN** (P1-10). Each signal alone stays under its threshold and
  the combination rule averages them (`src/mock_llm.py:134`), although the project's own prompt names "new device
  plus VPN" as a risky combination. Claude reviewed it in every run.
- **KYC risk tiering ignores nationality and cash-intensity** (P3-11, P3-14, and P3-04's tier). Country risk uses
  residence only (`src/tools.py:663`). Cash-intensive income declared at $9,800 a month is rated low; the
  structuring flag for $8,000 to $12,000 (`src/tools.py:502`) appears in the narrative and never in the score. A
  Brazilian real-estate business is rated low. Claude rated P3-11 and P3-14 low as well.
- **The swarm's identity specialist ignores two past chargebacks** (P2-10, both modes): it rates the customer low.
  In the rules, the history only reaches medium at three chargebacks.
- **The simulated geolocation contradicts itself.** `lookup_geo` draws the city independently of the country
  (`src/tools.py:85` in P1, line 78 in P2), producing, for example, "Germany, Moscow". Claude reads that as a red
  flag. The evaluation's scenarios now pin a coherent pair; the projects' own demo data still has the problem.
- **README and CLAUDE.md drift.** The KYC README says the rules are "validated through extensive testing"; there
  were no tests. CLAUDE.md gives `python -m src.main` for Project 3, which prints nothing; `python -m src` runs it.

### 10. The CI gate catches the pending threshold change

- **What happened.** Run against `origin/fix/tune-risk-thresholds` (changes `checkout_speed < 15` to `< 150` in P2
  and the fuzzy-name weight `0.6` to `0.06` in P3) in a temporary worktree, `python -m evals --check` exited 1 with
  8 regressed checks: P2-02 action, risk level and behavioral specialist (the saved-cart reorder goes to review);
  P2-08 behavioral specialist; P3-03 decision, escalation and risk tier (the exact OFAC and UN match scores 0.46
  instead of 1.0 and is approved at high risk with enhanced due diligence); P3-05 risk tier (the potential match
  drops below the alert threshold).
- **Also run:** open PR #2's head (`origin/test/parallel-agent-edits`) passes with no regressions. Its velocity
  change sets a flag that the rules never read, so the gate cannot see it; the LLM tier would.
- Neither branch was modified or pushed; the worktrees were removed.

## Proposed fixes

Not implemented in this change. Each alters decisions, so each needs its own review, and each should add at least
one new scenario so the fix is not fitted to this set.

| # | Change | Targets |
|---|---|---|
| 1 | Screen every applicant, including names on secondary documents; remove the low-risk skip from the rules and the supervisor prompt. | P3-01, 04, 06, 07, 09 to 11, 13 |
| 2 | Escalate any match at or above the alert threshold; reject and escalate a confirmed match. | P3-05 |
| 3 | Make the final decision read document validation: expired or wrong type escalates, tampered rejects and refers to fraud review. Compute expiry against the application date and pass that date to the document agent. | P3-06, 07, 10 |
| 4 | Verify identity across all documents; require the proof-of-address holder to be the applicant. | P3-09 |
| 5 | Escalate foreign PEPs for senior-management approval. | P3-12 |
| 6 | In the LLM mode, run sanctions screening as a fixed step before any supervisor decision, let only tool-backed document flags trigger escalation, and give the document agent basic document facts (passports carry no address). | P3-03, 04, 12, 13 (Claude) |
| 7 | Use the higher of nationality and residence risk; count cash-intensive income and the structuring flag; revisit sector weights. | P3-04, 11, 14 |
| 8 | Feed geolocation into the identity rules; let a high-confidence specialist set a floor on the final verdict instead of averaging it away; either use the LLM adjudicator's verdict or stop asking for it. | P2-04, 07 |
| 9 | Add a combination rule for an unrecognized device behind an anonymizer. | P1-10 |
| 10 | Give the LLM prompts examples of legitimate travel, VPN use and saved-cart checkouts. | P1-04, 05, P2-02 (Claude) |
| 11 | Make the simulated geolocation return a city in the chosen country. | Demo data, LLM mode |

## What is verified, inferred and not yet checked

- **Verified:** every number in this report is generated by the harness (`scorecard.json`, `claude-run-N.json`,
  `scorecard-claude.json`). Three rules-tier runs produced byte-identical scorecards. The CI gate fails on a
  planted regression (`P1-10: action regressed (pass -> fail)`), on evidence drift, and on the threshold branch
  (exit 1, 8 checks). The workflow's install path was run in a fresh virtual environment (Windows; CI uses
  Ubuntu). The three Claude runs made 381 calls, all answered by `claude-haiku-4-5-20251001`, with 0 failures and 0
  silent fallbacks, and returned identical decisions and summaries. A fourth run on 2026-10-12, after the fix,
  reproduced every graded result outside the KYC changes the fix made, but not the summary text, so the runs are
  reproducible at the decision level, not word for word. The code causes above were confirmed by
  reading the cited lines.
- **Inferred:** that the labels are what most analysts would decide. They were written by one author from each
  narrative before the pipeline ran. Costs are estimates from response token counts at list price
  ($1 per million input tokens, $5 per million output tokens).
- **Not yet checked:**
  - Run-to-run variance. At temperature 0 the three runs were identical, so they show reproducibility, not a
    spread; a non-zero temperature or another model may behave differently.
  - Two crash paths visible in the code never occurred: a supervisor reply naming a step outside the routing map
    (`src/graph.py:48`), and risk assessment running before identity verification, which leaves no PEP result
    (`src/agents/risk_assessment.py:57`). The harness records such crashes as errors if they happen.
  - Other models, and the projects' OpenAI path.

## Limitations

- **One labeler.** A second fraud reviewer and a second compliance reviewer should review the labels before the
  numbers drive decisions. Two specialist-level labels are arguably too strict and are left as written: P2-04
  accepts only "high" for the identity specialist, which Claude rated "critical"; P2-05 expects "high or critical"
  for a behavioral view that, on its evidence alone (a 6-second checkout within a 27-minute session with human
  input), a reviewer could rate medium. Both affect only the secondary specialist row.
- **Small sample.** 11, 10 and 14 scenarios. Percentages move in steps of seven to ten points.
- **Hand-authored scenarios on simulated sources.** The evidence is synthetic and limited by the simulators: for
  example the P1 and P2 velocity source keeps a customer's 30-day average between $50 and $500.
- **Evidence was tightened once, after the first Claude run.** That run showed evidence the narratives did not
  intend (a city inconsistent with its country, low name-email match on established identities, document numbers
  made of zeros), which the model reasonably read as red flags. The scenarios were tightened to their narratives,
  no label changed, and all three runs were repeated; the superseded run is not reported. In the same pass P2-10
  was pinned to two chargebacks because "two or three" straddled the specialist's threshold.
- **Two narratives were corrected after the reported runs.** P1-11 and P2-08 described the amount as two to three
  times and about twice the customer's average; the tools actually return about 1.6 times (the tool's
  `amount_deviation_factor` is measured in units of 30 percent of the average, not as a multiple). Both narratives
  now say about one and a half times the 30-day average. Inputs, evidence and labels are unchanged, so the runs
  still apply.
- **Overfitting risk.** Tuning the rules against these scenarios inflates the numbers. Each fix should be justified
  by its narrative and add a new scenario; a held-out set becomes meaningful past about 30 scenarios per project.

## How to reproduce

```text
pip install -r evals/requirements.txt          # pinned, as in CI
python -m evals                                 # rules tier for all projects; writes docs/evals/scorecard.*
python -m evals --check                         # the CI gate: exit 1 on any regression or unscored scenario
python -m pytest                                # harness unit tests and the gate
python -m evals --only P3-04 --verbose          # one scenario, printed with its full output

# LLM tier (needs ANTHROPIC_API_KEY in the environment; a local .env cannot override it)
python -m evals --tier llm --file-stem claude-run-1 --budget-usd 1.5
python -m evals --summarize-runs                # combine claude-run-*.json into scorecard-claude.*
python -m evals --tier llm --project p3 --only P3-03 P3-04 P3-12 P3-13 --verbose   # supervisor reasoning

# The gate against another branch's product code
git worktree add --detach ../wt origin/fix/tune-risk-thresholds
python -m evals --check --product-root ../wt
git worktree remove ../wt
```

Spend for this report: $1.15 for the three reported runs, about $0.07 for smoke and reproduction runs, and $0.38
for the superseded first run. Two further runs were stopped part-way when the evidence was tightened; their spend
was not recorded and is at most $0.76. Total: at most $2.36, within the $5 cap.

## Technical reference

| Item | Location |
|---|---|
| Scenarios (one JSON file each: narrative, inputs, evidence constraints, labels, rationale) | `evals/golden/<project>/` |
| CLI | `evals/__main__.py` |
| Worker subprocess (environment, evidence check, entrypoint call, LLM and fallback accounting) | `evals/worker.py` |
| Scoring rules, approval metrics, ratchet | `evals/score.py` |
| Evidence constraint syntax | `evals/evidence.py` |
| Input-ID search used at authoring time | `evals/find_inputs.py` |
| Repeated-run summary | `evals/runs.py` |
| Ratchet baseline | `evals/baseline.json` |
| CI gate test and workflow | `evals/tests/test_gate.py`, `.github/workflows/evals.yml` |

Scoring in brief. A label `a|b` accepts either; null is not graded. P3 conditions are graded only when the pipeline
approved. A run that crashed, failed an API call, timed out or whose evidence drifted is not scored and counts as
a regression in the gate; in the LLM tier a run in which any node silently fell back to the rules is also not
scored and is counted separately. The gate also fails closed when a scenario has no baseline entry. A check that
becomes inapplicable because the output took an alternative its label accepts (P3 conditions after an accepted
escalation) is not a regression. The headline per project is the decision: P1 and P2 recommended action, P3
compliance decision.
