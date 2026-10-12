"""Run golden scenarios through one project's real entrypoint.

This module runs in a subprocess whose working directory is the project
directory, so ``import src`` resolves to that project (all three projects use
the package name ``src`` and cannot share a process). The parent
(``python -m evals``) writes a request JSON file and reads the response file.

What the worker changes, and nothing else:

* Environment, before the project is imported. Rules tier: both API keys set
  to the empty string, which selects the projects' deterministic rules
  (``_has_api_key()`` is false). LLM tier: ``ANTHROPIC_API_KEY`` comes from the
  parent environment, ``OPENAI_API_KEY`` is empty and ``DEFAULT_MODEL`` is set
  explicitly. python-dotenv does not override variables that already exist, so
  a project's local ``.env`` cannot change these; the worker verifies that
  after import and refuses to run if it does not hold.
* ``src.tools.SIMULATED_LATENCY_SECONDS`` is set to 0 (a sleep, not logic).
* Observation-only wrappers: LLM calls are counted for tokens, models and
  errors; the projects' rules-based fallback functions are counted when they
  run in the LLM tier, where they only run after an LLM reply failed to parse
  (a silent fallback). Both wrappers call through unchanged. In the rules tier
  any LLM call raises, which proves the tier never reaches the network.

Graph construction, agents, prompts, thresholds, routing and tools all run
unmodified. Each scenario's evidence constraints are checked by calling the
project's own tool functions on the scenario inputs before the pipeline runs.
"""

from __future__ import annotations

import argparse
import asyncio
import importlib
import json
import os
import sys
import time
import traceback
from collections import Counter
from importlib import metadata
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.append(str(REPO_ROOT))

from evals import PRICING_PER_MTOK  # noqa: E402
from evals.evidence import check as check_evidence  # noqa: E402

P1_FALLBACK_MARKER = "Agent produced unstructured response"

# (module, function, node) for every rules-based fallback an LLM-mode node
# calls from its ``except`` block. P1 has no fallback function; its fallback
# is a fixed medium/review assessment whose summary starts with the marker.
FALLBACK_TARGETS = {
    "p1": [],
    "p2": [
        ("src.agents.velocity_agent", "mock_velocity_assess", "velocity_agent"),
        ("src.agents.identity_agent", "mock_identity_assess", "identity_agent"),
        ("src.agents.behavioral_agent", "mock_behavioral_assess", "behavioral_agent"),
        ("src.adjudicator", "mock_adjudicate", "adjudicator"),
    ],
    "p3": [
        ("src.supervisor", "mock_supervisor_route", "supervisor"),
        ("src.agents.document_intake", "mock_document_intake", "document_intake"),
        ("src.agents.identity_verification", "mock_identity_verify", "identity_verification"),
        ("src.agents.sanctions_screening", "mock_sanctions_screen", "sanctions_screening"),
        ("src.agents.risk_assessment", "mock_risk_assess", "risk_assessment"),
    ],
}

# Module whose _has_api_key() decides rules vs LLM mode, per project.
MODE_PROBE = {"p1": "src.agent", "p2": "src.adjudicator", "p3": "src.supervisor"}

MODULES = {
    "p1": ["src.models", "src.tools", "src.agent"],
    "p2": ["src.models", "src.tools", "src.graph", "src.adjudicator"],
    "p3": ["src.models", "src.tools", "src.graph", "src.supervisor"],
}

CURRENT: dict = {"rec": None}


def _new_llm_stats() -> dict:
    return {
        "calls": 0,
        "api_errors": 0,
        "error_types": [],
        "input_tokens": 0,
        "output_tokens": 0,
        "models": Counter(),
        "stop_reasons": Counter(),
        "replies": [],
    }


