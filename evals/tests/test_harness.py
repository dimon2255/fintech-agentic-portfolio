"""Harness plumbing against the real projects, with a stubbed LLM (no network).

These run the real project code in worker subprocesses. The LLM-tier tests
replace only the network call (ChatAnthropic.ainvoke) with canned replies, to
prove that silent fallbacks, API errors and token usage are detected and
recorded. They need the projects' dependencies installed but no API key.
The last tests load each project's src/llm.py by file path (the projects all
use the package name ``src``, so they cannot be imported together).
"""

import importlib.util
import json

import pytest

from evals import PRICING_PER_MTOK, PROJECTS, REPO_ROOT
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


def test_check_fails_closed_on_an_empty_baseline(tmp_path, capsys):
    from evals.__main__ import main

    baseline = tmp_path / "baseline.json"
    baseline.write_text("{}", encoding="utf-8")
    assert main(["--project", "p1", "--check", "--baseline", str(baseline)]) == 1
    assert "--write-baseline" in capsys.readouterr().err


def test_rules_tier_never_calls_an_llm():
    # The worker installs a guard that raises on any LLM call in the rules tier,
    # so a scored rules-tier run proves the agents stayed on their rules.
    response = run_worker("p3", _first("p3"), tier="rules")
    assert all(response["env_check"].values())
    assert response["results"][0]["status"] == "ok"


# Claude Haiku 5.5 (default since 2026-10-13): new prices, thinking blocks in replies.

THINKING_BLOCK = {"type": "thinking", "thinking": "Low velocity, home country, known device.", "signature": "sig"}


def test_haiku_5_5_price():
    from evals.worker import cost_usd

    assert PRICING_PER_MTOK["claude-haiku-5-5"] == (0.10, 0.50)
    assert PRICING_PER_MTOK["claude-sonnet-5-5"] == (2.00, 10.00)
    assert cost_usd("claude-haiku-5-5", 1_000_000, 1_000_000) == pytest.approx(0.60)
    assert cost_usd("claude-haiku-4-5-20251001", 1_000_000, 1_000_000) == pytest.approx(6.00)


def test_p1_reply_with_leading_thinking_block_is_parsed_not_a_fallback(tmp_path, monkeypatch):
    _llm_env(monkeypatch)
    scenarios = _first("p1")
    content = [THINKING_BLOCK, {"type": "text", "text": VALID_P1_REPLY}]
    response = run_worker("p1", scenarios, tier="llm", model="claude-haiku-5-5",
                          stub_llm=_stub(tmp_path, [{"content": content, "input_tokens": 800, "output_tokens": 300}]))
    result = response["results"][0]
    assert result["status"] == "ok" and result["fallbacks"] == {}
    assert result["output"]["recommended_action"] == "approve"
    assert result["llm"]["replies"][0]["head"].startswith('{"risk_level"')
    assert result["llm_cost_usd"] == pytest.approx(800 / 1e6 * 0.10 + 300 / 1e6 * 0.50)
    assert score_project("p1", scenarios, response)[0].status == "scored"


def _project_llm_module(key):
    path = REPO_ROOT / PROJECTS[key].directory / "src" / "llm.py"
    spec = importlib.util.spec_from_file_location(f"llm_{key}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("key", sorted(PROJECTS))
def test_message_text(key):
    from langchain_core.messages import AIMessage

    message_text = _project_llm_module(key).message_text
    assert message_text(AIMessage(content='{"a": 1}')) == '{"a": 1}'
    thinking_first = AIMessage(content=[THINKING_BLOCK, {"type": "text", "text": '{"a": 1}'}])
    assert message_text(thinking_first) == '{"a": 1}'
    assert message_text(AIMessage(content=["plain ", {"type": "text", "text": "text"}])) == "plain text"
    assert message_text(AIMessage(content="")) == ""
    assert message_text(AIMessage(content=[])) == ""
    assert message_text(AIMessage(content=[THINKING_BLOCK])) == ""


@pytest.mark.parametrize("key", sorted(PROJECTS))
def test_build_chat_model_sends_no_temperature_to_claude(key, monkeypatch):
    from langchain_core.messages import HumanMessage

    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-not-a-real-key")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-not-a-real-key")
    monkeypatch.delenv("DEFAULT_MODEL_EFFORT", raising=False)
    build_chat_model = _project_llm_module(key).build_chat_model
    payload = build_chat_model("claude-haiku-5-5")._get_request_payload([HumanMessage(content="hi")])
    assert "temperature" not in payload
    assert payload["max_tokens"] == 8192 and payload["output_config"] == {"effort": "low"}
    openai_model = build_chat_model("gpt-4o")
    assert type(openai_model).__name__ == "ChatOpenAI" and openai_model.temperature == 0


@pytest.mark.parametrize("key", sorted(PROJECTS))
def test_claude_effort_env_var_overrides_and_empty_sends_none(key, monkeypatch):
    """Models older than the 4.6 family reject effort, so an empty DEFAULT_MODEL_EFFORT must omit it."""
    from langchain_core.messages import HumanMessage

    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-not-a-real-key")
    build_chat_model = _project_llm_module(key).build_chat_model
    monkeypatch.setenv("DEFAULT_MODEL_EFFORT", "medium")
    payload = build_chat_model("claude-haiku-5-5")._get_request_payload([HumanMessage(content="hi")])
    assert payload["output_config"] == {"effort": "medium"}
    monkeypatch.setenv("DEFAULT_MODEL_EFFORT", "")
    payload = build_chat_model("claude-haiku-4-5-20251001")._get_request_payload([HumanMessage(content="hi")])
    assert "output_config" not in payload and "temperature" not in payload
