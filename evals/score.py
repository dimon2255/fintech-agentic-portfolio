"""Grade worker output against golden labels. Pure functions, no project imports.

Rules:

* A label ``"a|b"`` accepts either value (case-insensitive). A null label is
  not graded for that scenario.
* A scenario whose run crashed, hit an API error, timed out, or whose fixture
  evidence drifted is never scored: it is counted separately and excluded from
  every accuracy figure. In the ratchet gate it counts as a regression of each
  check that the baseline records as passing.
* In the LLM tier, a scenario run in which any node silently fell back to the
  rules (or, in P1, to the fixed medium/review assessment) is a measurement of
  the fallback, not of the LLM. It is counted separately and excluded from
  accuracy like an error.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from . import PROJECTS
from .scenario import SPECIALISTS, alternatives

EDD_CONDITION = "Enhanced Due Diligence required"
PEP_CONDITION_PREFIX = "PEP monitoring"

CHECKS = {
    "p1": ["action", "risk_level"],
    "p2": ["action", "risk_level"] + [f"specialist_{s}" for s in SPECIALISTS],
    "p3": ["decision", "risk_tier", "escalation", "screening", "conditions"],
}

CHECK_LABELS = {
    "action": "Recommended action",
    "risk_level": "Risk level",
    "specialist_velocity": "Velocity specialist level",
    "specialist_identity": "Identity specialist level",
    "specialist_behavioral": "Behavioral specialist level",
    "decision": "Decision",
    "risk_tier": "Risk tier",
    "escalation": "Escalated to a human when required",
    "screening": "Sanctions screening ran when required",
    "conditions": "EDD and PEP conditions on approvals",
}


@dataclass
class Ratio:
    hits: int = 0
    total: int = 0

    def add(self, ok: bool) -> None:
        self.total += 1
        self.hits += int(ok)

    def pct(self) -> float | None:
        return None if self.total == 0 else 100.0 * self.hits / self.total

    def display(self) -> str:
        if self.total == 0:
            return "n/a (0 graded)"
        return f"{self.pct():.0f}% ({self.hits} of {self.total})"

    def to_json(self) -> dict:
        return {"hits": self.hits, "total": self.total, "pct": self.pct()}


def label_matches(label: Any, actual: Any) -> bool | None:
    """True/False when graded, None when the label is null."""
    if label is None:
        return None
    if isinstance(label, bool):
        return actual is label
    if actual is None:
        return False
    return str(actual).strip().lower() in alternatives(label)


def grade_p1(expected: dict, out: dict) -> dict[str, bool | None]:
    return {
        "action": label_matches(expected.get("recommended_action"), out.get("recommended_action")),
        "risk_level": label_matches(expected.get("risk_level"), out.get("risk_level")),
    }


def grade_p2(expected: dict, out: dict) -> dict[str, bool | None]:
    checks = {
        "action": label_matches(expected.get("recommended_action"), out.get("recommended_action")),
        "risk_level": label_matches(expected.get("risk_level"), out.get("risk_level")),
    }
    specialists = out.get("specialists") or {}
    for name in SPECIALISTS:
        label = (expected.get("specialists") or {}).get(name)
        actual = (specialists.get(name) or {}).get("risk_level")
        checks[f"specialist_{name}"] = label_matches(label, actual)
    return checks


def grade_p3(expected: dict, out: dict) -> dict[str, bool | None]:
    checks = {
        "decision": label_matches(expected.get("decision"), out.get("decision")),
        "risk_tier": label_matches(expected.get("risk_tier"), out.get("risk_tier")),
        "escalation": label_matches(expected.get("was_escalated"), out.get("was_escalated")),
    }
    screening_ran = (out.get("checklist") or {}).get("sanctions_screening") == "completed"
    required = expected.get("sanctions_screening_required")
    checks["screening"] = screening_ran if required else None

    # Conditions attach to approvals; graded only when the pipeline approved.
    edd = expected.get("edd_required")
    pep = expected.get("pep_monitoring_required")
    if (edd is None and not pep) or out.get("decision") != "approved":
        checks["conditions"] = None
    else:
        conditions = out.get("conditions") or []
        ok = True
        if edd is not None:
            ok = ok and ((EDD_CONDITION in conditions) == edd)
        if pep:
            ok = ok and any(c.startswith(PEP_CONDITION_PREFIX) for c in conditions)
        checks["conditions"] = ok
    return checks


GRADERS = {"p1": grade_p1, "p2": grade_p2, "p3": grade_p3}


@dataclass
class ScenarioScore:
    id: str
    title: str
    category: str
    status: str  # scored | error | harness_error | skipped | fallback
    checks: dict[str, bool | None] = field(default_factory=dict)
    expected: dict = field(default_factory=dict)
    output: dict | None = None
    error: str | None = None
    fallbacks: dict = field(default_factory=dict)
    llm: dict | None = None
    llm_cost_usd: float | None = None
    rationale: str = ""

    @property
    def scored(self) -> bool:
        return self.status == "scored"

    def graded_checks(self) -> dict[str, bool]:
        return {k: v for k, v in self.checks.items() if v is not None}

    def all_pass(self) -> bool:
        return self.scored and all(self.graded_checks().values())

    def to_json(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "category": self.category,
            "status": self.status,
            "checks": self.checks,
            "expected": self.expected,
            "output": self.output,
            "error": self.error,
            "fallbacks": self.fallbacks,
            "llm": self.llm,
            "llm_cost_usd": self.llm_cost_usd,
        }


def score_scenario(project: str, scenario: dict, result: dict, tier: str = "rules") -> ScenarioScore:
    score = ScenarioScore(
        id=scenario["id"],
        title=scenario["title"],
        category=scenario["category"],
        status="scored",
        expected=scenario["expected"],
        output=result.get("output"),
        error=result.get("error"),
        fallbacks=result.get("fallbacks") or {},
        llm=result.get("llm") if tier == "llm" else None,
        llm_cost_usd=result.get("llm_cost_usd"),
        rationale=scenario.get("rationale", ""),
    )
    status = result.get("status", "error")
    if status != "ok" or score.output is None:
        score.status = status if status != "ok" else "error"
        return score
    score.checks = GRADERS[project](scenario["expected"], score.output)
    if tier == "llm" and score.fallbacks:
        score.status = "fallback"
    return score


def score_project(project: str, scenarios: list[dict], response: dict) -> list[ScenarioScore]:
    by_id = {r["id"]: r for r in response["results"]}
    tier = response.get("tier", "rules")
    return [
        score_scenario(project, s, by_id.get(s["id"], {"status": "error", "error": "no result"}), tier)
        for s in scenarios
    ]


APPROVE = {"p1": ("recommended_action", "approve"), "p2": ("recommended_action", "approve"), "p3": ("decision", "approved")}


def approval_outcomes(project: str, expected: dict, output: dict | None) -> tuple[bool | None, bool | None]:
    """(legitimate case approved?, should-stop case approved?) for one scored run.

    A legitimate case is one whose label requires approval and nothing else; a
    should-stop case is one whose label does not accept approval. Each element
    is None when the scenario is not of that kind.
    """
    key, value = APPROVE[project]
    labels = alternatives(expected.get(key) or "")
    approved = (output or {}).get(key) == value
    legit = approved if labels == [value] else None
    stop = approved if value not in labels else None
    return legit, stop


@dataclass
class ProjectSummary:
    project: str
    scenarios: int
    scored: int
    errors: int
    harness_errors: int
    fallbacks: int
    skipped: int
    checks: dict[str, Ratio]
    all_checks: Ratio
    legit_approved: Ratio = field(default_factory=Ratio)
    wrongly_approved: Ratio = field(default_factory=Ratio)

    @property
    def headline(self) -> Ratio:
        return self.checks[PROJECTS[self.project].headline]

    def to_json(self) -> dict:
        return {
            "project": self.project,
            "scenarios": self.scenarios,
            "scored": self.scored,
            "errors": self.errors,
            "harness_errors": self.harness_errors,
            "fallbacks": self.fallbacks,
            "skipped": self.skipped,
            "headline_check": PROJECTS[self.project].headline,
            "headline": self.headline.to_json(),
            "checks": {k: v.to_json() for k, v in self.checks.items()},
            "all_checks": self.all_checks.to_json(),
            "legit_approved": self.legit_approved.to_json(),
            "wrongly_approved": self.wrongly_approved.to_json(),
        }


def summarize(project: str, scores: list[ScenarioScore]) -> ProjectSummary:
    checks = {name: Ratio() for name in CHECKS[project]}
    all_checks = Ratio()
    legit, wrong = Ratio(), Ratio()
    for s in scores:
        if not s.scored:
            continue
        for name, ok in s.graded_checks().items():
            checks[name].add(ok)
        all_checks.add(s.all_pass())
        is_legit, is_stop = approval_outcomes(project, s.expected, s.output)
        if is_legit is not None:
            legit.add(is_legit)
        if is_stop is not None:
            wrong.add(is_stop)
    count = lambda status: sum(1 for s in scores if s.status == status)  # noqa: E731
    return ProjectSummary(
        project=project,
        scenarios=len(scores),
        scored=count("scored"),
        errors=count("error"),
        harness_errors=count("harness_error"),
        fallbacks=count("fallback"),
        skipped=count("skipped"),
        checks=checks,
        all_checks=all_checks,
        legit_approved=legit,
        wrongly_approved=wrong,
    )


# ----------------------------------------------------------------------------
# Ratchet baseline
# ----------------------------------------------------------------------------


def baseline_entry(score: ScenarioScore) -> dict[str, bool]:
    return {k: bool(v) for k, v in sorted(score.graded_checks().items())}


def compare(baseline: dict, scores: list[ScenarioScore]) -> tuple[list[str], list[str]]:
    """Return (regressions, improvements) against the recorded baseline.

    A check recorded as passing that now fails, is no longer graded, or whose
    scenario did not produce a scorable run is a regression. A check that now
    passes but is recorded as failing (or is new) is an improvement.
    """
    regressions, improvements = [], []
    seen = set()
    for s in scores:
        seen.add(s.id)
        recorded = baseline.get(s.id, {})
        if not s.scored:
            for check, passed in sorted(recorded.items()):
                if passed:
                    regressions.append(f"{s.id}: {check} regressed (pass -> {s.status}: {s.error or ''})".rstrip())
            continue
        graded = s.graded_checks()
        for check, passed in sorted(recorded.items()):
            if passed and not graded.get(check, False):
                now = "not graded" if check not in graded else "fail"
                regressions.append(f"{s.id}: {check} regressed (pass -> {now})")
        for check, ok in sorted(graded.items()):
            if ok and not recorded.get(check, False):
                improvements.append(f"{s.id}: {check} now passes")
    for sid in sorted(set(baseline) - seen):
        if any(baseline[sid].values()):
            regressions.append(f"{sid}: scenario missing from this run")
    return regressions, improvements
