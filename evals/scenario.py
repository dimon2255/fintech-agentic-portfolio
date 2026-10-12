"""Load and validate golden scenarios.

One JSON file per scenario under ``evals/golden/<project>/``. Every scenario
has: id, title, category, narrative, inputs, fixtures, expected, rationale.
Expected values are strings (``"review|decline"`` accepts either), booleans,
or null (not graded for this scenario).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from . import PROJECTS, Project
from .evidence import validate_constraint

REQUIRED_FIELDS = (
    "id",
    "title",
    "category",
    "narrative",
    "inputs",
    "fixtures",
    "expected",
    "rationale",
)

RISK_LEVELS = {"low", "medium", "high", "critical"}
ACTIONS = {"approve", "review", "decline"}
DECISIONS = {"approved", "rejected", "escalated"}
TIERS = {"low", "medium", "high", "prohibited"}
SPECIALISTS = ("velocity", "identity", "behavioral")

# Allowed expected keys and, for categorical ones, the allowed values.
EXPECTED_SCHEMA: dict[str, dict[str, set[str] | type | None]] = {
    "p1": {"risk_level": RISK_LEVELS, "recommended_action": ACTIONS},
    "p2": {"risk_level": RISK_LEVELS, "recommended_action": ACTIONS, "specialists": dict},
    "p3": {
        "decision": DECISIONS,
        "risk_tier": TIERS,
        "was_escalated": bool,
        "sanctions_screening_required": bool,
        "edd_required": bool,
        "pep_monitoring_required": bool,
    },
}

REQUIRED_EXPECTED = {
    "p1": ("risk_level", "recommended_action"),
    "p2": ("risk_level", "recommended_action", "specialists"),
    "p3": ("decision", "sanctions_screening_required"),
}

INPUT_KEY = {"p1": "transaction", "p2": "transaction", "p3": "application"}


class ScenarioError(ValueError):
    pass


def alternatives(label: str) -> list[str]:
    return [part.strip().lower() for part in label.split("|") if part.strip()]


def _check_label(project: str, sid: str, key: str, value: Any, allowed: Any) -> None:
    if value is None:
        return
    if allowed is bool:
        if not isinstance(value, bool):
            raise ScenarioError(f"{sid}: expected.{key} must be true, false or null")
        return
    if allowed is dict:
        if not isinstance(value, dict):
            raise ScenarioError(f"{sid}: expected.{key} must be an object")
        for name, label in value.items():
            if name not in SPECIALISTS:
                raise ScenarioError(f"{sid}: unknown specialist {name!r}")
            _check_label(project, sid, f"{key}.{name}", label, RISK_LEVELS)
        return
    if not isinstance(value, str) or not alternatives(value):
        raise ScenarioError(f"{sid}: expected.{key} must be a non-empty string")
    bad = [a for a in alternatives(value) if a not in allowed]
    if bad:
        raise ScenarioError(f"{sid}: expected.{key} has unknown value(s) {bad}")


def validate(project: str, scenario: dict) -> None:
    sid = scenario.get("id", "<no id>")
    missing = [f for f in REQUIRED_FIELDS if f not in scenario]
    if missing:
        raise ScenarioError(f"{sid}: missing fields {missing}")
    for f in ("title", "category", "narrative", "rationale"):
        if not isinstance(scenario[f], str) or not scenario[f].strip():
            raise ScenarioError(f"{sid}: {f} must be a non-empty string")
    prefix = project.upper() + "-"
    if not sid.startswith(prefix):
        raise ScenarioError(f"{sid}: id must start with {prefix}")
    if INPUT_KEY[project] not in scenario["inputs"]:
        raise ScenarioError(f"{sid}: inputs.{INPUT_KEY[project]} is required")
    evidence = scenario["fixtures"].get("evidence")
    if not isinstance(evidence, dict):
        raise ScenarioError(f"{sid}: fixtures.evidence must be an object")
    for path, constraint in evidence.items():
        err = validate_constraint(constraint)
        if err:
            raise ScenarioError(f"{sid}: fixtures.evidence[{path!r}]: {err}")
    expected = scenario["expected"]
    schema = EXPECTED_SCHEMA[project]
    unknown = set(expected) - set(schema)
    if unknown:
        raise ScenarioError(f"{sid}: unknown expected keys {sorted(unknown)}")
    for key in REQUIRED_EXPECTED[project]:
        if expected.get(key) is None:
            raise ScenarioError(f"{sid}: expected.{key} is required")
    for key, value in expected.items():
        _check_label(project, sid, key, value, schema[key])


def load_project(project: Project | str, golden_dir: Path | None = None) -> list[dict]:
    if isinstance(project, str):
        project = PROJECTS[project]
    directory = golden_dir or project.golden_dir
    scenarios = []
    for path in sorted(directory.glob("*.json")):
        try:
            scenario = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ScenarioError(f"{path.name}: invalid JSON: {exc}") from exc
        validate(project.key, scenario)
        if not path.name.startswith(scenario["id"]):
            raise ScenarioError(f"{path.name}: file name must start with the id {scenario['id']}")
        scenario["_file"] = path.name
        scenarios.append(scenario)
    ids = [s["id"] for s in scenarios]
    if len(ids) != len(set(ids)):
        raise ScenarioError(f"{project.key}: duplicate scenario ids")
    return scenarios
