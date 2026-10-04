"""Measure Maria's journey on a running TFOTB (the live app by default): how long each step takes, and whether the
answers meet a fixed checklist. This measures the PRODUCT side of the 10x case only. How long the same steps take a
person without the product has to be timed on people (docs/TIMING_STUDY.md); this script never estimates that.

    python scripts/measure_journey.py [BASE_URL] [--runs 10] [--out docs/measurements/journey.json]

Each run makes the five calls the /10x page makes for CLN3 disease. The first call of the first run may hit a cold
instance and is reported separately. The checklist is written down before running (below), not fitted to the output.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_URL = "https://tfotb-403661953034.us-central1.run.app"
DISEASE = "MONDO:0008767"  # CLN3 disease
KNOWN_RELATED = "MONDO:0018982"  # Niemann-Pick disease type C: the paper EBioMedicine 2023 (PMID 37245481) reports the shared lysosomal cholesterol storage

STEPS = {
    "q1_related_diseases": f"/api/entities/{DISEASE}/related-diseases",
    "q2_patient_groups": f"/api/entities/{DISEASE}/groups",
    "q2_studies": f"/api/entities/{DISEASE}/assets",
    "q3_researchers": f"/api/entities/{DISEASE}/collaborators",
    "q4_evidence_brief": f"/api/entities/{DISEASE}/actions",
}


def get(base: str, path: str) -> tuple[float, dict]:
    t = time.perf_counter()
    with urllib.request.urlopen(base + path, timeout=120) as r:
        body = json.load(r)
    return (time.perf_counter() - t) * 1000, body


def checklist(base: str, answers: dict[str, dict]) -> list[dict]:
    """Fixed pass/fail checks, decided before measuring. A check fails if its evidence is missing."""
    rel = answers["q1_related_diseases"]
    npc = next((d for d in rel["diseases"] if d["id"] == KNOWN_RELATED), None)
    mech = [r for r in (npc or {}).get("reasons", []) if r["kind"] == "mechanism" and r.get("claim_ids")]
    groups = answers["q2_patient_groups"]["groups"]
    studies = answers["q2_studies"]["assets"]
    people = answers["q3_researchers"]["items"]
    brief = next((c for c in answers["q4_evidence_brief"]["cards"] if c["kind"] == "evidence_brief"), None)
    cited = (brief or {}).get("claim_ids", [])
    resolved = 0
    for cid in cited:
        try:
            _, claim = get(base, f"/api/claims/{cid}")
            c = claim.get("claim") or {}
            if c.get("source_span") and c.get("source_url"):  # the quote and the paper it came from
                resolved += 1
        except urllib.error.URLError:
            pass
    return [
        {"check": "lists the known related disease (Niemann-Pick type C)", "pass": npc is not None},
        {"check": "that link has a mechanism reason backed by stored claims", "pass": bool(mech)},
        {"check": "at least one patient group with a registry link", "pass": any(g.get("registry_url") for g in groups)},
        {"check": "at least one matched study with a source URL", "pass": any(s.get("source_url") for s in studies)},
        {"check": "at least one researcher with their papers", "pass": any(p.get("papers") for p in people)},
        {"check": "an evidence brief exists and cites stored claims", "pass": bool(brief) and bool(cited)},
        {"check": "every claim the brief cites opens with its quote and source URL",
         "pass": bool(cited) and resolved == len(cited), "detail": f"{resolved} of {len(cited)} opened"},
    ]


def pct(xs: list[float], p: float) -> float:
    xs = sorted(xs)
    return xs[min(len(xs) - 1, round(p * (len(xs) - 1)))]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("base", nargs="?", default=DEFAULT_URL)
    ap.add_argument("--runs", type=int, default=10)
    ap.add_argument("--out", default="docs/measurements/journey.json")
    a = ap.parse_args()
    base = a.base.rstrip("/")
    cold_ms, _ = get(base, "/api/health")
    runs: dict[str, list[float]] = {k: [] for k in STEPS}
    answers: dict[str, dict] = {}
    totals = []
    for _ in range(a.runs):
        total = 0.0
        for key, path in STEPS.items():
            ms, body = get(base, path)
            runs[key].append(ms)
            answers[key] = body
            total += ms
        totals.append(total)
    checks = checklist(base, answers)
    out = {
        "measured_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "base_url": base,
        "disease": DISEASE,
        "runs": a.runs,
        "first_request_ms": round(cold_ms),
        "what_this_is": "Product-side timing for Maria's four steps, from one client over the internet, plus a fixed "
                        "checklist. It does NOT measure how long a person takes without the product.",
        "per_step_ms": {k: {"median": round(statistics.median(v)), "p95": round(pct(v, 0.95)), "max": round(max(v))}
                        for k, v in runs.items()},
        "all_five_calls_ms": {"median": round(statistics.median(totals)), "p95": round(pct(totals, 0.95))},
        "checklist": checks,
        "checklist_passed": f"{sum(c['pass'] for c in checks)} of {len(checks)}",
    }
    path = Path(a.out)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, indent=2) + "\n")
    print(json.dumps(out, indent=2))
    return 0 if all(c["pass"] for c in checks) else 1


if __name__ == "__main__":
    sys.exit(main())
