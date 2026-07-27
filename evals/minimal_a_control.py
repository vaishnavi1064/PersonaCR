"""
Minimal-A Positive Control — diagnostic runner
==============================================
Extreme MAX-IN-STYLE / MAX-OFF-STYLE cases against the psf/requests fingerprint.

Does NOT change honesty guards or scoring in evals/minimal_a.py.
Reuses: _run_arm, pace, backoff, error exclusion, clean-only checkpointing.

Adds instrumentation (Step 3):
- Chroma two-stage retrieval neighbors + distances
- Whether similar snippets are non-empty (would reach Style Analyst prompt)
- Raw Style Analyst findings (text), separate from final orchestrator counts

Run from repo root:
    backend\\.venv\\Scripts\\python.exe evals\\minimal_a_control.py
    backend\\.venv\\Scripts\\python.exe evals\\minimal_a_control.py --pace 25

Outputs:
    evals/minimal_a_control_checkpoint.jsonl
    evals/results/minimal_a_control_raw.json
    evals/minimal_a_control.md
"""
from __future__ import annotations

import argparse
import asyncio
import io
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
else:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / "backend" / ".env")

HERE = Path(__file__).parent
FIX_PATH = HERE / "minimal_a_control_fixtures.json"
FP_PATH = HERE / "results" / "minimal_a_fingerprint.json"
RESULTS_DIR = HERE / "results"
CHECKPOINT = HERE / "minimal_a_control_checkpoint.jsonl"
RAW_OUT = RESULTS_DIR / "minimal_a_control_raw.json"
REPORT = HERE / "minimal_a_control.md"

# Reuse harness primitives — do not fork scoring / honesty logic
from evals.minimal_a import (  # noqa: E402
    SLEEP_BETWEEN_CALLS_S,
    _count_style_findings,
    _is_clean,
    append_checkpoint,
    load_checkpoint,
)


def _probe_retrieval_and_style(
    code: str,
    language: str,
    fingerprint: dict,
    user_id: str,
    repo_name: str,
) -> dict:
    """
    Step 3 instrumentation: what the personalized Style Analyst path sees.
    Calls the same query_similar_staged + analyze_style used in production.
    Does not alter their behavior.
    """
    from backend.src.core.embedder import query_similar_staged
    from backend.src.agents.style_analyst import analyze_style

    staged = query_similar_staged(
        code=code,
        user_id=user_id,
        repo_name=repo_name,
        n_files=3,
        n_functions=8,
        language_filter=language,
    )
    functions = staged.get("functions", [])
    files = staged.get("files", [])

    # Mirror style_analyst snippet construction exactly
    similar_snippets = ""
    retrieval_log = []
    for i, func in enumerate(functions[:5]):
        src = func.get("source", "")[:500]
        meta = func.get("metadata", {}) or {}
        fname = meta.get("function_name", "unknown")
        fpath = meta.get("file_path", "unknown")
        dist = func.get("distance")
        similar_snippets += (
            f"\n--- Similar function {i + 1}: {fname} from {fpath} ---\n{src}\n"
        )
        retrieval_log.append({
            "rank": i + 1,
            "function_name": fname,
            "file_path": fpath,
            "distance": dist,
            "source_preview": src[:200],
        })

    style_out, style_ms = analyze_style(
        code, language, fingerprint, user_id, repo_name, focus_areas=None
    )

    raw_findings = [
        {
            "category": f.category,
            "severity": f.severity,
            "description": f.description,
            "fingerprint_value": f.fingerprint_value,
            "submitted_value": f.submitted_value,
        }
        for f in style_out.findings
    ]
    n_style_ex_error = sum(
        1 for f in style_out.findings if f.category != "error"
    )

    return {
        "retrieval_files": [
            {
                "file_path": (f.get("metadata") or {}).get("file_path"),
                "distance": f.get("distance"),
            }
            for f in files
        ],
        "retrieval_functions": retrieval_log,
        "n_retrieved_functions": len(functions),
        "similar_snippets_nonempty": bool(similar_snippets.strip()),
        "similar_snippets_chars": len(similar_snippets),
        "prompt_would_include_similar": bool(similar_snippets.strip()),
        "style_analyst_ms": style_ms,
        "style_score": style_out.overall_style_score,
        "similar_functions_found_field": style_out.similar_functions_found,
        "raw_findings": raw_findings,
        "n_raw_findings_ex_error": n_style_ex_error,
        "n_raw_findings_total": len(raw_findings),
    }


