"""Write the generated scorecards (Markdown and JSON)."""

from __future__ import annotations

import json
from pathlib import Path

from . import PROJECTS
from .score import CHECK_LABELS, CHECKS, ProjectSummary, ScenarioScore

STATUS_TEXT = {
    "error": "run failed",
    "harness_error": "harness error",
    "skipped": "skipped",
    "fallback": "silent fallback",
}


def _mark(ok: bool | None) -> str:
    return "n/a" if ok is None else ("pass" if ok else "**miss**")


def _label(value) -> str:
    if value is None:
        return "not graded"
    if isinstance(value, bool):
        return "yes" if value else "no"
    return str(value).replace("|", " or ")


def _yn(value) -> str:
    return "?" if value is None else ("yes" if value else "no")


def _row_p1(s: ScenarioScore) -> str:
    e, o = s.expected, s.output or {}
    got = f"{o.get('recommended_action', '?')} / {o.get('risk_level', '?')}" if s.output else STATUS_TEXT.get(s.status, s.status)
    return (
        f"| {s.id} | {s.title} | {_label(e.get('recommended_action'))} / {_label(e.get('risk_level'))} | {got} "
        f"| {_mark(s.checks.get('action'))} | {_mark(s.checks.get('risk_level'))} |"
    )


def _spec(o: dict, name: str) -> str:
    v = (o.get("specialists") or {}).get(name) or {}
    return f"{v.get('risk_level', '?')} ({v.get('risk_score', 0):.2f})" if v else "?"


def _row_p2(s: ScenarioScore) -> str:
    e, o = s.expected, s.output or {}
    if not s.output:
        return f"| {s.id} | {s.title} | {_label(e.get('recommended_action'))} / {_label(e.get('risk_level'))} | {STATUS_TEXT.get(s.status, s.status)} | | | | | |"
    specs = e.get("specialists") or {}
    cells = []
    for name in ("velocity", "identity", "behavioral"):
        cells.append(f"{_label(specs.get(name))} / {_spec(o, name)} {_mark(s.checks.get('specialist_' + name))}")
    return (
        f"| {s.id} | {s.title} | {_label(e.get('recommended_action'))} / {_label(e.get('risk_level'))} "
        f"| {o.get('recommended_action')} / {o.get('risk_level')} (agreement {o.get('agreement_score', 0):.2f}) "
        f"| {_mark(s.checks.get('action'))} | {_mark(s.checks.get('risk_level'))} | " + " | ".join(cells) + " |"
    )


def _row_p3(s: ScenarioScore) -> str:
    e, o = s.expected, s.output or {}
    expected = f"{_label(e.get('decision'))} / {_label(e.get('risk_tier'))} / escalated: {_label(e.get('was_escalated'))}"
    if not s.output:
        return f"| {s.id} | {s.title} | {expected} | {STATUS_TEXT.get(s.status, s.status)} | | | | | |"
    screening = (o.get("checklist") or {}).get("sanctions_screening", "?")
    got = f"{o.get('decision')} / {o.get('risk_tier')} / escalated: {_yn(o.get('was_escalated'))}"
    return (
        f"| {s.id} | {s.title} | {expected} | {got} | {_mark(s.checks.get('decision'))} "
        f"| {_mark(s.checks.get('risk_tier'))} | {_mark(s.checks.get('escalation'))} "
        f"| {screening} {_mark(s.checks.get('screening'))} | {_mark(s.checks.get('conditions'))} |"
    )


HEADERS = {
    "p1": ("| ID | Scenario | Expected action / level | Got | Action | Level |", "|---|---|---|---|---|---|"),
    "p2": (
        "| ID | Scenario | Expected action / level | Got | Action | Level | Velocity (expected / got) | Identity (expected / got) | Behavioral (expected / got) |",
        "|---|---|---|---|---|---|---|---|---|",
    ),
    "p3": (
        "| ID | Scenario | Expected decision / tier / escalated | Got | Decision | Tier | Escalation | Sanctions screening | Conditions |",
        "|---|---|---|---|---|---|---|---|---|",
    ),
}

ROWS = {"p1": _row_p1, "p2": _row_p2, "p3": _row_p3}


