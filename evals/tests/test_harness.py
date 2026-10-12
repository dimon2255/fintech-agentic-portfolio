"""Harness plumbing against the real projects, with a stubbed LLM (no network).

These run the real project code in worker subprocesses. The LLM-tier tests
replace only the network call (ChatAnthropic.ainvoke) with canned replies, to
prove that silent fallbacks, API errors and token usage are detected and
recorded. They need the projects' dependencies installed but no API key.
"""

import json

import pytest

from evals.runner import run_worker
from evals.scenario import load_project
from evals.score import score_project

VALID_P1_REPLY = json.dumps(
    {
        "risk_level": "low",
        "confidence": 0.9,
        "reasoning_chain": [],
        "recommended_action": "approve",
        "summary": "Stubbed reply.",
    }
)


def _stub(tmp_path, replies):
    path = tmp_path / "stub.json"
    path.write_text(json.dumps({"replies": replies}), encoding="utf-8")
    return path


def _llm_env(monkeypatch):
    # A fake key: the stub intercepts the call before any request is sent.
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-not-a-real-key")


def _first(key):
    return load_project(key)[:1]


def test_p1_valid_reply_is_scored_and_tokens_counted(tmp_path, monkeypatch):
    _llm_env(monkeypatch)
    scenarios = _first("p1")
    response = run_worker("p1", scenarios, tier="llm", model="claude-haiku-4-5-20251001",
                          stub_llm=_stub(tmp_path, [{"content": VALID_P1_REPLY, "input_tokens": 800, "output_tokens": 300}]))
    assert all(response["env_check"].values())
    result = response["results"][0]
    assert result["status"] == "ok" and result["fallbacks"] == {}
    assert result["llm"]["calls"] == 1 and result["llm"]["input_tokens"] == 800
    assert result["llm_cost_usd"] == pytest.approx(800 / 1e6 * 1.0 + 300 / 1e6 * 5.0)
    assert score_project("p1", scenarios, response)[0].status == "scored"


def test_p1_unparseable_reply_is_a_detected_fallback(tmp_path, monkeypatch):
    _llm_env(monkeypatch)
    scenarios = _first("p1")
    response = run_worker("p1", scenarios, tier="llm", model="claude-haiku-4-5-20251001",
                          stub_llm=_stub(tmp_path, [{"content": "I think this looks fine."}]))
    result = response["results"][0]
    assert result["fallbacks"] == {"assess_risk": 1}
    assert result["output"]["recommended_action"] == "review"  # the product's fixed fallback
    assert score_project("p1", scenarios, response)[0].status == "fallback"


def test_p2_fallbacks_counted_per_node(tmp_path, monkeypatch):
    _llm_env(monkeypatch)
    scenarios = _first("p2")
    response = run_worker("p2", scenarios, tier="llm", model="claude-haiku-4-5-20251001",
                          stub_llm=_stub(tmp_path, [{"content": "not json"}]))
    result = response["results"][0]
    assert result["fallbacks"] == {"velocity_agent": 1, "identity_agent": 1, "behavioral_agent": 1, "adjudicator": 1}
    assert result["llm"]["calls"] == 4


def test_p3_api_error_is_recorded_not_scored(tmp_path, monkeypatch):
    _llm_env(monkeypatch)
    scenarios = _first("p3")
    response = run_worker("p3", scenarios, tier="llm", model="claude-haiku-4-5-20251001",
                          stub_llm=_stub(tmp_path, [{"raise": "overloaded"}]))
    result = response["results"][0]
    assert result["status"] == "error" and "stubbed API failure" in result["error"]
    assert result["llm"]["api_errors"] == 1
    assert score_project("p3", scenarios, response)[0].status == "error"


def test_write_baseline_refuses_to_record_a_regression(tmp_path):
    from evals.__main__ import main

    baseline = tmp_path / "baseline.json"
    # P1-10 fails both checks today; pretend the baseline recorded a pass.
    baseline.write_text(json.dumps({"P1-10": {"action": True, "risk_level": False}}), encoding="utf-8")
    before = baseline.read_text(encoding="utf-8")
    assert main(["--project", "p1", "--write-baseline", "--no-write", "--baseline", str(baseline)]) == 1
    assert baseline.read_text(encoding="utf-8") == before
    assert main(["--project", "p1", "--check", "--baseline", str(baseline)]) == 1


def test_rules_tier_never_calls_an_llm():
    # The worker installs a guard that raises on any LLM call in the rules tier,
    # so a scored rules-tier run proves the agents stayed on their rules.
    response = run_worker("p3", _first("p3"), tier="rules")
    assert all(response["env_check"].values())
    assert response["results"][0]["status"] == "ok"