async def _run_arm_with_issues(
    code: str,
    language: str,
    fingerprint: dict,
    user_id: str,
    repo_name: str,
    arm_label: str,
) -> tuple[dict, list[dict] | None]:
    """
    Same honesty/retry semantics as evals.minimal_a._run_arm, but also
    returns final pipeline issue dicts when clean (for eyeballing).
    Scoring unchanged: style count still uses _count_style_findings.
    """
    from backend.src.agents.orchestrator import run_review
    from evals.minimal_a import (
        BACKOFF_SLEEPS,
        DEGENERATE_EXEC_MS,
        MAX_RETRIES,
        _is_degenerate,
    )

    for attempt in range(1, MAX_RETRIES + 2):
        t0 = time.monotonic()
        try:
            result = await run_review(
                code=code,
                language=language,
                fingerprint=fingerprint,
                user_id=user_id,
                repo_name=repo_name,
                max_iterations=1,
            )
            exec_ms = int((time.monotonic() - t0) * 1000)

            has_error = any(issue.get("category") == "error" for issue in result.issues)
            if has_error:
                raise RuntimeError("Groq rate-limit/fallback error detected in findings")

            n_style = _count_style_findings(result)
            quality = result.review_output.get("quality_scores") or {}
            out = {
                "arm": arm_label,
                "n_style_findings": n_style,
                "style_score": result.review_output.get("style_score"),
                "similar_functions_found": result.review_output.get(
                    "similar_functions_used", 0
                ),
                "comprehensiveness": quality.get("comprehensiveness"),
                "conciseness": quality.get("conciseness"),
                "relevance": quality.get("relevance"),
                "status": result.status,
                "exec_ms": exec_ms,
                "attempt": attempt,
                "throttled": False,
                "error": None,
            }
            if _is_degenerate(out):
                raise RuntimeError("Degenerate response detected")

            issues = [
                {
                    "type": i.get("type"),
                    "category": i.get("category"),
                    "severity": i.get("severity"),
                    "description": i.get("description"),
                }
                for i in result.issues
            ]
            return out, issues

        except Exception as e:
            if attempt <= MAX_RETRIES:
                sleep_s = BACKOFF_SLEEPS[attempt - 1]
                print(
                    f"    [throttle/error on attempt {attempt}] "
                    f"sleeping {sleep_s}s... ({e})"
                )
                await asyncio.sleep(sleep_s)
                continue
            return {
                "arm": arm_label,
                "n_style_findings": 0,
                "style_score": 50.0,
                "similar_functions_found": 0,
                "comprehensiveness": None,
                "conciseness": None,
                "relevance": None,
                "status": "throttled",
                "exec_ms": int((time.monotonic() - t0) * 1000),
                "attempt": attempt,
                "throttled": True,
                "error": f"Exhausted retries. Last error: {e}",
            }, None

    return {
        "arm": arm_label,
        "n_style_findings": 0,
        "style_score": 50.0,
        "similar_functions_found": 0,
        "comprehensiveness": None,
        "conciseness": None,
        "relevance": None,
        "status": "throttled",
        "exec_ms": 0,
        "attempt": MAX_RETRIES,
        "throttled": True,
        "error": "Exhausted retries",
    }, None


