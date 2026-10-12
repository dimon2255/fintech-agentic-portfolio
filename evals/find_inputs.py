"""Developer tool: choose fixture input IDs that realize a scenario's evidence.

The projects' simulated data sources derive their observations from MD5
hashes of input IDs (customer, IP, device, email, document number). A scenario
is authored as narrative, evidence constraints and labels first, with the ID
fields set to ``"SEARCH"`` (optionally ``"SEARCH:<hint>"``: an IP's first octet,
an email's ``local@domain`` stem, or a document-number pattern such as
``"K#8"``, meaning K followed by eight pseudo-random digits). This tool then
searches candidate IDs, calling the project's own tool functions, until every
evidence constraint holds, and writes the chosen IDs into the golden file.
Labels and constraints are never touched.

    python -m evals.find_inputs p2            # all P2 scenarios with SEARCH fields
    python -m evals.find_inputs p3 P3-04      # one scenario

The search is sequential and deterministic, so rerunning it on an unchanged
scenario picks the same IDs. It runs once at authoring time; the harness
verifies the evidence on every run (``evals.evidence``).
"""

from __future__ import annotations

import argparse
import asyncio
import copy
import hashlib
import importlib
import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.append(str(REPO_ROOT))

from evals import PROJECTS  # noqa: E402
from evals.evidence import check  # noqa: E402

MAX_TRIES = 3_000_000


def _group(constraints: dict, prefix: str) -> dict:
    return {k: v for k, v in constraints.items() if k.startswith(prefix + ".")}


def _hint(value: str, default: str) -> str:
    return value.split(":", 1)[1] if ":" in value else default


async def _first(candidates, ok, label):
    for n, candidate in enumerate(candidates):
        if n >= MAX_TRIES:
            break
        if await ok(candidate):
            return candidate
    raise SystemExit(f"no candidate found for {label} within {MAX_TRIES} tries")


def _customer_ids():
    n = 10000
    while True:
        yield f"cust_{n:05d}"
        n += 1


def _ips(first_octet: str):
    n = 0
    while True:
        yield f"{first_octet}.{n // 64516 % 254 + 1}.{n // 254 % 254 + 1}.{n % 254 + 1}"
        n += 1


def _emails(local: str, domain: str):
    n = 1
    while True:
        yield f"{local}{n}@{domain}"
        n += 1


def _devices():
    n = 0x1000
    while True:
        yield f"dev_{n:08x}"
        n += 1


def _doc_numbers(pattern: str):
    """Realistic-looking numbers: ``"K#8"`` yields K plus 8 pseudo-random digits."""
    prefix, _, count = pattern.partition("#")
    width = int(count) if count.isdigit() else 5
    n = 0
    while True:
        digits = str(int(hashlib.md5(f"{pattern}:{n}".encode()).hexdigest(), 16))[:width]
        yield f"{prefix}{digits}"
        n += 1


async def search_transaction(project: str, scenario: dict) -> dict:
    models = importlib.import_module("src.models")
    tools = importlib.import_module("src.tools")
    tools.SIMULATED_LATENCY_SECONDS = 0
    txn = copy.deepcopy(scenario["inputs"]["transaction"])
    ev = scenario["fixtures"]["evidence"]

    async def holds(field, value, prefixes, fns):
        trial = dict(txn, **{field: value})
        t = models.Transaction.model_validate(trial)
        evidence = {}
        for prefix, fn in zip(prefixes, fns):
            evidence[prefix] = (await fn(t)).model_dump(mode="json")
        return not any(check(evidence, _group(ev, p)) for p in prefixes)

    if str(txn["customer_id"]).startswith("SEARCH"):
        txn["customer_id"] = await _first(
            _customer_ids(),
            lambda c: holds("customer_id", c, ["velocity"], [tools.check_velocity]),
            "customer_id",
        )
    if str(txn["ip_address"]).startswith("SEARCH"):
        txn["ip_address"] = await _first(
            _ips(_hint(txn["ip_address"], "73")),
            lambda ip: holds("ip_address", ip, ["geo"], [tools.lookup_geo]),
            "ip_address",
        )
    if project == "p2" and str(txn["customer_email"]).startswith("SEARCH"):
        local, domain = _hint(txn["customer_email"], "user@gmail.com").split("@")
        txn["customer_email"] = await _first(
            _emails(local, domain),
            lambda e: holds("customer_email", e, ["identity"], [tools.check_identity]),
            "customer_email",
        )
    if str(txn["device_id"]).startswith("SEARCH"):
        prefixes = ["device"] + (["behavioral"] if project == "p2" else [])
        fns = [tools.fingerprint_device] + ([tools.analyze_behavior] if project == "p2" else [])
        txn["device_id"] = await _first(
            _devices(), lambda d: holds("device_id", d, prefixes, fns), "device_id"
        )
    return {"transaction": txn}


