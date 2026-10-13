# ADR-001: Golden-Set Evaluation of Decision Quality

**Status:** Accepted (2026-10-11); amended 2026-10-13 (default model, see the end)

**Scope:** all three projects. This is the first repository-level ADR; each project keeps its own ADRs in
`project-*/docs/adr/`. The evaluation lives at the root because it spans all three projects and compares them
with one method.

## Context

The three projects make decisions that matter in regulated financial services: approve, review or decline a card
transaction (Project 1, Project 2), and approve, reject or escalate a customer onboarding application
(Project 3). Each project explains its reasoning, but nothing measured whether the decisions are right. There were
no tests and no CI. The READMEs list an evaluation framework and a calibration framework as future work.

Two properties of the code shape how an evaluation can work:

- **The agents have two modes.** With no API key, every agent runs deterministic rules (`src/mock_llm.py`). With
  a key, every agent node calls an LLM (default `claude-haiku-4-5-20251001`). When an LLM reply cannot be parsed,
  the node silently uses the rules instead (P2, P3) or emits a fixed medium-risk "review" assessment (P1). Nothing
  in the output says this happened.
- **The data sources are simulated and deterministic.** Each project's `tools.py` derives its observations from
  MD5 hashes of input identifiers (customer, IP, device and email in P1 and P2; document numbers and names in P3),
  then computes risk scores from those observations. The scoring code in `tools.py` is product logic: an unmerged
  branch (`fix/tune-risk-thresholds`) changes exactly that code.

The three projects all use the top-level package name `src`, so they cannot be imported into one Python process.

## Decision

Add a **golden-set evaluation**: hand-labeled scenarios replayed through each project's production entrypoint and
scored against what a competent fraud or compliance analyst would decide.

1. **Real pipeline, real tools, controlled inputs.** Each scenario runs the unmodified entrypoint
   (`classify_transaction`, `analyze_transaction`, `run_kyc_application`) with the project's own tools, prompts,
   thresholds and routing. The harness sets only the scenario inputs and sets `SIMULATED_LATENCY_SECONDS` to zero.
   Instead of replacing the tools with fixtures, each scenario states the evidence its narrative relies on as
   constraints over the tools' raw observations (for example "VPN true, Tor false, device never seen, 0 to 1
   transactions in the past hour"), and its input IDs are chosen so the deterministic simulated sources return
   that evidence (`evals/find_inputs.py`, run once at authoring time). The harness checks the constraints on every
   run by calling the project's own tool functions; if they no longer hold, the scenario is reported as evidence
   drift and not scored. Constraints cover raw observations only, never derived scores, so a change to scoring
   logic shows up as a changed decision, not as drift. This keeps the tools' risk-scoring code under test, which a
   fixture replacement of `run_all_checks` would have bypassed.
2. **One worker process per project.** `python -m evals` starts one subprocess per project with that project as
   its working directory, sends the scenarios as JSON and reads back plain JSON results. The scorer never imports
   project code.
3. **Labels describe the case, not the code.** Every label was written from the scenario narrative before the
   pipeline ran on it, with a rationale. Where analysts would accept more than one answer the label says so
   (`"review|decline"`); a null label means that check is not graded for the scenario. Labels are never edited to
   match an output. Positions taken in the KYC labels, stated here so a reviewer can challenge them:
   - Sanctions screening is required for every applicant. It is a list check that applies to all customers; a
     risk-based approach varies the depth of due diligence, not whether a customer is screened.
   - A confirmed exact sanctions match is rejected and escalated to the compliance officer for reporting. A
     potential match (a name variant above the alert threshold) is held for analyst disposition: escalated.
   - A foreign politically exposed person (PEP) needs senior-management approval (FATF Recommendation 12), so an
     automatic approval is wrong even with enhanced due diligence (EDD) attached. A domestic PEP with an otherwise
     low-risk profile may be approved with EDD and PEP monitoring.
   - An expired or tampered identity document cannot support approval.
4. **What is graded.** P1: risk level and recommended action. P2: final risk level and action, plus each
   specialist's risk level as a secondary diagnostic. P3: decision, risk tier, whether a human was involved
   (`was_escalated`), whether sanctions screening ran when required, and whether EDD and PEP conditions are
   attached to approvals that require them. The headline per project is decision accuracy (P1 and P2 recommended
   action, P3 compliance decision). Every percentage is reported with its count.