async def _run_control_case(
    case: dict,
    fingerprint: dict,
    user_id: str,
    repo_name: str,
    checkpoint: dict,
    pace_s: float,
) -> dict:
    case_id = case["id"]
    code = case["code"]
    language = "python"
    print(f"\n=== {case['label']} ({case_id}) ===")

    print("  [instrument] retrieval + Style Analyst probe...")
    try:
        probe = _probe_retrieval_and_style(
            code, language, fingerprint, user_id, repo_name
        )
        print(
            f"    retrieved={probe['n_retrieved_functions']} funcs, "
            f"snippets_in_prompt={probe['prompt_would_include_similar']}, "
            f"raw_style_findings(ex_error)={probe['n_raw_findings_ex_error']}"
        )
        for f in probe["raw_findings"]:
            if f["category"] == "error":
                continue
            print(f"      • [{f['category']}] {f['description'][:120]}")
    except Exception as e:
        probe = {"error": str(e)}
        print(f"    probe FAILED: {e}")

    await asyncio.sleep(pace_s)

    result_block = {
        "id": case_id,
        "label": case["label"],
        "task": case["task"],
        "design_notes": case.get("design_notes"),
        "instrumentation": probe,
        "arms": {},
    }

    for arm_label, fp, uid, rname in (
        ("personalized", fingerprint, user_id, repo_name),
        ("generic", {}, "__benchmark_generic__", "__none__"),
    ):
        key = f"{case_id}/{arm_label}"
        if key in checkpoint and _is_clean(checkpoint[key]["result"]):
            print(f"  {arm_label}... skip (checkpointed)")
            result_block["arms"][arm_label] = checkpoint[key]["result"]
            result_block["arms"][arm_label + "_meta"] = {
                "from_checkpoint": True,
                "issues": checkpoint[key].get("issues"),
            }
            continue

        print(f"  {arm_label}...", end=" ", flush=True)
        arm_out, issues = await _run_arm_with_issues(
            code=code,
            language=language,
            fingerprint=fp,
            user_id=uid,
            repo_name=rname,
            arm_label=arm_label,
        )

        if _is_clean(arm_out):
            rec = {
                "key": key,
                "case_id": case_id,
                "arm": arm_label,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "result": arm_out,
                "issues": issues,
            }
            append_checkpoint(rec, path=CHECKPOINT)
            checkpoint[key] = rec
            print(
                f"ok findings={arm_out['n_style_findings']} "
                f"score={arm_out.get('style_score')} "
                f"rel={arm_out.get('relevance')} [checkpointed]"
            )
        else:
            print(f"throttled/err — NOT checkpointed ({str(arm_out.get('error'))[:80]})")

        result_block["arms"][arm_label] = arm_out
        result_block["arms"][arm_label + "_meta"] = {
            "from_checkpoint": False,
            "issues": issues,
        }
        await asyncio.sleep(pace_s)

    return result_block


