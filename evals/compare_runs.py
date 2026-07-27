"""
PersonaCR Defect Hunter — Prompt Regression Comparison
======================================================
Compares two eval runs (e.g. before/after a Defect Hunter prompt change)
and flags whether catch-rate regressed.

Workflow:
    1. python evals/run_eval.py --version v1      # baseline
    2. (edit the system_prompt / user_prompt in backend/src/agents/defect_hunter.py)
    3. python evals/run_eval.py --version v2      # after change
    4. python evals/compare_runs.py v1 v2         # did it regress?

Usage:
    python evals/compare_runs.py <baseline_version> <new_version>
"""

import json
import sys
from pathlib import Path

RESULTS_DIR = Path(__file__).parent / "results"


def load(version):
    path = RESULTS_DIR / f"eval_{version}.json"
    if not path.exists():
        raise SystemExit(f"No results for '{version}'. Run: python evals/run_eval.py --version {version}")
    return json.loads(path.read_text())


def main():
    if len(sys.argv) != 3:
        raise SystemExit("Usage: python evals/compare_runs.py <baseline_version> <new_version>")

    base = load(sys.argv[1])
    new = load(sys.argv[2])

    d_catch = round(new["catch_rate_pct"] - base["catch_rate_pct"], 1)
    d_fp = round(new["false_positive_rate_pct"] - base["false_positive_rate_pct"], 1)

    print(f"\n{'metric':<24}{base['version']:>12}{new['version']:>12}{'delta':>10}")
    print("-" * 58)
    print(f"{'catch-rate %':<24}{base['catch_rate_pct']:>12}{new['catch_rate_pct']:>12}{d_catch:>+10}")
    print(f"{'false-positive %':<24}{base['false_positive_rate_pct']:>12}{new['false_positive_rate_pct']:>12}{d_fp:>+10}")
    print("-" * 58)

    # Per-case catch regressions (defects the baseline caught but the new run missed)
    base_cases = {c["id"]: c for c in base["per_case"]}
    regressions = []
    for c in new["per_case"]:
        b = base_cases.get(c["id"])
        if b and not c["is_clean"] and c["caught"] < b["caught"]:
            regressions.append((c["id"], b["caught"], c["caught"]))

    if d_catch < 0:
        print(f"\n  REGRESSION: catch-rate dropped {abs(d_catch)} points.")
    elif d_catch > 0:
        print(f"\n  IMPROVEMENT: catch-rate up {d_catch} points.")
    else:
        print("\n  No change in catch-rate.")

    if regressions:
        print("  Cases that newly missed a defect:")
        for cid, was, now in regressions:
            print(f"    - {cid}: caught {was} -> {now}")


if __name__ == "__main__":
    main()