class StubLLM:
    """Canned replies for harness unit tests (no network). Never used for results."""

    def __init__(self, path: str):
        spec = json.loads(Path(path).read_text(encoding="utf-8"))
        self.replies = spec["replies"]
        self.index = 0

    def next(self, model_name: str):
        from langchain_core.messages import AIMessage

        reply = self.replies[self.index % len(self.replies)]
        self.index += 1
        if "raise" in reply:
            raise RuntimeError(f"stubbed API failure: {reply['raise']}")
        return AIMessage(
            content=reply["content"],
            usage_metadata={
                "input_tokens": reply.get("input_tokens", 100),
                "output_tokens": reply.get("output_tokens", 50),
                "total_tokens": reply.get("input_tokens", 100) + reply.get("output_tokens", 50),
            },
            response_metadata={"model": model_name, "stop_reason": reply.get("stop_reason", "end_turn")},
        )


def install_llm_guards(tier: str, stub: StubLLM | None) -> None:
    from langchain_anthropic import ChatAnthropic
    from langchain_openai import ChatOpenAI

    async def openai_guard(self, *args, **kwargs):
        raise RuntimeError("harness guard: an OpenAI model was invoked; the eval runs Claude only")

    ChatOpenAI.ainvoke = openai_guard

    if tier == "rules":

        async def rules_guard(self, *args, **kwargs):
            raise RuntimeError("harness guard: an LLM was invoked during the rules tier")

        ChatAnthropic.ainvoke = rules_guard
        return

    original = ChatAnthropic.ainvoke

    async def recorded(self, input, config=None, **kwargs):  # noqa: A002 (LangChain's name)
        stats = CURRENT["rec"]["llm"]
        stats["calls"] += 1
        try:
            if stub is not None:
                response = stub.next(self.model)
            else:
                response = await original(self, input, config, **kwargs)
        except Exception as exc:
            stats["api_errors"] += 1
            stats["error_types"].append(type(exc).__name__)
            raise
        usage = getattr(response, "usage_metadata", None) or {}
        stats["input_tokens"] += int(usage.get("input_tokens", 0) or 0)
        stats["output_tokens"] += int(usage.get("output_tokens", 0) or 0)
        meta = getattr(response, "response_metadata", None) or {}
        stats["models"][str(meta.get("model") or meta.get("model_name") or "unknown")] += 1
        stats["stop_reasons"][str(meta.get("stop_reason") or "unknown")] += 1
        content = response.content if isinstance(response.content, str) else json.dumps(response.content)
        stats["replies"].append(
            {
                "stop_reason": meta.get("stop_reason"),
                "output_tokens": usage.get("output_tokens"),
                "head": content[:160],
            }
        )
        return response

    ChatAnthropic.ainvoke = recorded


def install_fallback_counters(project: str) -> None:
    for module_name, func_name, node in FALLBACK_TARGETS[project]:
        module = importlib.import_module(module_name)
        original = getattr(module, func_name)

        def make_wrapper(fn, node_name):
            def wrapper(*args, **kwargs):
                rec = CURRENT["rec"]
                if rec is not None:
                    rec["fallbacks"][node_name] = rec["fallbacks"].get(node_name, 0) + 1
                return fn(*args, **kwargs)

            return wrapper

        setattr(module, func_name, make_wrapper(original, node))


# ----------------------------------------------------------------------------
# Per-project evidence and output extraction
# ----------------------------------------------------------------------------


async def gather_evidence(project: str, mods: dict, scenario: dict) -> dict:
    tools = mods["src.tools"]
    models = mods["src.models"]
    if project in ("p1", "p2"):
        txn = models.Transaction.model_validate(scenario["inputs"]["transaction"])
        results = await tools.run_all_checks(txn)
        return {name: value.model_dump(mode="json") for name, value in results.items()}
    app = models.KYCApplication.model_validate(scenario["inputs"]["application"])
    docs = await tools.run_document_intake_tools(app.documents_submitted)
    documents = []
    for ext, cls, val in zip(docs["extractions"], docs["classifications"], docs["validations"]):
        documents.append(
            {
                "extraction_confidence": ext.extraction_confidence,
                "is_correct_type": cls.is_correct_type,
                **val.model_dump(mode="json"),
            }
        )
    ident = await tools.run_identity_tools(app, docs["extractions"][0])
    return {
        "documents": documents,
        "identity": {
            "name_match_score": ident["name_match"].match_score,
            "address_match_status": ident["address_verify"].match_status,
            "dob_match": ident["dob_crosscheck"].match,
            "is_pep": ident["pep_check"].is_pep,
            "pep_tier": ident["pep_check"].pep_tier,
        },
    }