async def search_application(scenario: dict) -> dict:
    models = importlib.import_module("src.models")
    tools = importlib.import_module("src.tools")
    tools.SIMULATED_LATENCY_SECONDS = 0
    app = copy.deepcopy(scenario["inputs"]["application"])
    ev = scenario["fixtures"]["evidence"]

    for i, doc in enumerate(app["documents_submitted"]):
        if not str(doc["document_number"]).startswith("SEARCH"):
            continue
        group = {
            k.replace(f"documents.{i}.", "", 1): v
            for k, v in ev.items()
            if k.startswith(f"documents.{i}.")
        }

        async def doc_holds(number, doc=doc, group=group):
            d = models.DocumentSubmission.model_validate(dict(doc, document_number=number))
            ext = await tools.document_extract(d)
            cls = await tools.document_classify(d)
            val = await tools.document_validate(d)
            evidence = {
                "extraction_confidence": ext.extraction_confidence,
                "is_correct_type": cls.is_correct_type,
                **val.model_dump(mode="json"),
            }
            return not check(evidence, group)

        doc["document_number"] = await _first(
            _doc_numbers(_hint(doc["document_number"], "DOC-#8")), doc_holds, f"document {i}"
        )
    return {"application": app}


def inner(project: str, scenario_paths: list[str]) -> None:
    os.environ["ANTHROPIC_API_KEY"] = ""
    os.environ["OPENAI_API_KEY"] = ""
    found = {}
    for path in scenario_paths:
        scenario = json.loads(Path(path).read_text(encoding="utf-8"))
        if project == "p3":
            found[path] = asyncio.run(search_application(scenario))
        else:
            found[path] = asyncio.run(search_transaction(project, scenario))
    print(json.dumps(found))


def _has_search(value) -> bool:
    if isinstance(value, str):
        return value.startswith("SEARCH")
    if isinstance(value, dict):
        return any(_has_search(v) for v in value.values())
    if isinstance(value, list):
        return any(_has_search(v) for v in value)
    return False


def outer(project_key: str, ids: list[str]) -> None:
    project = PROJECTS[project_key]
    paths = []
    for path in sorted(project.golden_dir.glob("*.json")):
        scenario = json.loads(path.read_text(encoding="utf-8"))
        if ids and scenario["id"] not in ids:
            continue
        if _has_search(scenario["inputs"]):
            paths.append(str(path))
    if not paths:
        print("nothing to search")
        return
    env = dict(os.environ, PYTHONPATH=str(REPO_ROOT), ANTHROPIC_API_KEY="", OPENAI_API_KEY="")
    proc = subprocess.run(
        [sys.executable, "-m", "evals.find_inputs", "--inner", project_key, *paths],
        cwd=project.project_dir(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise SystemExit(proc.stderr[-3000:])
    found = json.loads(proc.stdout.strip().splitlines()[-1])
    for path, inputs in found.items():
        scenario = json.loads(Path(path).read_text(encoding="utf-8"))
        scenario["inputs"].update(inputs)
        Path(path).write_text(json.dumps(scenario, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"{scenario['id']}: inputs written")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--inner", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("project", choices=sorted(PROJECTS))
    parser.add_argument("items", nargs="*", help="scenario ids (outer) or paths (inner)")
    args = parser.parse_args()
    if args.inner:
        inner(args.project, args.items)
    else:
        outer(args.project, args.items)


if __name__ == "__main__":
    main()
