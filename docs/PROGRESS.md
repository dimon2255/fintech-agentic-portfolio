# Progress

Repository-level progress log. Per-project design notes stay in each project's `docs/`.

## 2026-10-11: Golden-set evaluation (branch `features/golden-set-evals`)

**Goal:** measure whether the three projects make the right decisions, with accuracy numbers, a CI gate and a
repeatable LLM-tier measurement. Method: [ADR-001](adr/001-golden-set-evaluation.md). Data flow:
[diagrams/eval-harness.md](diagrams/eval-harness.md). Results and findings:
[evals-baseline-2026-10-11/golden-set-report.md](evals-baseline-2026-10-11/golden-set-report.md).

| Phase | Status | Notes |
|---|---|---|
| Survey of the three projects (entrypoints, rules, thresholds, fallbacks) | Done | No tests or CI existed before this change. |
| Harness: per-project worker subprocess, scorer, ratchet, reports | Done | `evals/`; projects cannot share a process (all use package `src`). |
| Golden scenarios: P1 11, P2 10, P3 14, labels and rationale written before running | Done | `evals/golden/`; input IDs searched with `evals/find_inputs.py`. |
| Rules tier scorecard and baseline | Done | `docs/evals/scorecard.md`; three runs byte-identical. |
| CI workflow (rules-tier gate and harness tests, no secrets) | Done | `.github/workflows/evals.yml`, pinned `evals/requirements.txt`; verified in a fresh virtual environment. |
| Gate demonstration against `origin/fix/tune-risk-thresholds` and PR #2 head | Done | Fix branch fails 8 checks; PR #2 passes. Temporary worktrees removed; neither branch modified. |
| LLM tier, three runs on `claude-haiku-4-5-20251001` | Done | `docs/evals-baseline-2026-10-11/claude-run-1..3`, `docs/evals-baseline-2026-10-11/scorecard-claude.md` (moved there on 2026-10-12). 381 calls, 0 failures, 0 fallbacks, $1.15; the three runs were identical (temperature 0). |
| Independent review of the harness diff | Done | One blocker and four should-fix gaps (run summary buckets, `--check` and `--write-baseline` guard rails, unpriced-model budget, range counts); all fixed with tests. |
| Lead-facing report and README sections | Done | Root README "Evaluation"; project READMEs link to it. |

### Decisions made during implementation

- **Real tools with searched inputs instead of fixture injection** for P1 and P2. Replacing `run_all_checks` with
  fixtures would have bypassed the tools' risk-scoring code, which is product logic (the unmerged threshold branch
  changes it). Scenarios state evidence constraints; IDs are chosen so the deterministic simulators return that
  evidence, and the harness re-checks it on every run.
- **Sanctions screening is required in every KYC scenario.** The product's skip rule for low-risk domestic
  individuals is graded as a miss. Misses are broken down in the report into "skipped by rule" and "never reached
  because the case was escalated first".
- **Silent fallbacks are excluded from LLM-tier accuracy** and counted separately (decided before the first LLM
  run).
- **No LLM judge**: every graded field is categorical.
- **Evidence tightened once after the first LLM run.** It exposed evidence the narratives did not intend (a city
  inconsistent with its country, low name-email match on established identities, document numbers made of zeros).
  Scenarios were tightened to their narratives with no label change, and all three runs were repeated; the
  superseded run is not reported. P2-10 was pinned to two chargebacks because "two or three" straddled a threshold.
- **Two lead-facing metrics computed by the harness**: legitimate cases approved (false positives) and should-stop
  cases approved.

### Known issues (product defects found, not fixed here)

Ranked by impact in [the baseline report](evals-baseline-2026-10-11/golden-set-report.md#findings). Highlights: the KYC
sanctions-screening skip rule approves a UN-listed name; potential sanctions matches, expired documents, tampered
documents and third-party proof of address are all approved by the rules; in LLM mode the KYC supervisor escalates
on invented document issues before sanctions screening runs; the fraud swarm ignores Tor, VPN and geolocation in
its rules and averages away a decisive identity signal; the LLM adjudicator's own verdict is discarded. None is
fixed in this change.

### Follow-ups

- Second-reviewer pass on all labels (fraud and compliance).
- Fix the findings one at a time, each with a new scenario, re-running the evaluation after each.
- Grow the set past 30 scenarios per project so a held-out split is meaningful.
- Pin the LLM-tier model per run and compare models (for example a newer Haiku) on the same scenarios.

## 2026-10-12: Mandatory sanctions screening and re-measurement

**Goal:** fix golden-set finding 1 (the KYC platform skipped sanctions screening for low-risk individuals and approved
an exact UN-list name), test the fix on new cases, re-measure, and reconcile the documentation with the code and the
measured results. Current results: [evals/golden-set-report.md](evals/golden-set-report.md).

| Phase | Status | Notes |
|---|---|---|
| Fix: screening mandatory in both modes, enforced in `supervisor_node` | Done | Earlier escalations are deferred until screening completes, not dropped (a first version dropped them and approved an expired passport in LLM mode; caught by measurement before commit). |
| New scenarios P3-15, P3-16, P1-12 (labels before running) | Done | EU-list match at the old skip boundary; Arabic-name false-positive control; velocity flag boundary from PR #2. |
| Rules re-baseline and gate | Done | 0 regressions; KYC decision 10 of 16 (was 7 of 14); screening 16 of 16. |
| Claude run 4 (one run, $0.47) | Done | KYC decision 15 of 16 (was 12 of 14); 0 failures, 0 fallbacks in 166 calls. |
| Documentation reconciled with code and measurements | Done | Swarm verdict described as an unweighted mean; audit trail no longer called immutable; costs recomputed from measured tokens; skip-logic claims removed. |

### Decisions made during implementation

- **Baseline results archived, not overwritten.** The 2026-10-11 report and scorecards moved to
  `docs/evals-baseline-2026-10-11/` so `--summarize-runs` does not pool pre-fix and post-fix runs.
- **The scenario-count test no longer caps a project at 15**, since ADR-001 plans to grow past 30.
- **Independent review of the diff: no blockers, nine should-fix items.** Fixed: a deferred escalation now reaches the
  reviewer with its original reason; screening also runs before risk assessment if the LLM supervisor tries to skip
  ahead; the P1-12 narrative now states the 24 transactions in the past day that the tool returns (pinned as evidence;
  inputs and labels unchanged); the P3-16 rationale, a cost rounding, a stale docstring and two compliance-mapping
  claims were corrected.
- **Claude run 4 predates the review hardening.** For its recorded replies the routes are unchanged (the
  risk-before-screening path did not occur, and the guard's text is not sent to the LLM); only the guard's reasoning
  text in those records differs from what the current code writes.

### Known issues (not fixed here)

- Baseline findings 2 to 9 remain open; status table in the current report.
- The document tool checks expiry against a fixed date (`project-3-kyc-platform/src/tools.py:104`); fixing it needs
  the application date passed to the tool, not a one-line change.
- `datetime.utcnow()` is deprecated in Python 3.12 (15 call sites in P1 and P2); left as is.
- The supervisor's `next_step` is not validated (pre-existing): an LLM reply naming an unknown step raises a
  `KeyError`, and one that repeats a completed step can loop until LangGraph's recursion limit.

