"""Golden-set evaluation harness for the three portfolio projects.

See docs/adr/001-golden-set-evaluation.md for the method. The harness never
imports a project's ``src`` package into its own process: the three projects
all use the top-level package name ``src``, so each one runs in its own
subprocess (``evals.worker``) and returns plain JSON. Everything in this
package except ``worker.py`` and ``find_inputs.py`` is pure Python with no
project imports, so the scorer can be unit-tested without the projects.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
EVALS_DIR = REPO_ROOT / "evals"
GOLDEN_DIR = EVALS_DIR / "golden"
BASELINE_PATH = EVALS_DIR / "baseline.json"
DOCS_EVALS_DIR = REPO_ROOT / "docs" / "evals"

# Model the LLM tier runs by default: the projects' own DEFAULT_MODEL default.
DEFAULT_LLM_MODEL = "claude-haiku-4-5-20251001"

# USD per million tokens for the models the LLM tier may run. Source: the
# claude-api skill's model table (cached 2026-10-06): Haiku 4.5 is $1 input,
# $5 output. Used only to estimate cost from response usage tokens.
PRICING_PER_MTOK = {
    "claude-haiku-4-5-20251001": (1.00, 5.00),
    "claude-haiku-4-5": (1.00, 5.00),
}


@dataclass(frozen=True)
class Project:
    key: str
    name: str
    directory: str
    golden: str
    headline: str
    headline_label: str

    def project_dir(self, product_root: Path) -> Path:
        return product_root / self.directory

    @property
    def golden_dir(self) -> Path:
        return GOLDEN_DIR / self.golden


PROJECTS: dict[str, Project] = {
    "p1": Project(
        key="p1",
        name="Transaction Risk Classifier",
        directory="project-1-risk-classifier",
        golden="p1-risk-classifier",
        headline="action",
        headline_label="Recommended action correct",
    ),
    "p2": Project(
        key="p2",
        name="Fraud Detection Swarm",
        directory="project-2-fraud-swarm",
        golden="p2-fraud-swarm",
        headline="action",
        headline_label="Recommended action correct",
    ),
    "p3": Project(
        key="p3",
        name="KYC/AML Compliance Platform",
        directory="project-3-kyc-platform",
        golden="p3-kyc-platform",
        headline="decision",
        headline_label="Compliance decision correct",
    ),
}
