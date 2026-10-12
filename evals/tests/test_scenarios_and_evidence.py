"""Golden files load and validate; evidence constraints behave as documented."""

import pytest

from evals import PROJECTS
from evals.evidence import check, validate_constraint
from evals.scenario import ScenarioError, load_project, validate


@pytest.mark.parametrize("key", sorted(PROJECTS))
def test_golden_set_loads(key):
    scenarios = load_project(key)
    assert len(scenarios) >= 10
    for s in scenarios:
        assert s["fixtures"]["evidence"], f"{s['id']} states no evidence"
        assert len(s["rationale"]) > 40


def test_every_p3_scenario_requires_sanctions_screening():
    # Screening is a list check required for every applicant (ADR-001).
    assert all(s["expected"]["sanctions_screening_required"] is True for s in load_project("p3"))


def test_no_unfilled_search_placeholders():
    for key in PROJECTS:
        for s in load_project(key):
            assert "SEARCH" not in str(s["inputs"]), f"{s['id']} still has a SEARCH placeholder"


def test_validation_rejects_unknown_label_values():
    bad = {
        "id": "P1-99",
        "title": "t",
        "category": "c",
        "narrative": "n",
        "inputs": {"transaction": {}},
        "fixtures": {"evidence": {}},
        "expected": {"risk_level": "severe", "recommended_action": "approve"},
        "rationale": "r",
    }
    with pytest.raises(ScenarioError):
        validate("p1", bad)


def test_evidence_constraints():
    evidence = {"geo": {"is_vpn": True, "ip_country": "GB"}, "velocity": {"n": 3}, "documents": [{"ok": False}]}
    assert check(evidence, {"geo.is_vpn": True, "velocity.n": [2, 4], "geo.ip_country": {"in": ["GB", "DE"]}}) == []
    assert check(evidence, {"documents.0.ok": False}) == []
    violations = check(evidence, {"geo.is_vpn": False, "velocity.n": [5, 8], "geo.missing": True})
    assert len(violations) == 3
    # A boolean never satisfies a numeric range.
    assert check({"x": True}, {"x": [0, 1]}) != []


def test_constraint_validation():
    assert validate_constraint([0, 1]) is None
    assert validate_constraint([2, 1]) is not None
    assert validate_constraint({"in": ["a"]}) is None
    assert validate_constraint({"not": 1}) is not None
