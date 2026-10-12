"""Combine repeated LLM-tier runs into one summary.

The LLM is not deterministic, so one run's accuracy is a sample. This reads
every ``claude-run-*.json`` written by ``--tier llm --file-stem claude-run-N``
and reports, per project: per-run headline accuracy, the pooled figure, the
range, how many scenarios were correct in a majority of runs, in every run or
in none, and each scenario's verdict per run with an "(unstable)" flag when the
runs disagree. Failed runs (errors, timeouts, evidence drift) and silent
fallbacks are listed as their own verdicts and excluded from accuracy.
"""

from __future__ import annotations

import json
from pathlib import Path

from . import PROJECTS
from .score import CHECK_LABELS, CHECKS, Ratio

RUN_PREFIX = "claude-run-"
SUMMARY_STEM = "scorecard-claude"

VERDICT_TEXT = {
    "correct": "correct",
    "wrong": "**wrong**",
    "error": "error",
    "harness_error": "harness error",
    "fallback": "fallback",
    "skipped": "skipped",
}


def verdict(project: str, scenario: dict) -> str:
    status = scenario["status"]
    if status != "scored":
        return status
    ok = scenario["checks"].get(PROJECTS[project].headline)
    return "correct" if ok else "wrong"


def load_runs(directory: Path) -> list[tuple[str, dict]]:
    paths = sorted(
        (p for p in directory.glob(f"{RUN_PREFIX}*.json")),
        key=lambda p: int(p.stem[len(RUN_PREFIX):]) if p.stem[len(RUN_PREFIX):].isdigit() else 10**6,
    )
    if not paths:
        raise SystemExit(f"no {RUN_PREFIX}*.json files in {directory}")
    runs = []
    for p in paths:
        doc = json.loads(p.read_text(encoding="utf-8"))
        if doc.get("tier") != "llm":
            raise SystemExit(f"{p.name} is not an LLM-tier run")
        runs.append((p.stem, doc))
    models = {doc.get("model") for _, doc in runs}
    if len(models) != 1:
        raise SystemExit(f"runs used different models; summarize like with like: {sorted(map(str, models))}")
    return runs