def _miss_detail(project: str, s: ScenarioScore) -> list[str]:
    lines = [f"#### {s.id}: {s.title}", ""]
    if not s.scored:
        lines.append(f"Not scored ({STATUS_TEXT.get(s.status, s.status)}): {s.error or ''}".rstrip())
        if s.fallbacks:
            lines.append(f"Fallback nodes: {', '.join(f'{k} ({v})' for k, v in sorted(s.fallbacks.items()))}.")
        lines.append("")
        return lines
    missed = [CHECK_LABELS[k] for k, v in s.checks.items() if v is False]
    lines.append(f"Missed: {', '.join(missed)}.")
    lines.append("")
    o = s.output or {}
    if project == "p1":
        lines.append(f"Got {o.get('recommended_action')} / {o.get('risk_level')} (confidence {o.get('confidence')}). Summary: {o.get('summary', '')}")
    elif project == "p2":
        specs = ", ".join(f"{k} {v['risk_level']} ({v['risk_score']:.2f})" for k, v in (o.get("specialists") or {}).items())
        lines.append(
            f"Got {o.get('recommended_action')} / {o.get('risk_level')}; specialists: {specs}; agreement "
            f"{o.get('agreement_score', 0):.2f}."
        )
    else:
        sanctions = o.get("sanctions")
        sanc = "not run" if sanctions is None else f"hits={sanctions['any_hits']}, highest={sanctions['highest_match_score']}"
        lines.append(
            f"Got {o.get('decision')} / {o.get('risk_tier')} / escalated {_yn(o.get('was_escalated'))}. Route: "
            f"{' > '.join(o.get('route') or [])}. Sanctions: {sanc}. Identity confirmed: {_yn(o.get('identity_confirmed'))}. "
            f"Composite risk: {o.get('risk_composite')}. Conditions: {o.get('conditions') or 'none'}. "
            f"Document issues: {o.get('document_issues') or 'none'}. Reasoning: {o.get('reasoning', '')}"
        )
    lines += ["", f"Label rationale: {s.rationale}", ""]
    return lines


def project_section(project: str, summary: ProjectSummary, scores: list[ScenarioScore]) -> list[str]:
    p = PROJECTS[project]
    lines = [f"## {project.upper()}: {p.name}", ""]
    lines.append("| Check | Result |")
    lines.append("|---|---|")
    for name in CHECKS[project]:
        lines.append(f"| {CHECK_LABELS[name]} | {summary.checks[name].display()} |")
    lines.append(f"| All graded checks pass | {summary.all_checks.display()} |")
    not_scored = summary.scenarios - summary.scored
    lines.append(
        f"| Not scored | {not_scored} (run failures {summary.errors}, harness errors {summary.harness_errors}, "
        f"silent fallbacks {summary.fallbacks}, skipped {summary.skipped}) |"
    )
    lines += ["", HEADERS[project][0], HEADERS[project][1]]
    lines += [ROWS[project](s) for s in scores]
    misses = [s for s in scores if not s.all_pass()]
    if misses:
        lines += ["", "### Misses and unscored runs", ""]
        for s in misses:
            lines += _miss_detail(project, s)
    lines.append("")
    return lines


def headline_table(summaries: dict[str, ProjectSummary]) -> list[str]:
    lines = [
        "| Project | Headline check | Result | All graded checks pass | Legitimate cases approved | Should-stop cases approved | Not scored |",
        "|---|---|---|---|---|---|---|",
    ]
    for key, summary in summaries.items():
        p = PROJECTS[key]
        lines.append(
            f"| {key.upper()} {p.name} | {p.headline_label} | {summary.headline.display()} "
            f"| {summary.all_checks.display()} | {summary.legit_approved.hits} of {summary.legit_approved.total} "
            f"| {summary.wrongly_approved.hits} of {summary.wrongly_approved.total} | {summary.scenarios - summary.scored} |"
        )
    lines += [
        "",
        "Legitimate cases are scenarios whose label requires approval (a false-positive check: higher is better). "
        "Should-stop cases are scenarios whose label does not accept approval (lower is better).",
    ]
    return lines


