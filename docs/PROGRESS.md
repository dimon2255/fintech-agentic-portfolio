# Progress

Repository-level progress log. Per-project design notes stay in each project's `docs/`.

## 2026-10-11: Golden-set evaluation (branch `features/golden-set-evals`)

**Goal:** measure whether the three projects make the right decisions, with accuracy numbers, a CI gate and a
repeatable LLM-tier measurement. Method: [ADR-001](adr/001-golden-set-evaluation.md). Data flow:
[diagrams/eval-harness.md](diagrams/eval-harness.md). Results and findings:
[evals/golden-set-report.md](evals/golden-set-report.md).

| Phase | Status | Notes |
|---|---|---|
| Survey of the three projects (entrypoints, rules, thresholds, fallbacks) | Done | No tests or CI existed before this change. |
| Harness: per-project worker subprocess, scorer, ratchet, reports | Done | `evals/`; projects cannot share a process (all use package `src`). |
| Golden scenarios: P1 11, P2 10, P3 14, labels and rationale written before running | Done | `evals/golden/`; input IDs searched with `evals/find_inputs.py`. |
| Rules tier scorecard and baseline | Done | `docs/evals/scorecard.md`; three runs byte-identical. |
| CI workflow (rules-tier gate and harness tests, no secrets) | Done | `.github/workflows/evals.yml`, pinned `evals/requirements.txt`; verified in a fresh virtual environment. |
| Gate demonstration against `origin/fix/tune-risk-thresholds` and PR #2 head | Done | Fix branch fails 8 checks; PR #2 passes. Temporary worktrees removed; neither branch modified. |
| LLM tier, three runs on `claude-haiku-4-5-20251001` | Done | `docs/evals/claude-run-1..3`, `docs/evals/scorecard-claude.md`. 381 calls, 0 failures, 0 fallbacks, $1.15; the three runs were identical (temperature 0). |
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

Ranked by impact in [evals/golden-set-report.md](evals/golden-set-report.md#findings). Highlights: the KYC
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