def _lower(value) -> str:
    if hasattr(value, "value"):
        value = value.value
    return str(value).strip().lower()


async def run_pipeline(project: str, mods: dict, scenario: dict) -> dict:
    models = mods["src.models"]
    if project == "p1":
        txn = models.Transaction.model_validate(scenario["inputs"]["transaction"])
        assessment = await mods["src.agent"].classify_transaction(txn)
        return {
            "risk_level": _lower(assessment.risk_level),
            "recommended_action": _lower(assessment.recommended_action),
            "confidence": assessment.confidence,
            "summary": assessment.summary[:400],
            "p1_fallback": assessment.summary.startswith(P1_FALLBACK_MARKER),
        }
    if project == "p2":
        txn = models.Transaction.model_validate(scenario["inputs"]["transaction"])
        result = await mods["src.graph"].analyze_transaction(txn)
        final = result["final_assessment"]
        return {
            "risk_level": _lower(final.risk_level),
            "recommended_action": _lower(final.recommended_action),
            "confidence": final.confidence,
            "agreement_score": final.debate_analysis.agreement_score,
            "specialists": {
                v.agent_name: {
                    "risk_level": _lower(v.risk_level),
                    "risk_score": v.risk_score,
                    "recommended_action": _lower(v.recommended_action),
                }
                for v in final.specialist_verdicts
            },
            "summary": final.summary[:400],
        }
    app = models.KYCApplication.model_validate(scenario["inputs"]["application"])
    result = await mods["src.graph"].run_kyc_application(app)
    decision = result["compliance_decision"]
    sanctions = decision.sanctions_screening_result
    identity = decision.identity_verification_result
    documents = decision.document_intake_result
    risk = decision.risk_assessment_result
    checklist = decision.checklist
    return {
        "decision": _lower(decision.decision),
        "risk_tier": _lower(decision.risk_tier),
        "was_escalated": bool(decision.was_escalated),
        "conditions": list(decision.conditions),
        "checklist": {
            step: getattr(checklist, step)
            for step in (
                "document_intake",
                "identity_verification",
                "sanctions_screening",
                "risk_assessment",
            )
        },
        "route": [d.next_step for d in decision.supervisor_decisions],
        "sanctions": None
        if sanctions is None
        else {"any_hits": sanctions.any_hits, "highest_match_score": sanctions.highest_match_score},
        "identity_confirmed": None if identity is None else identity.identity_confirmed,
        "is_pep": None if identity is None else identity.pep_check.is_pep,
        "document_quality": None if documents is None else documents.overall_document_quality,
        "document_issues": [] if documents is None else list(documents.issues_found),
        "risk_composite": None if risk is None else risk.overall_risk.composite_score,
        "reasoning": decision.reasoning[:400],
    }


# ----------------------------------------------------------------------------
# Main loop
# ----------------------------------------------------------------------------


def cost_usd(model: str, input_tokens: int, output_tokens: int) -> float | None:
    price = PRICING_PER_MTOK.get(model)
    if price is None:
        return None
    return input_tokens / 1e6 * price[0] + output_tokens / 1e6 * price[1]


def _versions() -> dict:
    out = {"python": sys.version.split()[0]}
    for pkg in ("langgraph", "langchain-core", "langchain-anthropic", "anthropic", "pydantic"):
        try:
            out[pkg] = metadata.version(pkg)
        except metadata.PackageNotFoundError:
            out[pkg] = None
    return out