def _verdict(cases_out: list[dict]) -> tuple[str, str]:
    """
    Return (letter, explanation) for A / B / C based on observed data only.
    Primary metric (Bug 1 fix): style_score separation (off − in).
    Finding counts are diagnostic only.
    """
    by_id = {c["id"]: c for c in cases_out}
    inn = by_id.get("control_max_in_style")
    off = by_id.get("control_max_off_style")
    if not inn or not off:
        return "INCOMPLETE", "Both control cases did not complete cleanly."

    p_in = inn["arms"].get("personalized") or {}
    p_off = off["arms"].get("personalized") or {}
    g_in = inn["arms"].get("generic") or {}
    g_off = off["arms"].get("generic") or {}

    if not all(_is_clean(x) for x in (p_in, p_off, g_in, g_off)):
        return "INCOMPLETE", "One or more arms throttled/errored; cannot diagnose."

    # Primary: style_score (0–100). Separation = off − in (more negative = clearer).
    ps_in, ps_off = p_in.get("style_score"), p_off.get("style_score")
    gs_in, gs_off = g_in.get("style_score"), g_off.get("style_score")
    sep_p_score = (
        round(ps_off - ps_in, 3) if ps_in is not None and ps_off is not None else None
    )
    sep_g_score = (
        round(gs_off - gs_in, 3) if gs_in is not None and gs_off is not None else None
    )

    # Diagnostic count separation
    sep_p_n = p_off["n_style_findings"] - p_in["n_style_findings"]
    sep_g_n = g_off["n_style_findings"] - g_in["n_style_findings"]

    raw_in = (inn.get("instrumentation") or {}).get("n_raw_findings_ex_error")
    raw_off = (off.get("instrumentation") or {}).get("n_raw_findings_ex_error")
    raw_sep = None
    if isinstance(raw_in, int) and isinstance(raw_off, int):
        raw_sep = raw_off - raw_in

    off_texts = " ".join(
        f.get("description", "").lower()
        for f in (off.get("instrumentation") or {}).get("raw_findings") or []
        if f.get("category") != "error"
    )
    expected_keywords = (
        "type", "hint", "snake", "camel", "pascal", "docstring", "naming", "except", "error"
    )
    keyword_hits = [k for k in expected_keywords if k in off_texts]
    retrieval_ok = bool((off.get("instrumentation") or {}).get("prompt_would_include_similar"))

    # Per-feature from checkpointed issues
    from evals.minimal_a import _style_category_counts
    cats_in = _style_category_counts((inn.get("arms") or {}).get("personalized_meta", {}).get("issues"))
    cats_off = _style_category_counts((off.get("arms") or {}).get("personalized_meta", {}).get("issues"))

    # Clear score signal: off at least 15 points more deviant than in
    clear_score_sep = sep_p_score is not None and sep_p_score <= -15
    clear_raw_sep = raw_sep is not None and raw_sep >= 2
    raw_mentions_deviations = len(keyword_hits) >= 2

    detail = (
        f"style_score personalized in={ps_in} off={ps_off} sep(off−in)={sep_p_score}; "
        f"generic in={gs_in} off={gs_off} sep={sep_g_score}; "
        f"[diag] findings sep_p={sep_p_n} sep_g={sep_g_n}; "
        f"raw_sep={raw_sep}; keyword_hits={keyword_hits}; "
        f"retrieval_in_prompt={retrieval_ok}; "
        f"per_feature_in={cats_in}; per_feature_off={cats_off}."
    )

    if clear_score_sep:
        residual = []
        if cats_in:
            residual.append(
                f"Bug2 residual: MAX-IN still has style categories {cats_in} "
                f"(false/inverted findings can inflate IN deviance / depress IN score)"
            )
        if "type_safety" not in cats_off and "type" in keyword_hits:
            residual.append(
                "Bug3 residual: type_safety present in raw OFF probe but absent "
                "from final pipeline style issues"
            )
        residual_txt = (" " + "; ".join(residual)) if residual else ""
        return (
            "B",
            f"PRIMARY style_score shows clear personalized separation "
            f"(sep={sep_p_score} ≤ −15). Bug 1 metric fix recovers the control "
            f"signal. {detail}{residual_txt}",
        )

    if (clear_raw_sep or raw_mentions_deviations) and not clear_score_sep:
        return (
            "A",
            f"Raw Style Analyst still shows personalization-relevant text, but "
            f"style_score separation is weak (sep={sep_p_score}). {detail}",
        )

    return (
        "C",
        f"Even MAX-OFF shows weak/no style_score separation (sep={sep_p_score}) "
        f"and raw findings don't clearly differ. {detail}",
    )


