"""CI regression gate for decision quality (ADR-001).

Replays the full golden set in the rules tier and fails if any check recorded
as passing in evals/baseline.json now fails, or if any scenario fails to run
or its fixture evidence drifted. New passes are allowed and printed; lock them
in with `python -m evals --write-baseline`.
"""

import json

from evals import BASELINE_PATH, PROJECTS
from evals.runner import run_projects
from evals.scenario import load_project
from evals.score import compare, score_project, summarize


def test_golden_set_does_not_regress():
    selection = {key: load_project(key) for key in PROJECTS}
    responses = run_projects(selection, tier="rules")
    scores = []
    for key in PROJECTS:
        project_scores = score_project(key, selection[key], responses[key])
        summary = summarize(key, project_scores)
        print(f"{key}: headline {summary.headline.display()}, all checks {summary.all_checks.display()}")
        scores += project_scores

    unscored = [f"{s.id}: {s.status}: {s.error}" for s in scores if not s.scored]
    assert not unscored, "scenarios did not produce a scorable run:\n  " + "\n  ".join(unscored)

    baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    regressions, improvements = compare(baseline, scores)
    for line in improvements:
        print(f"IMPROVED  {line}")
    assert not regressions, "decision quality regressed against evals/baseline.json:\n  " + "\n  ".join(regressions)