async def main_async(request: dict, stub: StubLLM | None) -> dict:
    project = request["project"]
    tier = request["tier"]
    model = request.get("model")
    timeout_s = float(request.get("timeout_s", 600))
    budget = request.get("budget_usd")

    # Environment is set by the parent; re-assert before importing the project.
    if tier == "rules":
        os.environ["ANTHROPIC_API_KEY"] = ""
        os.environ["OPENAI_API_KEY"] = ""
    else:
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise SystemExit("LLM tier needs ANTHROPIC_API_KEY in the environment")
        os.environ["OPENAI_API_KEY"] = ""
        os.environ["DEFAULT_MODEL"] = model
    os.environ["LANGSMITH_TRACING"] = "false"
    os.environ["LANGCHAIN_TRACING_V2"] = "false"
    key_before = os.environ.get("ANTHROPIC_API_KEY")

    mods = {name: importlib.import_module(name) for name in MODULES[project]}

    # The project modules ran load_dotenv at import. Prove the process values won.
    has_key = importlib.import_module(MODE_PROBE[project])._has_api_key()
    env_check = {
        "anthropic_key_unchanged_by_dotenv": os.environ.get("ANTHROPIC_API_KEY") == key_before,
        "openai_key_empty": os.environ.get("OPENAI_API_KEY") == "",
        "mode_matches_tier": has_key == (tier == "llm"),
    }
    if tier == "llm":
        env_check["default_model"] = os.environ.get("DEFAULT_MODEL") == model
    if not all(env_check.values()):
        return {"project": project, "tier": tier, "env_check": env_check, "fatal": "environment check failed", "results": []}

    mods["src.tools"].SIMULATED_LATENCY_SECONDS = 0
    install_llm_guards(tier, stub)
    if tier == "llm":
        install_fallback_counters(project)

    results = []
    spent = 0.0
    for scenario in request["scenarios"]:
        rec = {"id": scenario["id"], "status": "ok", "fallbacks": {}, "llm": _new_llm_stats()}
        CURRENT["rec"] = rec
        if budget is not None and spent >= budget:
            rec["status"] = "skipped"
            rec["error"] = f"budget of ${budget:.2f} reached"
            results.append(rec)
            continue
        started = time.perf_counter()
        try:
            evidence = await gather_evidence(project, mods, scenario)
        except Exception as exc:  # harness error: fixture could not be evaluated
            rec["status"] = "harness_error"
            rec["error"] = f"evidence collection failed: {type(exc).__name__}: {exc}"
            results.append(rec)
            continue
        rec["evidence"] = evidence
        violations = check_evidence(evidence, scenario["fixtures"].get("evidence", {}))
        if violations:
            rec["status"] = "harness_error"
            rec["error"] = "evidence drift: " + "; ".join(violations)
            results.append(rec)
            continue
        try:
            rec["output"] = await asyncio.wait_for(run_pipeline(project, mods, scenario), timeout_s)
        except asyncio.TimeoutError:
            rec["status"] = "error"
            rec["error"] = f"timeout after {timeout_s:.0f}s"
        except Exception as exc:
            rec["status"] = "error"
            rec["error"] = f"{type(exc).__name__}: {str(exc)[:300]}"
            rec["traceback_tail"] = traceback.format_exc().splitlines()[-6:]
        rec["elapsed_ms"] = round((time.perf_counter() - started) * 1000, 1)
        if tier == "llm":
            if project == "p1" and rec.get("output", {}).get("p1_fallback"):
                rec["fallbacks"]["assess_risk"] = 1
            stats = rec["llm"]
            rec["llm_cost_usd"] = cost_usd(model, stats["input_tokens"], stats["output_tokens"])
            spent += rec["llm_cost_usd"] or 0.0
        rec["llm"]["models"] = dict(rec["llm"]["models"])
        rec["llm"]["stop_reasons"] = dict(rec["llm"]["stop_reasons"])
        results.append(rec)
    CURRENT["rec"] = None
    return {
        "project": project,
        "tier": tier,
        "model": model if tier == "llm" else None,
        "stub": stub is not None,
        "env_check": env_check,
        "versions": _versions(),
        "results": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--stub-llm", help="canned LLM replies for harness unit tests only")
    args = parser.parse_args()
    request = json.loads(Path(args.request).read_text(encoding="utf-8"))
    stub = StubLLM(args.stub_llm) if args.stub_llm else None
    response = asyncio.run(main_async(request, stub))
    Path(args.out).write_text(json.dumps(response, indent=2, default=str), encoding="utf-8")


if __name__ == "__main__":
    main()