5. **A failed run is never scored.** Crashes, API errors, timeouts and evidence drift are counted separately and
   excluded from every accuracy figure. In the LLM tier, a scenario run in which any node silently fell back is a
   measurement of the fallback, not of the LLM, and is also excluded and counted. The harness detects fallbacks by
   wrapping the projects' fallback functions (P2, P3) and by the fixed summary text of the P1 fallback; the
   wrappers call through unchanged.
6. **Rules tier is the CI gate.** With both API keys empty the pipeline is deterministic (three runs produced
   byte-identical scorecards). `evals/baseline.json` records which checks pass per scenario, and
   `.github/workflows/evals.yml` fails if any recorded pass regresses, any scenario fails to run, or any scenario
   has no baseline entry. A check that becomes inapplicable because the output took an alternative its label
   accepts (for example P3 conditions after an accepted escalation) is not a regression. New passes are allowed and
   locked in with `--write-baseline`, which refuses to record regressions. In this tier the harness also makes any LLM call raise, which
   proves the gate never reaches the network and needs no secrets.
7. **LLM tier is opt-in, real Claude, three runs.** `python -m evals --tier llm` runs every agent node on
   `claude-haiku-4-5-20251001` through the projects' own LangChain code, with the key taken from the process
   environment (python-dotenv does not override existing variables; the worker verifies this after import and
   refuses to run otherwise). Each run is written to `docs/evals/claude-run-N.md/json`; `--summarize-runs` writes
   `scorecard-claude.md/json` with per-run and pooled accuracy, stability, errors, fallbacks, tokens and cost. A
   per-run spending cap stops new scenarios once reached.
8. **No LLM judge.** Every graded field is categorical (a level, an action, a decision, a flag), so all grading is
   deterministic. A judge would only be warranted for free-text reasoning, which this evaluation does not grade.

## Consequences

- Decision quality becomes a number per project that can move, and a change to thresholds or rules is judged by
  its effect on the scorecard. Demonstrated on 2026-10-11: run against the unmerged `fix/tune-risk-thresholds`
  branch, the gate failed eight checks, including an exact OFAC and UN sanctions match that the branch approves.
- The first run measures the projects as they stand. Low scores are findings about the projects, not defects in
  the evaluation. The analysis is in `docs/evals-baseline-2026-10-11/golden-set-report.md`; results after the
  2026-10-12 sanctions fix are in `docs/evals/golden-set-report.md`.
- **One labeler.** Every label was written by one author. A second fraud or compliance reviewer should review
  them before the numbers drive decisions.
- **Small sample.** 11, 10 and 14 scenarios at first, 12, 10 and 16 since 2026-10-12: one scenario moves a
  percentage by six to ten points. Counts are always shown.
- **Hand-authored scenarios on simulated sources.** The evidence is synthetic, and the simulated sources limit
  what a scenario can express. For example, the P1 and P2 velocity source draws a customer's 30-day average from
  $50 to $500, so a customer who habitually makes large purchases cannot be represented.
- **Overfitting risk.** Tuning the rules against the same scenarios that score them inflates the numbers. Labels
  are fixed before tuning, a change made to improve a score must be justified by its scenario narrative, and each
  such change should add a new scenario. A held-out set becomes meaningful once the set is larger.
- **Coupling to the simulators.** If a change to a simulated source alters the raw evidence (for example the
  draw order in a tool), affected scenarios report evidence drift, and their IDs must be searched again with
  `python -m evals.find_inputs`. The labels do not change.

## Amendment (2026-10-13): default model

The projects' default model, and so the LLM tier's default, moved from `claude-haiku-4-5-20251001` to
`claude-haiku-5-5`. Where this ADR names Haiku 4.5 it describes the runs recorded on 2026-10-11 and 2026-10-12, which
remain the LLM-tier baseline. Decision 7 is amended as follows. Haiku 5.5 rejects a non-default temperature, so Claude
models are now called with no temperature, `effort="low"` and `max_tokens=8192` (each project's `src/llm.py`), and the
stability seen at temperature 0 must be measured again rather than assumed. Haiku 5.5 also thinks by default, so a
reply can arrive as thinking and text blocks; the projects parse only the text, which keeps a thinking block from being
counted as an unparseable reply and a silent fallback. Runs of a new model are written to their own folder with
`--out-dir`, because `--summarize-runs` refuses to pool runs of different models.