def summarize_runs(runs: list[tuple[str, dict]]) -> dict:
    n = len(runs)
    majority = n // 2 + 1
    projects = {}
    for key in PROJECTS:
        if not all(key in doc["projects"] for _, doc in runs):
            continue
        first = runs[0][1]["projects"][key]
        ids = [s["id"] for s in first]
        titles = {s["id"]: s["title"] for s in first}
        per_run = []
        pooled = Ratio()
        checks_pooled = {c: Ratio() for c in CHECKS[key]}
        counts = {"errors": 0, "harness_errors": 0, "fallbacks": 0, "skipped": 0}
        verdicts: dict[str, list[str]] = {sid: [] for sid in ids}
        fallback_nodes: dict[str, int] = {}
        for _, doc in runs:
            run_ratio = Ratio()
            by_id = {s["id"]: s for s in doc["projects"][key]}
            for sid in ids:
                s = by_id.get(sid)
                v = "missing" if s is None else verdict(key, s)
                verdicts[sid].append(v)
                if v in ("correct", "wrong"):
                    run_ratio.add(v == "correct")
                    pooled.add(v == "correct")
                    for c, ok in s["checks"].items():
                        if ok is not None:
                            checks_pooled[c].add(bool(ok))
                elif v == "error":
                    counts["errors"] += 1
                elif v == "harness_error":
                    counts["harness_errors"] += 1
                elif v == "fallback":
                    counts["fallbacks"] += 1
                elif v == "skipped":
                    counts["skipped"] += 1
                if s is not None:
                    for node, k in (s.get("fallbacks") or {}).items():
                        fallback_nodes[node] = fallback_nodes.get(node, 0) + k
            per_run.append(run_ratio)
        always = never = mixed = majority_correct = 0
        rows = []
        for sid in ids:
            vs = verdicts[sid]
            graded = [v for v in vs if v in ("correct", "wrong")]
            correct = sum(1 for v in graded if v == "correct")
            if graded and correct == len(graded):
                always += 1
            elif correct == 0:
                never += 1
            else:
                mixed += 1
            if correct >= majority:
                majority_correct += 1
            rows.append(
                {
                    "id": sid,
                    "title": titles[sid],
                    "verdicts": vs,
                    "correct": correct,
                    "graded": len(graded),
                    "stable": len(set(vs)) == 1,
                }
            )
        pcts = [r.pct() for r in per_run if r.pct() is not None]
        projects[key] = {
            "per_run": [r.to_json() for r in per_run],
            "pooled": pooled.to_json(),
            "range": [min(pcts), max(pcts)] if pcts else None,
            "majority_correct": majority_correct,
            "always": always,
            "never": never,
            "mixed": mixed,
            "scenarios": len(ids),
            "checks_pooled": {c: r.to_json() for c, r in checks_pooled.items()},
            "counts": counts,
            "fallback_nodes": fallback_nodes,
            "rows": rows,
        }
    totals = {"calls": 0, "api_errors": 0, "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0}
    for _, doc in runs:
        t = doc.get("llm_totals") or {}
        for k in totals:
            totals[k] += t.get(k, 0) or 0
    totals["cost_usd"] = round(totals["cost_usd"], 4)
    return {
        "runs": [name for name, _ in runs],
        "model": runs[0][1].get("model"),
        "majority_threshold": majority,
        "projects": projects,
        "totals": totals,
        "per_run_totals": {name: doc.get("llm_totals") for name, doc in runs},
    }


def _r(d: dict) -> str:
    return Ratio(d["hits"], d["total"]).display()


def write_summary(directory: Path) -> tuple[Path, Path]:
    runs = load_runs(directory)
    summary = summarize_runs(runs)
    names = summary["runs"]
    n = len(names)
    lines = [
        "# Claude Runs: Repeated-Run Summary",
        "",
        f"Generated by `python -m evals --summarize-runs` from {n} runs of `--tier llm`. Do not edit by hand. Model: "
        f"`{summary['model']}` in every agent node. Method: [ADR-001](../adr/001-golden-set-evaluation.md). Per-run "
        f"detail: {', '.join(f'[{x}]({x}.md)' for x in names)}.",
        "",
        "Each run replays the same scenarios with the same tool evidence; only the LLM replies differ. The headline "
        "verdict per scenario is the project's decision check (P1 and P2 recommended action, P3 compliance decision). "
        "Runs that failed (error) or in which a node silently fell back to the rules (fallback) are excluded from "
        "accuracy and counted separately.",
        "",
        "## Cost and reliability",
        "",
        "| Run | LLM calls | Failed calls | Input tokens | Output tokens | Estimated cost |",
        "|---|---|---|---|---|---|",
    ]
    for name in names:
        t = summary["per_run_totals"][name] or {}
        lines.append(
            f"| {name} | {t.get('calls', 0)} | {t.get('api_errors', 0)} | {t.get('input_tokens', 0):,} "
            f"| {t.get('output_tokens', 0):,} | ${t.get('cost_usd', 0):.2f} |"
        )
    t = summary["totals"]
    lines.append(
        f"| **All runs** | **{t['calls']}** | **{t['api_errors']}** | **{t['input_tokens']:,}** "
        f"| **{t['output_tokens']:,}** | **${t['cost_usd']:.2f}** |"
    )
    lines.append("")
    for key, p in summary["projects"].items():
        proj = PROJECTS[key]
        lines += [f"## {key.upper()}: {proj.name}", "", f"Headline: {proj.headline_label.lower()}.", ""]
        lines += ["| Run | Correct | Run failures | Silent fallbacks |", "|---|---|---|---|"]
        for name, r in zip(names, p["per_run"]):
            run_rows = [row["verdicts"][names.index(name)] for row in p["rows"]]
            lines.append(
                f"| {name} | {_r(r)} | {sum(v in ('error', 'harness_error') for v in run_rows)} "
                f"| {sum(v == 'fallback' for v in run_rows)} |"
            )
        lines.append(
            f"| **All runs pooled** | **{_r(p['pooled'])}** | {p['counts']['errors'] + p['counts']['harness_errors']} "
            f"| {p['counts']['fallbacks']} |"
        )
        rng = p["range"]
        lines += [
            "",
            "| Measure | Result |",
            "|---|---|",
            f"| Range across runs | {'n/a' if rng is None else f'{rng[0]:.0f}% to {rng[1]:.0f}%'} |",
            f"| Correct in a majority of runs ({summary['majority_threshold']} or more of {n}) | {p['majority_correct']} of {p['scenarios']} |",
            f"| Correct in every graded run | {p['always']} of {p['scenarios']} |",
            f"| Never correct | {p['never']} of {p['scenarios']} |",
            f"| Mixed verdicts | {p['mixed']} of {p['scenarios']} |",
        ]
        if p["fallback_nodes"]:
            nodes = ", ".join(f"{k} ({v})" for k, v in sorted(p["fallback_nodes"].items()))
            lines.append(f"| Silent fallbacks by node (all runs) | {nodes} |")
        lines += ["", "Every check, pooled over graded runs:", "", "| Check | Pooled result |", "|---|---|"]
        for c, r in p["checks_pooled"].items():
            lines.append(f"| {CHECK_LABELS[c]} | {_r(r)} |")
        lines += ["", f"| ID | Scenario | {' | '.join(names)} | Correct in |", f"|---|---|{'---|' * n}---|"]
        for row in p["rows"]:
            cells = " | ".join(VERDICT_TEXT.get(v, v) for v in row["verdicts"])
            flag = "" if row["stable"] else " (unstable)"
            lines.append(f"| {row['id']} | {row['title']} | {cells} | {row['correct']} of {row['graded']}{flag} |")
        lines.append("")
    md = directory / f"{SUMMARY_STEM}.md"
    md.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    js = directory / f"{SUMMARY_STEM}.json"
    js.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return md, js
