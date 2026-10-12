"""Repeated-run summary: stability, majority, exclusions."""

import json

from evals.runs import summarize_runs, write_summary


def _scenario(sid, status="scored", decision_ok=True, fallbacks=None):
    return {
        "id": sid,
        "title": f"title {sid}",
        "status": status,
        "checks": {"decision": decision_ok} if status == "scored" else {},
        "fallbacks": fallbacks or {},
    }


def _run(scenarios, calls=10, cost=0.01):
    return {
        "tier": "llm",
        "model": "m",
        "projects": {"p3": scenarios},
        "llm_totals": {"calls": calls, "api_errors": 0, "input_tokens": 100, "output_tokens": 50, "cost_usd": cost},
    }


def test_summary_counts_and_flags(tmp_path):
    runs = [
        _run([_scenario("P3-01"), _scenario("P3-02", decision_ok=False), _scenario("P3-03")]),
        _run([_scenario("P3-01"), _scenario("P3-02"), _scenario("P3-03", status="error")]),
        _run([_scenario("P3-01"), _scenario("P3-02", decision_ok=False), _scenario("P3-03", status="fallback", fallbacks={"supervisor": 1})]),
    ]
    summary = summarize_runs([(f"claude-run-{i + 1}", r) for i, r in enumerate(runs)])
    p3 = summary["projects"]["p3"]
    # Pooled excludes the error and the fallback: 3 + 1 + 1 graded correct of 7 graded.
    assert p3["pooled"] == {"hits": 5, "total": 7, "pct": 500 / 7}
    assert p3["counts"]["errors"] == 1 and p3["counts"]["fallbacks"] == 1
    assert p3["fallback_nodes"] == {"supervisor": 1}
    rows = {r["id"]: r for r in p3["rows"]}
    assert rows["P3-01"]["stable"] and rows["P3-01"]["correct"] == 3
    assert not rows["P3-02"]["stable"] and rows["P3-02"]["correct"] == 1
    assert p3["always"] == 2  # P3-01, and P3-03 (correct in its only graded run)
    assert p3["majority_correct"] == 1
    assert summary["totals"]["calls"] == 30

    # Stability compares scored verdicts only: correct, error, fallback is stable.
    assert rows["P3-03"]["stable"]
    assert p3["unscorable"] == 0

    for i, r in enumerate(runs):
        (tmp_path / f"claude-run-{i + 1}.json").write_text(json.dumps(r), encoding="utf-8")
    md, js = write_summary(tmp_path)
    text = md.read_text(encoding="utf-8")
    assert "(unstable)" in text and "P3-02" in text
    assert "50% (1 of 2) to 100% (2 of 2)" in text  # range carries counts
    assert json.loads(js.read_text(encoding="utf-8"))["runs"] == ["claude-run-1", "claude-run-2", "claude-run-3"]


def test_budget_skipped_runs_are_visible(tmp_path):
    runs = [_run([_scenario("P3-01"), _scenario("P3-02", status="skipped")])]
    (tmp_path / "claude-run-1.json").write_text(json.dumps(runs[0]), encoding="utf-8")
    md, _ = write_summary(tmp_path)
    text = md.read_text(encoding="utf-8")
    # One scored run out of two scenarios: the skipped one is shown, not hidden.
    assert "| claude-run-1 | 100% (1 of 1) | 0 | 0 | 1 |" in text
    assert "Skipped (budget cap reached)" in text


def test_scenario_that_never_scored_is_not_never_correct():
    runs = [
        _run([_scenario("P3-01"), _scenario("P3-05", status="fallback", fallbacks={"supervisor": 1})]),
        _run([_scenario("P3-01"), _scenario("P3-05", status="error")]),
    ]
    p3 = summarize_runs([(f"claude-run-{i + 1}", r) for i, r in enumerate(runs)])["projects"]["p3"]
    assert p3["unscorable"] == 1 and p3["never"] == 0 and p3["always"] == 1