def write_report(cases_out: list[dict], letter: str, explanation: str) -> None:
    lines = [
        "# Minimal-A Positive Control — Diagnosis",
        "",
        f"**Generated:** {datetime.now(timezone.utc).isoformat()}",
        f"**Fingerprint:** psf/requests (`evals/results/minimal_a_fingerprint.json`)",
        f"**Fixtures:** `evals/minimal_a_control_fixtures.json` (NOT in main case set)",
        f"**Primary metric (Bug 1 fix):** `style_score` (off − in). Finding counts are diagnostic only.",
        f"**Verdict: {letter}**",
        "",
        "## Verdict explanation",
        "",
        explanation,
        "",
        "## What A / B / C mean (under style_score primary)",
        "",
        "- **A — Broken measurement:** raw findings show a signal; even style_score aggregation flattens it.",
        "- **B — Metric recovers / effect detectable:** style_score shows clear MAX-OFF vs MAX-IN gap on personalized arm.",
        "- **C — Mechanism genuinely flat:** even extremes show ~0 style_score separation and raw findings don't differ.",
        "",
    ]

    for c in cases_out:
        lines.append(f"## Case: {c['label']} (`{c['id']}`)")
        lines.append("")
        lines.append(f"Task: {c['task']}")
        lines.append("")
        inst = c.get("instrumentation") or {}
        lines.append("### Step 3 — Retrieval / prompt instrumentation (personalized path)")
        lines.append("")
        if inst.get("error"):
            lines.append(f"Probe error: `{inst['error']}`")
        else:
            lines.append(
                f"- Retrieved functions: **{inst.get('n_retrieved_functions')}** "
                f"(similar_functions_found field={inst.get('similar_functions_found_field')})"
            )
            lines.append(
                f"- Similar snippets non-empty / would reach prompt: "
                f"**{inst.get('prompt_would_include_similar')}** "
                f"({inst.get('similar_snippets_chars')} chars)"
            )
            lines.append("- Retrieval neighbors:")
            for r in inst.get("retrieval_functions") or []:
                lines.append(
                    f"  - rank {r['rank']}: `{r['function_name']}` "
                    f"in `{r['file_path']}` distance={r['distance']}"
                )
            lines.append("")
            lines.append(
                f"- Raw Style Analyst findings (ex error): "
                f"**{inst.get('n_raw_findings_ex_error')}** "
                f"(style_score={inst.get('style_score')})"
            )
            for f in inst.get("raw_findings") or []:
                lines.append(
                    f"  - [{f.get('category')}/{f.get('severity')}] {f.get('description')}"
                )
                if f.get("fingerprint_value") or f.get("submitted_value"):
                    lines.append(
                        f"    - fp=`{f.get('fingerprint_value')}` → "
                        f"submitted=`{f.get('submitted_value')}`"
                    )
        lines.append("")
        lines.append("### Official arm metrics (primary = style_score)")
        lines.append("")
        lines.append("| Arm | **style_score** | n_style (diag) | similar | comp | conc | rel | status |")
        lines.append("|-----|----------------:|---------------:|--------:|-----:|-----:|----:|--------|")
        for arm in ("personalized", "generic"):
            a = c["arms"].get(arm) or {}
            lines.append(
                f"| {arm} | **{a.get('style_score')}** | {a.get('n_style_findings')} | "
                f"{a.get('similar_functions_found')} | {a.get('comprehensiveness')} | "
                f"{a.get('conciseness')} | {a.get('relevance')} | {a.get('status')} |"
            )
        lines.append("")
        for arm in ("personalized", "generic"):
            meta = c["arms"].get(arm + "_meta") or {}
            issues = meta.get("issues")
            lines.append(f"#### Final pipeline issues ({arm})")
            lines.append("")
            if not issues:
                lines.append("_No issue texts captured (throttled or unavailable)._")
            else:
                for i in issues:
                    lines.append(
                        f"- [{i.get('type')}/{i.get('category')}/{i.get('severity')}] "
                        f"{i.get('description')}"
                    )
            lines.append("")

    # Separation summary table
    by_id = {c["id"]: c for c in cases_out}
    inn = by_id.get("control_max_in_style", {})
    off = by_id.get("control_max_off_style", {})
    p_in = (inn.get("arms") or {}).get("personalized") or {}
    p_off = (off.get("arms") or {}).get("personalized") or {}
    g_in = (inn.get("arms") or {}).get("generic") or {}
    g_off = (off.get("arms") or {}).get("generic") or {}
    raw_in = (inn.get("instrumentation") or {}).get("n_raw_findings_ex_error")
    raw_off = (off.get("instrumentation") or {}).get("n_raw_findings_ex_error")
    from evals.minimal_a import _style_category_counts
    feat_in = _style_category_counts(
        ((inn.get("arms") or {}).get("personalized_meta") or {}).get("issues")
    )
    feat_off = _style_category_counts(
        ((off.get("arms") or {}).get("personalized_meta") or {}).get("issues")
    )
    ps_sep = None
    if p_in.get("style_score") is not None and p_off.get("style_score") is not None:
        ps_sep = round(p_off["style_score"] - p_in["style_score"], 3)
    gs_sep = None
    if g_in.get("style_score") is not None and g_off.get("style_score") is not None:
        gs_sep = round(g_off["style_score"] - g_in["style_score"], 3)

    lines.extend([
        "## Separation summary (Bug 1: style_score is primary)",
        "",
        "| Signal | MAX-IN | MAX-OFF | Separation (off − in) |",
        "|--------|-------:|--------:|----------------------:|",
        f"| **Personalized style_score (PRIMARY)** | {p_in.get('style_score')} | {p_off.get('style_score')} | **{ps_sep}** |",
        f"| Generic style_score | {g_in.get('style_score')} | {g_off.get('style_score')} | {gs_sep} |",
        f"| Personalized n_style (diagnostic) | {p_in.get('n_style_findings')} | {p_off.get('n_style_findings')} | "
        f"{(p_off.get('n_style_findings') or 0) - (p_in.get('n_style_findings') or 0) if p_in and p_off else None} |",
        f"| Generic n_style (diagnostic) | {g_in.get('n_style_findings')} | {g_off.get('n_style_findings')} | "
        f"{(g_off.get('n_style_findings') or 0) - (g_in.get('n_style_findings') or 0) if g_in and g_off else None} |",
        f"| Personalized raw Style Analyst (ex error) | {raw_in} | {raw_off} | "
        f"{(raw_off - raw_in) if isinstance(raw_in, int) and isinstance(raw_off, int) else None} |",
        "",
        "### Per-feature style categories (final pipeline issues, personalized)",
        "",
        f"- MAX-IN categories: `{feat_in}`",
        f"- MAX-OFF categories: `{feat_off}`",
        "",
        "## Constraint note",
        "",
        "Honesty guards, arm definitions, and scoring were not modified. "
        "Only the aggregation/reporting primary metric switched from finding "
        "counts to `style_score`. Control fixtures are separate from "
        "`minimal_a_pairs.json`. No numbers were fabricated.",
        "",
    ])
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nWrote {REPORT}")


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pace", type=float, default=SLEEP_BETWEEN_CALLS_S)
    ap.add_argument("--report-only", action="store_true")
    ap.add_argument(
        "--force",
        action="store_true",
        help="Ignore existing control checkpoint and re-run all arms.",
    )
    args = ap.parse_args()

    if not os.environ.get("GROQ_API_KEY") and not args.report_only:
        raise SystemExit("GROQ_API_KEY not set.")
    if not FP_PATH.exists():
        raise SystemExit(f"Missing {FP_PATH}")
    if not FIX_PATH.exists():
        raise SystemExit(f"Missing {FIX_PATH}")

    fp_data = json.loads(FP_PATH.read_text(encoding="utf-8"))
    fixtures = json.loads(FIX_PATH.read_text(encoding="utf-8"))
    fingerprint = fp_data["fingerprint"]
    user_id = fp_data["user_id"]
    repo_name = fp_data["repo_name"]

    # Separate checkpoint file for control (reuse load/append helpers)
    # load_checkpoint defaults to main path — pass control path
    if args.force and CHECKPOINT.exists() and not args.report_only:
        CHECKPOINT.unlink()
        print(f"  --force: removed {CHECKPOINT}")
    checkpoint = load_checkpoint(CHECKPOINT)

    print("Minimal-A POSITIVE CONTROL")
    print(f"Fingerprint: requests  user_id={user_id}")
    print(f"Cases: {[c['id'] for c in fixtures['cases']]}")
    print(f"Pace: {args.pace}s | checkpoint={CHECKPOINT}")
    print("=" * 65)

    cases_out: list[dict] = []
    if args.report_only and RAW_OUT.exists():
        cases_out = json.loads(RAW_OUT.read_text(encoding="utf-8"))["cases"]
    else:
        for case in fixtures["cases"]:
            block = await _run_control_case(
                case, fingerprint, user_id, repo_name, checkpoint, args.pace
            )
            cases_out.append(block)

        RESULTS_DIR.mkdir(exist_ok=True)
        RAW_OUT.write_text(
            json.dumps(
                {
                    "meta": {
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "fingerprint_repo": "psf/requests",
                        "fixtures": str(FIX_PATH),
                    },
                    "cases": cases_out,
                },
                indent=2,
                default=str,
            ),
            encoding="utf-8",
        )
        print(f"Saved raw -> {RAW_OUT}")

    letter, explanation = _verdict(cases_out)
    print("\n" + "=" * 65)
    print(f"VERDICT: {letter}")
    print(explanation)
    print("=" * 65)
    write_report(cases_out, letter, explanation)


if __name__ == "__main__":
    asyncio.run(main())
