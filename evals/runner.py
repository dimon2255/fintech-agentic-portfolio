"""Spawn one worker subprocess per project and collect raw results."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import PROJECTS, REPO_ROOT


class WorkerError(RuntimeError):
    pass


def _strip_private(scenario: dict) -> dict:
    return {k: v for k, v in scenario.items() if not k.startswith("_")}


def worker_env(tier: str, model: str | None) -> dict:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(REPO_ROOT) + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    env["PYTHONIOENCODING"] = "utf-8"
    env["LANGSMITH_TRACING"] = "false"
    env["LANGCHAIN_TRACING_V2"] = "false"
    env["OPENAI_API_KEY"] = ""
    if tier == "rules":
        env["ANTHROPIC_API_KEY"] = ""
        env.pop("DEFAULT_MODEL", None)
    else:
        if not env.get("ANTHROPIC_API_KEY"):
            raise WorkerError("the LLM tier needs ANTHROPIC_API_KEY in the environment")
        env["DEFAULT_MODEL"] = model or ""
    return env


def run_worker(
    project_key: str,
    scenarios: list[dict],
    *,
    tier: str = "rules",
    model: str | None = None,
    product_root: Path = REPO_ROOT,
    budget_usd: float | None = None,
    timeout_s: float = 600,
    stub_llm: Path | None = None,
) -> dict:
    project = PROJECTS[project_key]
    project_dir = project.project_dir(product_root)
    if not (project_dir / "src").is_dir():
        raise WorkerError(f"{project_dir} has no src package")
    with tempfile.TemporaryDirectory(prefix="evals-") as tmp:
        request_path = Path(tmp) / "request.json"
        out_path = Path(tmp) / "response.json"
        request_path.write_text(
            json.dumps(
                {
                    "project": project_key,
                    "tier": tier,
                    "model": model,
                    "timeout_s": timeout_s,
                    "budget_usd": budget_usd,
                    "scenarios": [_strip_private(s) for s in scenarios],
                }
            ),
            encoding="utf-8",
        )
        cmd = [sys.executable, "-m", "evals.worker", "--request", str(request_path), "--out", str(out_path)]
        if stub_llm is not None:
            cmd += ["--stub-llm", str(stub_llm)]
        proc = subprocess.run(
            cmd,
            cwd=project_dir,
            env=worker_env(tier, model),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if proc.returncode != 0 or not out_path.exists():
            raise WorkerError(
                f"{project_key} worker failed (exit {proc.returncode}):\n{proc.stderr[-3000:]}"
            )
        response = json.loads(out_path.read_text(encoding="utf-8"))
    if response.get("fatal"):
        raise WorkerError(f"{project_key}: {response['fatal']}: {response.get('env_check')}")
    return response


def run_projects(
    selection: dict[str, list[dict]],
    *,
    budgets: dict[str, float] | None = None,
    **kwargs,
) -> dict[str, dict]:
    """Run each project's scenarios in its own worker, concurrently; returns project -> response."""
    budgets = budgets or {}
    with ThreadPoolExecutor(max_workers=len(selection)) as pool:
        futures = {
            key: pool.submit(run_worker, key, scenarios, budget_usd=budgets.get(key), **kwargs)
            for key, scenarios in selection.items()
        }
        return {key: fut.result() for key, fut in futures.items()}
