"""Golden-set evaluation CLI.

    python -m evals                                 # rules tier: all projects, writes docs/evals/scorecard.*
    python -m evals --check                         # CI gate: rules tier vs baseline.json, exit 1 on regression
    python -m evals --only P3-04                    # one scenario, printed only
    python -m evals --write-baseline                # accept improvements into the ratchet
    python -m evals --product-root ../other-tree    # run this harness against another checkout's product code
    python -m evals --tier llm --file-stem claude-run-1    # one LLM-tier run (needs ANTHROPIC_API_KEY)
    python -m evals --summarize-runs                # combine claude-run-*.json into scorecard-claude.*
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from . import BASELINE_PATH, DEFAULT_LLM_MODEL, DOCS_EVALS_DIR, PRICING_PER_MTOK, PROJECTS, REPO_ROOT
from .report import write_scorecard
from .runner import run_projects
from .scenario import load_project
from .score import baseline_entry, compare, score_project, summarize

# Share of the LLM-tier budget each project may spend, by its expected number of
# LLM calls (P1 one per scenario, P2 four, P3 about ten).
BUDGET_SHARE = {"p1": 0.10, "p2": 0.25, "p3": 0.65}


def _product_label(product_root: Path) -> str:
    if product_root.resolve() == REPO_ROOT.resolve():
        return "this checkout"
    try:
        sha = subprocess.run(
            ["git", "-C", str(product_root), "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        ref = subprocess.run(
            ["git", "-C", str(product_root), "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        return f"{product_root.name} ({ref} at {sha})"
    except (subprocess.CalledProcessError, FileNotFoundError):
        return str(product_root)


def evaluate(args) -> tuple[dict, dict, dict, list[str]]:
    keys = [k.strip() for k in args.project.split(",")] if args.project else list(PROJECTS)
    selection = {}
    for key in keys:
        scenarios = load_project(key)
        if args.only:
            scenarios = [s for s in scenarios if s["id"] in args.only]
        if scenarios:
            selection[key] = scenarios
    if not selection:
        raise SystemExit("no scenarios selected")
    budgets = {}
    if args.tier == "llm":
        budgets = {k: args.budget_usd * BUDGET_SHARE[k] for k in selection}
    # Each project runs in its own subprocess; the projects run concurrently.
    responses = run_projects(
        selection,
        tier=args.tier,
        model=args.model if args.tier == "llm" else None,
        product_root=args.product_root,
        timeout_s=args.timeout,
        budgets=budgets,
        stub_llm=args.stub_llm,
    )
    scores = {key: score_project(key, selection[key], responses[key]) for key in selection}
    summaries = {key: summarize(key, scores[key]) for key in selection}
    versions = next(iter(responses.values())).get("versions", {})
    return scores, summaries, versions, list(selection)


def print_summary(scores, summaries, verbose: bool = False) -> None:
    for key, summary in summaries.items():
        p = PROJECTS[key]
        print(
            f"{key.upper()} {p.name}: {p.headline_label.lower()} {summary.headline.display()} | "
            f"all checks {summary.all_checks.display()} | not scored {summary.scenarios - summary.scored}"
        )
        for s in scores[key]:
            marks = " ".join(f"{k}={'ok' if v else 'MISS'}" for k, v in s.graded_checks().items())
            extra = f" [{s.status}: {s.error or s.fallbacks}]" if not s.scored else ""
            print(f"  {s.id} {marks}{extra}")
            if verbose:
                print("    output: " + json.dumps(s.output, default=str))
                if s.llm:
                    llm = {k: v for k, v in s.llm.items() if k != "replies"}
                    print(f"    llm: {json.dumps(llm)} cost=${s.llm_cost_usd or 0:.4f} fallbacks={s.fallbacks}")
                    for r in s.llm.get("replies", []):
                        print(f"      reply stop={r['stop_reason']} out={r['output_tokens']} head={r['head'][:90]!r}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m evals", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--tier", choices=["rules", "llm"], default="rules")
    parser.add_argument("--project", help="comma-separated subset of p1,p2,p3")
    parser.add_argument("--only", nargs="+", help="scenario ids to run; prints only, no files written")
    parser.add_argument("--check", action="store_true", help="compare with baseline.json and exit 1 on regression")
    parser.add_argument("--write-baseline", action="store_true")
    parser.add_argument("--no-write", action="store_true", help="do not write scorecard files")
    parser.add_argument("--product-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--out-dir", type=Path, default=DOCS_EVALS_DIR)
    parser.add_argument("--baseline", type=Path, default=BASELINE_PATH)
    parser.add_argument("--model", default=DEFAULT_LLM_MODEL)
    parser.add_argument("--file-stem", help="output stem; default scorecard (rules) or claude-run-1 (llm)")
    parser.add_argument("--budget-usd", type=float, default=2.0, help="LLM-tier spending cap for this run")
    parser.add_argument("--timeout", type=float, default=600, help="per-scenario timeout in seconds")
    parser.add_argument("--summarize-runs", action="store_true")
    parser.add_argument("--rerender-runs", action="store_true", help="rebuild claude-run-*.md/json from saved JSON, then summarize")
    parser.add_argument("--verbose", action="store_true", help="print each scenario's output and LLM usage")
    parser.add_argument("--stub-llm", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    if args.rerender_runs:
        from .report import rerender
        from .runs import RUN_PREFIX

        for path in sorted(args.out_dir.glob(f"{RUN_PREFIX}*.json")):
            md, _ = rerender(path)
            print(f"re-rendered {md.name} from {path.name}")
        args.summarize_runs = True

    if args.summarize_runs:
        from .runs import write_summary

        md, js = write_summary(args.out_dir)
        print(f"wrote {md} and {js}")
        return 0

    if (args.check or args.write_baseline) and (args.only or args.tier != "rules"):
        parser.error("--check and --write-baseline run the full rules tier; do not combine them with --only or --tier llm")
    if args.check and not args.baseline.exists():
        parser.error(f"--check needs a baseline file; {args.baseline} does not exist")
    if args.tier == "llm" and args.model not in PRICING_PER_MTOK and args.stub_llm is None:
        parser.error(f"no price recorded for {args.model} in evals.PRICING_PER_MTOK; the budget cap cannot work without one")

    scores, summaries, versions, keys = evaluate(args)
    print_summary(scores, summaries, verbose=args.verbose)

    if args.only:
        return 0

    if args.tier == "rules":
        flat = [s for key in keys for s in scores[key]]
        baseline = json.loads(args.baseline.read_text(encoding="utf-8")) if args.baseline.exists() else {}
        scoped = {sid: v for sid, v in baseline.items() if sid.split("-")[0].lower() in keys}
        regressions, improvements = compare(scoped, flat)
        unscored = [f"{s.id}: {s.status}: {s.error or ''}".rstrip() for s in flat if not s.scored]
        for line in improvements:
            print(f"IMPROVED   {line}")
        for line in regressions:
            print(f"REGRESSED  {line}")
        for line in unscored:
            print(f"NOT SCORED {line}")
        if args.write_baseline:
            if unscored:
                print("refusing to write a baseline from a run with unscored scenarios", file=sys.stderr)
                return 1
            if regressions:
                print("refusing to write a baseline that records regressions; fix them or edit baseline.json by hand "
                      "with a justification in the commit message", file=sys.stderr)
                return 1
            merged = dict(baseline)
            merged.update({s.id: baseline_entry(s) for s in flat})
            args.baseline.write_text(json.dumps(dict(sorted(merged.items())), indent=2) + "\n", encoding="utf-8")
            print(f"wrote {args.baseline}")
        if not args.no_write and not args.check:
            md, js = write_scorecard(
                args.out_dir, args.file_stem or "scorecard", scores, summaries, tier="rules", model=None,
                versions=versions, product_label=_product_label(args.product_root),
            )
            print(f"wrote {md} and {js}")
        if args.check and (regressions or unscored):
            print(
                f"gate failed: {len(regressions)} check(s) regressed against {args.baseline}, "
                f"{len(unscored)} scenario(s) not scored",
                file=sys.stderr,
            )
            return 1
        if args.check:
            print(f"gate passed: no regressions against {args.baseline.name}")
        return 0

    if args.stub_llm is not None and not args.no_write:
        print("stubbed LLM runs are for harness tests only; not writing run files", file=sys.stderr)
        return 0
    if not args.no_write:
        md, js = write_scorecard(
            args.out_dir, args.file_stem or "claude-run-1", scores, summaries, tier="llm", model=args.model,
            versions=versions, product_label=_product_label(args.product_root),
        )
        print(f"wrote {md} and {js}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