def llm_totals(scores: dict[str, list[ScenarioScore]]) -> dict:
    totals = {"calls": 0, "api_errors": 0, "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0, "models": {}, "stop_reasons": {}}
    for project_scores in scores.values():
        for s in project_scores:
            stats = s.llm or {}
            for k in ("calls", "api_errors", "input_tokens", "output_tokens"):
                totals[k] += int(stats.get(k, 0) or 0)
            totals["cost_usd"] += s.llm_cost_usd or 0.0
            for k, v in (stats.get("models") or {}).items():
                totals["models"][k] = totals["models"].get(k, 0) + v
            for k, v in (stats.get("stop_reasons") or {}).items():
                totals["stop_reasons"][k] = totals["stop_reasons"].get(k, 0) + v
    totals["cost_usd"] = round(totals["cost_usd"], 4)
    return totals


def write_scorecard(
    out_dir: Path,
    stem: str,
    scores: dict[str, list[ScenarioScore]],
    summaries: dict[str, ProjectSummary],
    *,
    tier: str,
    model: str | None,
    versions: dict,
    product_label: str,
) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    n = sum(len(v) for v in scores.values())
    if tier == "rules":
        title = "Golden-Set Scorecard: Rules Tier"
        tier_text = (
            "Tier: rules. Both API keys are empty, so every agent runs the project's deterministic rules "
            "(`mock_llm.py`); no LLM is called, and the harness fails the run if one is."
        )
        command = "python -m evals"
    else:
        title = f"Golden-Set Scorecard: Claude Run ({stem})"
        tier_text = (
            f"Tier: LLM. Every agent node calls `{model}` through the project's own ChatAnthropic code. A run in which "
            "any node silently fell back to the rules is excluded from accuracy and counted as a silent fallback."
        )
        command = f"python -m evals --tier llm --file-stem {stem}"
    lines = [
        f"# {title}",
        "",
        f"Generated by `{command}`. Do not edit by hand. Method: "
        "[ADR-001](../adr/001-golden-set-evaluation.md). Analysis: [golden-set-report.md](golden-set-report.md). "
        f"Scenarios: {n}. {tier_text} Product code: {product_label}.",
        "",
        "Each scenario runs the project's real entrypoint (P1 `classify_transaction`, P2 `analyze_transaction`, P3 "
        "`run_kyc_application`) with the project's own simulated tools. The harness only sets the scenario inputs, "
        "sets simulated latency to zero and checks that the tools returned the evidence the scenario states. Labels "
        "accept `a or b` where analysts would accept either; `not graded` means the label does not grade that check.",
        "",
        "## Headline",
        "",
    ]
    lines += headline_table(summaries)
    if tier == "llm":
        t = llm_totals(scores)
        lines += [
            "",
            f"LLM calls: {t['calls']}, failed calls (API or transport errors after client retries): {t['api_errors']}. "
            f"Tokens: {t['input_tokens']:,} input, {t['output_tokens']:,} output. Estimated cost: ${t['cost_usd']:.2f} "
            f"(at the list price for {model}). Models reported by the API: "
            f"{', '.join(f'{k} ({v})' for k, v in sorted(t['models'].items())) or 'none'}. Stop reasons: "
            f"{', '.join(f'{k} ({v})' for k, v in sorted(t['stop_reasons'].items())) or 'none'}.",
        ]
    lines.append("")
    for key in scores:
        lines += project_section(key, summaries[key], scores[key])
    md_path = out_dir / f"{stem}.md"
    md_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")

    doc = {
        "tier": tier,
        "model": model,
        "product": product_label,
        "versions": versions,
        "summary": {k: v.to_json() for k, v in summaries.items()},
        "projects": {k: [s.to_json() for s in v] for k, v in scores.items()},
    }
    if tier == "llm":
        doc["llm_totals"] = llm_totals(scores)
    json_path = out_dir / f"{stem}.json"
    json_path.write_text(json.dumps(doc, indent=2, default=str) + "\n", encoding="utf-8")
    return md_path, json_path


def rerender(json_path: Path) -> tuple[Path, Path]:
    """Rebuild a scorecard's Markdown and JSON from its saved JSON (no pipeline run).

    Used after a report-format change, so already-paid-for LLM runs are not
    repeated. Rationale text comes from the golden files.
    """
    from .scenario import load_project
    from .score import summarize

    doc = json.loads(json_path.read_text(encoding="utf-8"))
    scores: dict[str, list[ScenarioScore]] = {}
    for key, items in doc["projects"].items():
        rationale = {s["id"]: s["rationale"] for s in load_project(key)}
        scores[key] = [
            ScenarioScore(
                id=i["id"], title=i["title"], category=i["category"], status=i["status"], checks=i["checks"],
                expected=i["expected"], output=i["output"], error=i["error"], fallbacks=i["fallbacks"],
                llm=i["llm"], llm_cost_usd=i["llm_cost_usd"], rationale=rationale.get(i["id"], ""),
            )
            for i in items
        ]
    summaries = {key: summarize(key, s) for key, s in scores.items()}
    return write_scorecard(
        json_path.parent, json_path.stem, scores, summaries, tier=doc["tier"], model=doc.get("model"),
        versions=doc.get("versions", {}), product_label=doc.get("product", "this checkout"),
    )
