"""Evidence constraints: what each scenario says its data sources return.

The projects' data sources are simulated and deterministic: a transaction's
customer, IP, device and email IDs (P1, P2) or an application's document
numbers and names (P3) fully determine what the simulated tools return. A
scenario states the evidence its narrative relies on as constraints over the
tools' raw observations, and the harness checks those constraints on every run
by calling the project's own tool functions. If a code change makes a tool
return different raw evidence, the scenario is reported as a harness error
("evidence drift") instead of being scored against a label that no longer
describes it.

Constraints cover raw observations only (counts, flags, document checks),
never derived risk scores: scores are product logic and are what the
evaluation measures.

Constraint syntax, keyed by a dotted path into the evidence dict (list indexes
are path segments, e.g. ``documents.0.tampering_detected``):

    true / false / "text"     exact match
    [low, high]               numeric range, inclusive
    {"in": [a, b, ...]}       membership
"""

from __future__ import annotations

from typing import Any

_MISSING = object()


def resolve(evidence: Any, path: str) -> Any:
    node = evidence
    for part in path.split("."):
        if isinstance(node, list):
            try:
                node = node[int(part)]
            except (ValueError, IndexError):
                return _MISSING
        elif isinstance(node, dict):
            if part not in node:
                return _MISSING
            node = node[part]
        else:
            return _MISSING
    return node


def satisfies(value: Any, constraint: Any) -> bool:
    if isinstance(constraint, bool):
        return isinstance(value, bool) and value is constraint
    if isinstance(constraint, list):
        if len(constraint) != 2 or isinstance(value, bool):
            return False
        if not isinstance(value, (int, float)):
            return False
        low, high = constraint
        return low <= value <= high
    if isinstance(constraint, dict):
        if set(constraint) != {"in"}:
            raise ValueError(f"unsupported constraint {constraint!r}")
        return value in constraint["in"]
    return value == constraint


def check(evidence: dict, constraints: dict[str, Any]) -> list[str]:
    """Return one message per violated constraint; empty means all hold."""
    violations = []
    for path, constraint in constraints.items():
        value = resolve(evidence, path)
        if value is _MISSING:
            violations.append(f"{path}: not present in tool output")
        elif not satisfies(value, constraint):
            violations.append(f"{path}: expected {constraint!r}, tool returned {value!r}")
    return violations


def validate_constraint(constraint: Any) -> str | None:
    """Return an error message if a constraint is malformed."""
    if isinstance(constraint, (bool, str, int, float)):
        return None
    if isinstance(constraint, list):
        if len(constraint) == 2 and all(
            isinstance(x, (int, float)) and not isinstance(x, bool) for x in constraint
        ):
            return None if constraint[0] <= constraint[1] else "range low > high"
        return "range must be [low, high] numbers"
    if isinstance(constraint, dict):
        if set(constraint) == {"in"} and isinstance(constraint["in"], list):
            return None
        return 'dict constraint must be {"in": [...]}'
    return f"unsupported constraint type {type(constraint).__name__}"
