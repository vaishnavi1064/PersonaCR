"""
PersonaCR Defect Hunter — Eval Harness
======================================
Runs a labeled test set through the Defect Hunter agent and measures:
  - catch-rate (recall): fraction of known defects the agent found
  - false-positive rate: findings on clean snippets that have no real defect

Usage:
    # from the PersonaCR repo root, with GROQ_API_KEY set:
    python evals/run_eval.py --version v1

The --version label tags the results file so you can compare prompt versions
later with compare_runs.py (that's the "regression testing" part).
"""

import argparse
import json
import os
import time
import sys
from datetime import datetime, timezone
from pathlib import Path

# Ensure the repo root (parent of evals/) is importable so `backend...` resolves
# regardless of how the script is launched (running a script file puts evals/ on
# sys.path, not the repo root).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# PersonaCR's raw Defect Hunter entry point (no orchestrator / Supabase needed).
from backend.src.agents.defect_hunter import hunt_defects

HERE = Path(__file__).parent
TEST_SET_PATH = HERE / "test_set.json"
RESULTS_DIR = HERE / "results"


def all_findings(output) -> list:
    """Flatten DefectHunterOutput (bugs + code_smells + security_issues) into one list."""
    return list(output.bugs) + list(output.code_smells) + list(output.security_issues)


def finding_matches(finding, expected) -> bool:
    """
    A finding 'matches' an expected defect if any of the expected keywords
    appears in the finding's description (case-insensitive). Keyword matching
    keeps the eval robust to exact wording while still requiring the agent to
    name the actual problem.
    """
    text = (finding.description or "").lower() + " " + (finding.category or "").lower()
    return any(kw.lower() in text for kw in expected["keywords"])


def evaluate_case(case) -> dict:
    """Run one snippet through the Defect Hunter and score it against ground truth."""
    output, exec_ms = hunt_defects(case["code"], case["language"])
    findings = all_findings(output)

    expected = case["expected_defects"]
    is_clean = len(expected) == 0

    # How many of the KNOWN defects did the agent catch?
    caught = 0
    for exp in expected:
        if any(finding_matches(f, exp) for f in findings):
            caught += 1

    # On a clean snippet, every finding is a false positive.
    false_positives = len(findings) if is_clean else 0

    return {
        "id": case["id"],
        "is_clean": is_clean,
        "expected_count": len(expected),
        "caught": caught,
        "n_findings": len(findings),
        "false_positives": false_positives,
        "exec_ms": exec_ms,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", default="v1",
                        help="Label for this run (e.g. v1, v2-tighter-prompt)")
    args = parser.parse_args()

    if not os.environ.get("GROQ_API_KEY"):
        raise SystemExit("GROQ_API_KEY is not set. Export it before running.")

    test_set = json.loads(TEST_SET_PATH.read_text())
    cases = test_set["cases"]

    print(f"Running {len(cases)} cases  (version={args.version})\n")
    per_case = []
    for case in cases:
        try:
            r = evaluate_case(case)
        except Exception as e:
            print(f"  [ERROR] {case['id']}: {e}")
            continue
        per_case.append(r)
        tag = "clean" if r["is_clean"] else f"{r['caught']}/{r['expected_count']} caught"
        print(f"  {case['id']:<24} {tag:<14} findings={r['n_findings']} fp={r['false_positives']} ({r['exec_ms']}ms)")

    # Aggregate metrics
    defect_cases = [r for r in per_case if not r["is_clean"]]
    clean_cases = [r for r in per_case if r["is_clean"]]

    total_expected = sum(r["expected_count"] for r in defect_cases)
    total_caught = sum(r["caught"] for r in defect_cases)
    catch_rate = (total_caught / total_expected * 100) if total_expected else 0.0

    total_fp = sum(r["false_positives"] for r in clean_cases)
    fp_rate = (total_fp / len(clean_cases) * 100) if clean_cases else 0.0

    summary = {
        "version": args.version,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "n_cases": len(per_case),
        "total_expected_defects": total_expected,
        "total_caught": total_caught,
        "catch_rate_pct": round(catch_rate, 1),
        "clean_cases": len(clean_cases),
        "total_false_positives": total_fp,
        "false_positive_rate_pct": round(fp_rate, 1),
        "per_case": per_case,
    }

    print("\n" + "=" * 50)
    print(f"  Catch-rate:           {summary['catch_rate_pct']}%  ({total_caught}/{total_expected} known defects)")
    print(f"  False-positive rate:  {summary['false_positive_rate_pct']}%  ({total_fp} on {len(clean_cases)} clean snippets)")
    print("=" * 50)

    RESULTS_DIR.mkdir(exist_ok=True)
    out_path = RESULTS_DIR / f"eval_{args.version}.json"
    out_path.write_text(json.dumps(summary, indent=2))
    print(f"\nSaved -> {out_path}")


if __name__ == "__main__":
    main()
