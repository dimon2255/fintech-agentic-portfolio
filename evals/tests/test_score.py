"""Scorer and ratchet rules (pure, no project imports)."""

from evals.score import (
    EDD_CONDITION,
    ScenarioScore,
    baseline_entry,
    compare,
    missing_from_baseline,
    grade_p1,
    grade_p2,
    grade_p3,
    label_matches,
    score_scenario,
    summarize,
)


def test_label_alternatives_and_case():
    assert label_matches("review|decline", "decline")
    assert label_matches("review|decline", "Review")
    assert not label_matches("review|decline", "approve")
    assert label_matches(None, "anything") is None
    assert label_matches(True, True) and not label_matches(True, False)
    assert not label_matches("low", None)


def test_p1_and_p2_grading():
    assert grade_p1({"risk_level": "low", "recommended_action": "approve"}, {"risk_level": "low", "recommended_action": "approve"}) == {
        "action": True,
        "risk_level": True,
    }
    out = {
        "risk_level": "medium",
        "recommended_action": "review",
        "specialists": {"velocity": {"risk_level": "low"}, "identity": {"risk_level": "high"}, "behavioral": {"risk_level": "low"}},
    }
    checks = grade_p2(
        {"risk_level": "medium", "recommended_action": "review", "specialists": {"velocity": "low", "identity": None, "behavioral": "medium"}},
        out,
    )
    assert checks["specialist_velocity"] is True
    assert checks["specialist_identity"] is None
    assert checks["specialist_behavioral"] is False


def _p3_out(decision="approved", conditions=(), screening="completed", escalated=False, tier="low"):
    return {
        "decision": decision,
        "risk_tier": tier,
        "was_escalated": escalated,
        "conditions": list(conditions),
        "checklist": {"sanctions_screening": screening},
    }


def test_p3_screening_required_means_completed():
    exp = {"decision": "approved", "sanctions_screening_required": True}
    assert grade_p3(exp, _p3_out(screening="completed"))["screening"] is True
    assert grade_p3(exp, _p3_out(screening="skipped"))["screening"] is False
    assert grade_p3(exp, _p3_out(screening="pending"))["screening"] is False


def test_p3_conditions_graded_only_on_approvals():
    exp = {"decision": "approved|escalated", "sanctions_screening_required": True, "edd_required": True, "pep_monitoring_required": True}
    ok = _p3_out(conditions=[EDD_CONDITION, "PEP monitoring: senior_official"])
    assert grade_p3(exp, ok)["conditions"] is True
    assert grade_p3(exp, _p3_out(conditions=[EDD_CONDITION]))["conditions"] is False
    assert grade_p3(exp, _p3_out(decision="escalated"))["conditions"] is None
    clean = {"decision": "approved", "sanctions_screening_required": True, "edd_required": False}
    assert grade_p3(clean, _p3_out())["conditions"] is True
    assert grade_p3(clean, _p3_out(conditions=[EDD_CONDITION]))["conditions"] is False


SCENARIO = {"id": "P1-99", "title": "t", "category": "c", "expected": {"risk_level": "low", "recommended_action": "approve"}}


def test_failed_runs_are_never_scored():
    s = score_scenario("p1", SCENARIO, {"status": "error", "error": "boom"})
    assert s.status == "error" and s.checks == {}
    drift = score_scenario("p1", SCENARIO, {"status": "harness_error", "error": "evidence drift"})
    assert drift.status == "harness_error"
    summary = summarize("p1", [s, drift])
    assert summary.headline.total == 0 and summary.errors == 1 and summary.harness_errors == 1


def test_llm_fallback_excluded_from_accuracy():
    result = {"status": "ok", "output": {"risk_level": "low", "recommended_action": "approve"}, "fallbacks": {"assess_risk": 1}}
    s = score_scenario("p1", SCENARIO, result, tier="llm")
    assert s.status == "fallback"
    assert summarize("p1", [s]).headline.total == 0
    # The same output in the rules tier is a normal scored run.
    assert score_scenario("p1", SCENARIO, result, tier="rules").status == "scored"


def test_llm_api_error_is_never_scored_even_without_a_crash():
    # A failed call that the pipeline swallowed and still produced an output.
    result = {
        "status": "ok",
        "output": {"risk_level": "low", "recommended_action": "approve"},
        "llm": {"calls": 2, "api_errors": 1},
    }
    s = score_scenario("p1", SCENARIO, result, tier="llm")
    assert s.status == "error" and s.checks == {}
    assert "1 LLM call(s) failed" in s.error
    assert summarize("p1", [s]).headline.total == 0 and summarize("p1", [s]).errors == 1


def _scored(sid, **checks):
    return ScenarioScore(id=sid, title="t", category="c", status="scored", checks=checks)


def test_check_not_applicable_under_an_accepted_alternative_is_not_a_regression():
    baseline = {"P3-13": {"decision": True, "conditions": True}}
    # Escalated under "approved|escalated": decision passes, conditions not graded.
    regressions, _ = compare(baseline, [_scored("P3-13", decision=True, conditions=None)])
    assert regressions == []
    # If the decision itself is wrong, both the decision and the lost check regress.
    regressions, _ = compare(baseline, [_scored("P3-13", decision=False, conditions=None)])
    assert regressions == ["P3-13: conditions regressed (pass -> not graded)", "P3-13: decision regressed (pass -> fail)"]
    # --write-baseline records only graded checks, so it can record the new state.
    assert baseline_entry(_scored("P3-13", decision=True, conditions=None)) == {"decision": True}


def test_missing_baseline_entries_are_reported():
    scores = [_scored("P1-01", action=True), _scored("P1-02", action=False)]
    assert missing_from_baseline({}, scores) == ["P1-01", "P1-02"]
    assert missing_from_baseline({"P1-01": {"action": True}}, scores) == ["P1-02"]


def test_ratchet_detects_regressions_and_improvements():
    baseline = {"P1-01": {"action": True, "risk_level": False}, "P1-02": {"action": True}, "P1-03": {"action": True}}
    scores = [
        _scored("P1-01", action=False, risk_level=True),
        ScenarioScore(id="P1-02", title="t", category="c", status="error", error="timeout"),
    ]
    regressions, improvements = compare(baseline, scores)
    assert "P1-01: action regressed (pass -> fail)" in regressions
    assert any(r.startswith("P1-02: action regressed (pass -> error") for r in regressions)
    assert "P1-03: scenario missing from this run" in regressions
    assert improvements == ["P1-01: risk_level now passes"]


def test_ratchet_passes_when_nothing_regresses():
    baseline = {"P1-01": {"action": True, "risk_level": False}}
    regressions, improvements = compare(baseline, [_scored("P1-01", action=True, risk_level=False)])
    assert regressions == [] and improvements == []
