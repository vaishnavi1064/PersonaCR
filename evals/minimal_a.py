"""
Minimal-A Harness — Phase 3 & 4 (resumable)
===========================================
Two-arm experiment: does PersonaCR's personalization mechanism work END-TO-END?
- Personalized arm: real requests fingerprint + live ChromaDB retrieval
- Generic arm:      fingerprint={}, no retrieval

Measures STYLE MATCH via Style Analyst `overall_style_score` (0–100) as the
primary separation metric (off − in). Finding counts are retained as a
diagnostic column only — do not judge personalization on counts alone.

Honesty guards (do not weaken):
- Error findings (category="error") excluded from style counts and rejected mid-run
- Exponential backoff 5/15/45/90 on throttle/degenerate
- Throttled cases excluded from averages and NEVER written to the checkpoint

Resumability:
- Clean (case_id, arm) results append to evals/minimal_a_checkpoint.jsonl
- On start, skip keys already present in the checkpoint
- Throttled/errored arms are left absent so the next run retries them

Run from repo root:
    backend\\.venv\\Scripts\\python.exe evals\\minimal_a.py
    backend\\.venv\\Scripts\\python.exe evals\\minimal_a.py --max-cases 2
    backend\\.venv\\Scripts\\python.exe evals\\minimal_a.py --time-budget 600

Output:
    evals/minimal_a_checkpoint.jsonl
    evals/results/minimal_a.json
    evals/minimal_a_result.md  (via --write-report / auto when target met)
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
from statistics import mean

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
else:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / "backend" / ".env")

from backend.src.agents.orchestrator import run_review

HERE        = Path(__file__).parent
PAIRS_PATH  = HERE / "minimal_a_pairs.json"
FP_PATH     = HERE / "results" / "minimal_a_fingerprint.json"
RESULTS_DIR = HERE / "results"
CHECKPOINT  = HERE / "minimal_a_checkpoint.jsonl"
RESULT_MD   = HERE / "minimal_a_result.md"

# ── Tuning knobs ──────────────────────────────────────────────────────────────
# Groq llama-3.3-70b-versatile (docs base limits, org-level):
#   RPM=30, RPD=1000, TPM=12_000, TPD=100_000
# Each arm ≈ 3–4 LLM calls; TPM is the binding constraint (~1 arm / min safe).
SLEEP_BETWEEN_CALLS_S = 25     # pacing between arms (approach but don't blow RPM/TPM)
MAX_RETRIES           = 4      # max retries per (case, arm) on throttle/degenerate
BACKOFF_SLEEPS        = (5, 15, 45, 90)
DEGENERATE_EXEC_MS    = 4000
TARGET_PAIRED_CLEAN   = 6      # of 10 max (5 pairs × in/off); enough to report directionally
MAX_IN_FLIGHT         = 1      # serial arms — no concurrent Groq fan-out


def _case_key(pair_id: str, version: str) -> str:
    return f"{pair_id}/{version}"


def _ckpt_key(pair_id: str, version: str, arm: str) -> str:
    return f"{pair_id}/{version}/{arm}"


def _is_clean(arm_result: dict) -> bool:
    """Honesty: clean means not throttled and no error string."""
    return (not arm_result.get("throttled")) and (not arm_result.get("error"))


def _is_degenerate(result_dict: dict) -> bool:
    """
    Detect a throttled/cached non-answer.
    Tell: style_score==50 (default), exec_ms very low, zero style findings.
    This matches the previous benchmark's collapse pattern exactly.
    """
    style_score = result_dict.get("style_score", -1)
    exec_ms     = result_dict.get("exec_ms", 99999)
    n_style     = result_dict.get("n_style_findings", -1)
    return (
        style_score == 50.0
        and exec_ms < DEGENERATE_EXEC_MS
        and n_style == 0
    )


def _count_style_findings(review_result) -> int:
    """
    Count StyleFindings produced by the Style Analyst only.
    Excludes fallback/error findings from the count.
    """
    return sum(
        1
        for issue in review_result.issues
        if issue.get("type") == "style" and issue.get("category") != "error"
    )


def load_checkpoint(path: Path = CHECKPOINT) -> dict[str, dict]:
    """Load clean (case/arm) records keyed by ckpt_key. Corrupt lines skipped."""
    records: dict[str, dict] = {}
    if not path.exists():
        return records
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            key = rec.get("key")
            result = rec.get("result")
            if not key or not isinstance(result, dict):
                continue
            if not _is_clean(result):
                # Never treat a dirty record as done (defense in depth)
                continue
            records[key] = rec
    return records


def append_checkpoint(rec: dict, path: Path = CHECKPOINT) -> None:
    """Append one clean record. Caller must only pass clean results."""
    if not _is_clean(rec.get("result", {})):
        raise ValueError("Refusing to checkpoint a non-clean arm result")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, default=str) + "\n")
        f.flush()


def _write_pair_evidence_sidecar(
    checkpoint: dict[str, dict],
    pair_id: str,
    path: Path | None = None,
) -> Path:
    """
    Write retrieval neighbors + raw Style Analyst findings for one pair
    to evals/results/ (additive audit artifact). Does not change scores.
    """
    RESULTS_DIR.mkdir(exist_ok=True)
    out = path or (RESULTS_DIR / f"minimal_a_{pair_id}_evidence.json")
    arms: dict = {}
    for version in ("in_style", "off_style"):
        for arm in ("personalized", "generic"):
            key = _ckpt_key(pair_id, version, arm)
            rec = checkpoint.get(key)
            if not rec:
                arms[f"{version}/{arm}"] = None
                continue
            result = rec.get("result") or {}
            arms[f"{version}/{arm}"] = {
                "style_score": result.get("style_score"),
                "n_style_findings": result.get("n_style_findings"),
                "similar_functions_found": result.get("similar_functions_found"),
                "throttled": result.get("throttled"),
                "timestamp": rec.get("timestamp"),
                "evidence": rec.get("evidence"),
            }
    payload = {
        "pair_id": pair_id,
        "written_at": datetime.now(timezone.utc).isoformat(),
        "note": (
            "Additive instrumentation from live run_review wrappers. "
            "Style Analyst JSON schema only emits findings + overall_style_score; "
            "finding descriptions are the reasoning."
        ),
        "arms": arms,
    }
    out.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    print(f"\nEvidence sidecar -> {out}")
    return out


def paired_clean_cases(checkpoint: dict[str, dict]) -> list[str]:
    """Return case keys where BOTH personalized and generic arms are clean."""
    cases: dict[str, set[str]] = {}
    for key, rec in checkpoint.items():
        # key = pair_id/version/arm
        parts = key.rsplit("/", 1)
        if len(parts) != 2:
            continue
        case_id, arm = parts
        cases.setdefault(case_id, set()).add(arm)
    return sorted(
        cid for cid, arms in cases.items()
        if {"personalized", "generic"} <= arms
    )


def _capture_retrieval_log(staged: dict) -> dict:
    """Serialize two-stage retrieval the same way Style Analyst builds prompt snippets."""
    functions = staged.get("functions", []) or []
    files = staged.get("files", []) or []
    similar_snippets = ""
    retrieval_log = []
    for i, func in enumerate(functions[:5]):
        src = (func.get("source") or "")[:500]
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
            "source_in_prompt": src,  # exact snippet length placed in Style Analyst prompt
        })
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
        "n_retrieved_logged": len(retrieval_log),
        "similar_snippets_nonempty": bool(similar_snippets.strip()),
        "similar_snippets_chars": len(similar_snippets),
        "prompt_would_include_similar": bool(similar_snippets.strip()),
    }


async def _run_arm(
    code: str,
    language: str,
    fingerprint: dict,
    user_id: str,
    repo_name: str,
    arm_label: str,
) -> tuple[dict, dict | None]:
    """
    Run one arm (personalized or generic) for one code version.
    Returns (result_dict, evidence_or_None).

    Evidence (additive logging — does not change scoring) captures the live
    retrieval neighbors and raw Style Analyst findings from the same
    run_review path that produced style_score. Dirty/throttled arms return
    evidence=None and must not be checkpointed.
    """
    import backend.src.agents.orchestrator as orch
    import backend.src.core.embedder as emb

    for attempt in range(1, MAX_RETRIES + 2):
        t0 = time.monotonic()
        evidence_box: dict = {}
        try:
            orig_query = emb.query_similar_staged
            orig_analyze = orch.analyze_style

            def logged_query(*args, **kwargs):
                staged = orig_query(*args, **kwargs)
                evidence_box["retrieval"] = _capture_retrieval_log(staged)
                return staged

            def logged_analyze(*args, **kwargs):
                style_out, style_ms = orig_analyze(*args, **kwargs)
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
                evidence_box["style_analyst"] = {
                    "style_score": style_out.overall_style_score,
                    "similar_functions_found_field": style_out.similar_functions_found,
                    "style_analyst_ms": style_ms,
                    "raw_findings": raw_findings,
                    "n_raw_findings_ex_error": sum(
                        1 for f in style_out.findings if f.category != "error"
                    ),
                    "n_raw_findings_total": len(raw_findings),
                }
                return style_out, style_ms

            emb.query_similar_staged = logged_query  # type: ignore[assignment]
            orch.analyze_style = logged_analyze  # type: ignore[assignment]
            try:
                result = await run_review(
                    code=code,
                    language=language,
                    fingerprint=fingerprint,
                    user_id=user_id,
                    repo_name=repo_name,
                    max_iterations=1,
                )
            finally:
                emb.query_similar_staged = orig_query  # type: ignore[assignment]
                orch.analyze_style = orig_analyze  # type: ignore[assignment]

            exec_ms = int((time.monotonic() - t0) * 1000)

            # Detect fallback error findings
            has_error = any(issue.get("category") == "error" for issue in result.issues)
            if has_error:
                raise RuntimeError("Groq rate-limit/fallback error detected in findings")

            n_style = _count_style_findings(result)
            style_score = result.review_output.get("style_score", None)
            similar_found = result.review_output.get("similar_functions_used", 0)
            quality = result.review_output.get("quality_scores") or {}

            out = {
                "arm":           arm_label,
                "n_style_findings": n_style,
                "style_score":   style_score,
                "similar_functions_found": similar_found,
                "comprehensiveness": quality.get("comprehensiveness"),
                "conciseness":       quality.get("conciseness"),
                "relevance":         quality.get("relevance"),
                "status":        result.status,
                "exec_ms":       exec_ms,
                "attempt":       attempt,
                "throttled":     False,
                "error":         None,
            }

            if _is_degenerate(out):
                raise RuntimeError("Degenerate response detected")

            # Pipeline issues (post-QA) — additive, for audit
            issues = [
                {
                    "type": i.get("type"),
                    "category": i.get("category"),
                    "severity": i.get("severity"),
                    "description": i.get("description"),
                }
                for i in result.issues
            ]
            evidence = {
                "retrieval": evidence_box.get("retrieval"),
                "style_analyst": evidence_box.get("style_analyst"),
                "pipeline_issues": issues,
                "note": (
                    "Evidence captured from the live run_review path via wrappers; "
                    "scoring/retrieval/agent logic unchanged."
                ),
            }
            # Generic arm may never call query_similar_staged
            if evidence["retrieval"] is None and arm_label == "generic":
                evidence["retrieval"] = {
                    "n_retrieved_functions": 0,
                    "retrieval_functions": [],
                    "prompt_would_include_similar": False,
                    "note": "generic arm — no personalized retrieval expected",
                }

            return out, evidence

        except Exception as e:
            error = str(e)
            exec_ms = int((time.monotonic() - t0) * 1000)
            if attempt <= MAX_RETRIES:
                sleep_s = BACKOFF_SLEEPS[attempt - 1]
                print(
                    f"    [throttle/error on attempt {attempt}] "
                    f"sleeping {sleep_s}s before retry... (error: {error})"
                )
                await asyncio.sleep(sleep_s)
                continue

            return {
                "arm":                   arm_label,
                "n_style_findings":      0,
                "style_score":           50.0,
                "similar_functions_found": 0,
                "comprehensiveness":     None,
                "conciseness":           None,
                "relevance":             None,
                "status":                "throttled",
                "exec_ms":               exec_ms,
                "attempt":               attempt,
                "throttled":             True,
                "error":                 f"Exhausted retries. Last error: {error}",
            }, None

    return {
        "arm":                   arm_label,
        "n_style_findings":      0,
        "style_score":           50.0,
        "similar_functions_found": 0,
        "comprehensiveness":     None,
        "conciseness":           None,
        "relevance":             None,
        "status":                "throttled",
        "exec_ms":               0,
        "attempt":               MAX_RETRIES,
        "throttled":             True,
        "error":                 "Exhausted retries",
    }, None


async def _run_missing_arms_for_case(
    pair: dict,
    version: str,
    fingerprint: dict,
    user_id: str,
    repo_name: str,
    checkpoint: dict[str, dict],
    pace_s: float,
) -> tuple[dict | None, dict | None, bool]:
    """
    Ensure both arms for (pair, version) are clean in checkpoint.
    Returns (personal, generic, progress_made) where missing/throttled arms
    are None until clean. Does not write dirty results to checkpoint.
    """
    pair_id = pair["id"]
    code = pair[version]
    language = "python"
    progress = False

    p_key = _ckpt_key(pair_id, version, "personalized")
    g_key = _ckpt_key(pair_id, version, "generic")

    personal = checkpoint[p_key]["result"] if p_key in checkpoint else None
    generic = checkpoint[g_key]["result"] if g_key in checkpoint else None

    if personal is None:
        print(f"    personalized...", end=" ", flush=True)
        personal_run, personal_ev = await _run_arm(
            code=code, language=language,
            fingerprint=fingerprint,
            user_id=user_id, repo_name=repo_name,
            arm_label="personalized",
        )
        if _is_clean(personal_run):
            rec = {
                "key": p_key,
                "pair_id": pair_id,
                "version": version,
                "arm": "personalized",
                "task": pair.get("task"),
                "violations": pair.get("violations_in_off_style"),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "result": personal_run,
                "evidence": personal_ev,
            }
            append_checkpoint(rec)
            checkpoint[p_key] = rec
            personal = personal_run
            progress = True
            print(
                f"ok ({personal_run['exec_ms']}ms, "
                f"style_score={personal_run.get('style_score')}, "
                f"style_findings={personal_run['n_style_findings']}, "
                f"similar={personal_run['similar_functions_found']}) [checkpointed+evidence]"
            )
        else:
            print(
                f"throttled/err — NOT checkpointed "
                f"({personal_run.get('error', '')[:80]})"
            )
            personal = None
        await asyncio.sleep(pace_s)

    else:
        print(
            f"    personalized... skip (checkpointed, "
            f"style_score={personal.get('style_score')}, "
            f"style_findings={personal['n_style_findings']})"
        )

    if generic is None:
        print(f"    generic.......", end=" ", flush=True)
        generic_run, generic_ev = await _run_arm(
            code=code, language=language,
            fingerprint={},
            user_id="__benchmark_generic__", repo_name="__none__",
            arm_label="generic",
        )
        if _is_clean(generic_run):
            rec = {
                "key": g_key,
                "pair_id": pair_id,
                "version": version,
                "arm": "generic",
                "task": pair.get("task"),
                "violations": pair.get("violations_in_off_style"),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "result": generic_run,
                "evidence": generic_ev,
            }
            append_checkpoint(rec)
            checkpoint[g_key] = rec
            generic = generic_run
            progress = True
            print(
                f"ok ({generic_run['exec_ms']}ms, "
                f"style_score={generic_run.get('style_score')}, "
                f"style_findings={generic_run['n_style_findings']}) [checkpointed+evidence]"
            )
        else:
            print(
                f"throttled/err — NOT checkpointed "
                f"({generic_run.get('error', '')[:80]})"
            )
            generic = None
        await asyncio.sleep(pace_s)
    else:
        print(
            f"    generic....... skip (checkpointed, "
            f"style_score={generic.get('style_score')}, "
            f"style_findings={generic['n_style_findings']})"
        )

    return personal, generic, progress


def _aggregate(per_pair: list[dict]) -> dict:
    """
    Aggregate paired in/off results, excluding throttled cases.
    Primary separation = style_score (off − in). Finding counts kept as diagnostic.
    (In-memory / unit-test path; checkpoint aggregation uses _aggregate_from_checkpoint.)
    """
    personal_in_n, personal_off_n, generic_in_n, generic_off_n = [], [], [], []
    personal_in_s, personal_off_s, generic_in_s, generic_off_s = [], [], [], []
    throttled_cases: list[str] = []

    for p in per_pair:
        pid = p["id"]
        for version in ("in_style", "off_style"):
            pres = p["versions"][version]["personalized"]
            gres = p["versions"][version]["generic"]

            p_throttled = pres["throttled"] or bool(pres["error"])
            g_throttled = gres["throttled"] or bool(gres["error"])

            if p_throttled or g_throttled:
                throttled_cases.append(f"{pid}/{version}")
                continue

            if version == "in_style":
                personal_in_n.append(pres["n_style_findings"])
                generic_in_n.append(gres["n_style_findings"])
                if pres.get("style_score") is not None:
                    personal_in_s.append(pres["style_score"])
                if gres.get("style_score") is not None:
                    generic_in_s.append(gres["style_score"])
            else:
                personal_off_n.append(pres["n_style_findings"])
                generic_off_n.append(gres["n_style_findings"])
                if pres.get("style_score") is not None:
                    personal_off_s.append(pres["style_score"])
                if gres.get("style_score") is not None:
                    generic_off_s.append(gres["style_score"])

    def _safe_mean(vals: list) -> float | None:
        return round(mean(vals), 3) if vals else None

    def _arm_block(in_n, off_n, in_s, off_s) -> dict:
        avg_in_s, avg_off_s = _safe_mean(in_s), _safe_mean(off_s)
        avg_in_n, avg_off_n = _safe_mean(in_n), _safe_mean(off_n)
        return {
            # Primary metric: Style Analyst overall_style_score (0–100)
            "avg_style_score_in_style": avg_in_s,
            "avg_style_score_off_style": avg_off_s,
            "separation": (
                round(avg_off_s - avg_in_s, 3)
                if avg_in_s is not None and avg_off_s is not None
                else None
            ),
            "separation_metric": "style_score_off_minus_in",
            # Diagnostic: finding counts (demoted; do not judge separation on these)
            "avg_style_findings_in_style": avg_in_n,
            "avg_style_findings_off_style": avg_off_n,
            "separation_findings": (
                round(avg_off_n - avg_in_n, 3)
                if avg_in_n is not None and avg_off_n is not None
                else None
            ),
            "n_in": len(in_n),
            "n_off": len(off_n),
        }

    return {
        "personalized": _arm_block(
            personal_in_n, personal_off_n, personal_in_s, personal_off_s
        ),
        "generic": _arm_block(
            generic_in_n, generic_off_n, generic_in_s, generic_off_s
        ),
        "throttled_excluded": throttled_cases,
        "primary_metric": "style_score",
        "primary_metric_note": (
            "overall_style_score from Style Analyst (0=completely different, "
            "100=perfect match to fingerprint). Separation = off − in; "
            "more negative ⇒ off looks more deviant than in."
        ),
    }


def _style_category_counts(issues: list | None) -> dict[str, int]:
    """Per-feature deviation counts from pipeline style issues (excludes error)."""
    counts: dict[str, int] = {}
    for i in issues or []:
        if i.get("type") != "style":
            continue
        cat = i.get("category") or "unknown"
        if cat == "error":
            continue
        counts[cat] = counts.get(cat, 0) + 1
    return counts


def _aggregate_from_checkpoint(checkpoint: dict[str, dict]) -> dict:
    """Aggregate from paired-clean cases. Primary = style_score; counts diagnostic."""
    personal_in_n, personal_off_n, generic_in_n, generic_off_n = [], [], [], []
    personal_in_s, personal_off_s, generic_in_s, generic_off_s = [], [], [], []
    paired = paired_clean_cases(checkpoint)
    incomplete: list[str] = []

    seen_cases: set[str] = set()
    for key in checkpoint:
        parts = key.rsplit("/", 1)
        if len(parts) == 2:
            seen_cases.add(parts[0])
    for cid in sorted(seen_cases):
        if cid not in paired:
            incomplete.append(cid)

    # Per-feature category tallies (when issues were checkpointed)
    feature_in: dict[str, list[int]] = {}
    feature_off: dict[str, list[int]] = {}

    for cid in paired:
        pair_id, version = cid.rsplit("/", 1)
        prec = checkpoint[_ckpt_key(pair_id, version, "personalized")]
        grec = checkpoint[_ckpt_key(pair_id, version, "generic")]
        pres, gres = prec["result"], grec["result"]
        if version == "in_style":
            personal_in_n.append(pres["n_style_findings"])
            generic_in_n.append(gres["n_style_findings"])
            if pres.get("style_score") is not None:
                personal_in_s.append(pres["style_score"])
            if gres.get("style_score") is not None:
                generic_in_s.append(gres["style_score"])
            cats = _style_category_counts(prec.get("issues"))
            for cat, n in cats.items():
                feature_in.setdefault(cat, []).append(n)
        else:
            personal_off_n.append(pres["n_style_findings"])
            generic_off_n.append(gres["n_style_findings"])
            if pres.get("style_score") is not None:
                personal_off_s.append(pres["style_score"])
            if gres.get("style_score") is not None:
                generic_off_s.append(gres["style_score"])
            cats = _style_category_counts(prec.get("issues"))
            for cat, n in cats.items():
                feature_off.setdefault(cat, []).append(n)

    def _safe_mean(vals: list) -> float | None:
        return round(mean(vals), 3) if vals else None

    def _metric_means(arm: str, metric: str) -> dict:
        vals_in, vals_off = [], []
        for cid in paired:
            pair_id, version = cid.rsplit("/", 1)
            res = checkpoint[_ckpt_key(pair_id, version, arm)]["result"]
            v = res.get(metric)
            if v is None:
                continue
            if version == "in_style":
                vals_in.append(v)
            else:
                vals_off.append(v)
        return {
            "avg_in_style": _safe_mean(vals_in),
            "avg_off_style": _safe_mean(vals_off),
            "n_in": len(vals_in),
            "n_off": len(vals_off),
        }

    def _arm_block(in_n, off_n, in_s, off_s, arm: str) -> dict:
        avg_in_s, avg_off_s = _safe_mean(in_s), _safe_mean(off_s)
        avg_in_n, avg_off_n = _safe_mean(in_n), _safe_mean(off_n)
        return {
            "avg_style_score_in_style": avg_in_s,
            "avg_style_score_off_style": avg_off_s,
            "separation": (
                round(avg_off_s - avg_in_s, 3)
                if avg_in_s is not None and avg_off_s is not None
                else None
            ),
            "separation_metric": "style_score_off_minus_in",
            "avg_style_findings_in_style": avg_in_n,
            "avg_style_findings_off_style": avg_off_n,
            "separation_findings": (
                round(avg_off_n - avg_in_n, 3)
                if avg_in_n is not None and avg_off_n is not None
                else None
            ),
            "n_in": len(in_n),
            "n_off": len(off_n),
            "crscore": {
                "comprehensiveness": _metric_means(arm, "comprehensiveness"),
                "conciseness": _metric_means(arm, "conciseness"),
                "relevance": _metric_means(arm, "relevance"),
            },
        }

    all_cats = sorted(set(feature_in) | set(feature_off))
    per_feature = {}
    for cat in all_cats:
        ain = _safe_mean(feature_in.get(cat, []))
        aoff = _safe_mean(feature_off.get(cat, []))
        per_feature[cat] = {
            "avg_count_in_style": ain,
            "avg_count_off_style": aoff,
            "delta_off_minus_in": (
                round(aoff - ain, 3) if ain is not None and aoff is not None else None
            ),
            "n_in_cases_with_cat": len(feature_in.get(cat, [])),
            "n_off_cases_with_cat": len(feature_off.get(cat, [])),
        }

    return {
        "paired_clean_cases": paired,
        "n_paired_clean": len(paired),
        "incomplete_cases": incomplete,
        "primary_metric": "style_score",
        "primary_metric_note": (
            "overall_style_score from Style Analyst (0–100). "
            "Separation = off − in; more negative ⇒ off more deviant."
        ),
        "personalized": _arm_block(
            personal_in_n, personal_off_n, personal_in_s, personal_off_s, "personalized"
        ),
        "generic": _arm_block(
            generic_in_n, generic_off_n, generic_in_s, generic_off_s, "generic"
        ),
        "per_feature_personalized": per_feature,
    }


def _per_case_deltas(checkpoint: dict[str, dict]) -> list[dict]:
    """Per paired-clean case: style_score + diagnostic finding deltas + CRScore."""
    rows = []
    for cid in paired_clean_cases(checkpoint):
        pair_id, version = cid.rsplit("/", 1)
        prec = checkpoint[_ckpt_key(pair_id, version, "personalized")]
        grec = checkpoint[_ckpt_key(pair_id, version, "generic")]
        p, g = prec["result"], grec["result"]
        ps, gs = p.get("style_score"), g.get("style_score")
        row = {
            "case": cid,
            "style_score_personalized": ps,
            "style_score_generic": gs,
            "delta_style_score": (
                round(ps - gs, 3) if ps is not None and gs is not None else None
            ),
            "n_style_findings_personalized": p["n_style_findings"],
            "n_style_findings_generic": g["n_style_findings"],
            "delta_style_findings": p["n_style_findings"] - g["n_style_findings"],
            "style_categories_personalized": _style_category_counts(prec.get("issues")),
            "style_categories_generic": _style_category_counts(grec.get("issues")),
        }
        for m in ("comprehensiveness", "conciseness", "relevance"):
            pv, gv = p.get(m), g.get(m)
            row[f"{m}_personalized"] = pv
            row[f"{m}_generic"] = gv
            row[f"delta_{m}"] = (
                round(pv - gv, 4) if pv is not None and gv is not None else None
            )
        rows.append(row)
    return rows


def write_result_md(
    checkpoint: dict[str, dict],
    agg: dict,
    *,
    target: int = TARGET_PAIRED_CLEAN,
    path: Path = RESULT_MD,
) -> None:
    """Honest write-up from checkpoint only — no fabricated numbers."""
    n = agg["n_paired_clean"]
    deltas = _per_case_deltas(checkpoint)
    p = agg["personalized"]
    g = agg["generic"]
    incomplete = agg["incomplete_cases"]

    enough = n >= target
    power_note = (
        f"N={n} paired-clean cases is {'at/above' if enough else 'below'} the "
        f"predeclared target of {target}. At this sample size the result is "
        f"{'directional / preliminary — do not claim statistical significance' if n < 30 else 'larger but still should be interpreted cautiously'}."
    )

    lines = [
        "# Minimal-A Result (real checkpoint only)",
        "",
        f"**Generated:** {datetime.now(timezone.utc).isoformat()}",
        f"**Target N (paired-clean):** {target}",
        f"**Achieved N:** {n}",
        f"**Incomplete / unpaired cases in checkpoint:** {len(incomplete)}"
        + (f" (`{', '.join(incomplete)}`)" if incomplete else ""),
        f"**Status:** {'TARGET MET — reportable' if enough else 'INCOMPLETE — need more quota windows'}",
        f"**Primary metric:** `style_score` (Style Analyst `overall_style_score`, 0–100). "
        "Separation = off − in (more negative ⇒ off more deviant).",
        "",
        "## Step 0 budget (context)",
        "",
        "Groq `llama-3.3-70b-versatile` docs base limits: **30 RPM**, **1K RPD**, "
        "**12K TPM**, **100K TPD**. Each arm ≈ 3–4 LLM calls; TPM is binding. "
        f"Harness paces **{SLEEP_BETWEEN_CALLS_S}s** between arms, **{MAX_IN_FLIGHT}** in-flight.",
        "",
        "## Primary metric — style_score separation",
        "",
        "Source: `review_output.style_score` ← Style Analyst `overall_style_score` "
        "(deterministic from findings: start 100, subtract severity penalties "
        "high=25 / medium=12 / low=5; direction-filtered against fingerprint rates). "
        "LLM JSON score field is ignored.",
        "",
        "| Arm | Avg score IN-STYLE | Avg score OFF-STYLE | Separation (off − in) | n_in | n_off |",
        "|-----|-------------------:|--------------------:|----------------------:|-----:|------:|",
        f"| Personalized | {p.get('avg_style_score_in_style')} | {p.get('avg_style_score_off_style')} | **{p.get('separation')}** | {p['n_in']} | {p['n_off']} |",
        f"| Generic | {g.get('avg_style_score_in_style')} | {g.get('avg_style_score_off_style')} | **{g.get('separation')}** | {g['n_in']} | {g['n_off']} |",
        "",
        "## Diagnostic — finding-count separation (demoted; do not judge on this)",
        "",
        "Count of Style Analyst findings with `category != \"error\"`. Kept for visibility only.",
        "",
        "| Arm | Avg findings IN | Avg findings OFF | Separation_findings (off − in) |",
        "|-----|----------------:|-----------------:|-------------------------------:|",
        f"| Personalized | {p.get('avg_style_findings_in_style')} | {p.get('avg_style_findings_off_style')} | {p.get('separation_findings')} |",
        f"| Generic | {g.get('avg_style_findings_in_style')} | {g.get('avg_style_findings_off_style')} | {g.get('separation_findings')} |",
        "",
        "## Per-feature deviation (personalized style issue categories, when checkpointed)",
        "",
    ]

    feats = agg.get("per_feature_personalized") or {}
    if feats:
        lines.append("| Category | Avg count IN | Avg count OFF | Δ (off − in) |")
        lines.append("|----------|-------------:|--------------:|-------------:|")
        for cat, row in sorted(feats.items()):
            lines.append(
                f"| `{cat}` | {row.get('avg_count_in_style')} | "
                f"{row.get('avg_count_off_style')} | {row.get('delta_off_minus_in')} |"
            )
        lines.append("")
    else:
        lines.append(
            "_No per-feature issue texts in main checkpoint "
            "(control runner stores issues; main harness arm records may not)._"
        )
        lines.append("")

    lines.append("## CRScore-style metrics (Layer 3 scores captured per clean arm)")
    lines.append("")

    for metric in ("comprehensiveness", "conciseness", "relevance"):
        pm = p["crscore"][metric]
        gm = g["crscore"][metric]
        lines.append(f"### {metric}")
        lines.append("")
        lines.append(
            f"- Personalized: in={pm['avg_in_style']}, off={pm['avg_off_style']} "
            f"(n_in={pm['n_in']}, n_off={pm['n_off']})"
        )
        lines.append(
            f"- Generic: in={gm['avg_in_style']}, off={gm['avg_off_style']} "
            f"(n_in={gm['n_in']}, n_off={gm['n_off']})"
        )
        # Mean personalized − generic across paired cases that have the metric
        dvals = [
            row[f"delta_{metric}"]
            for row in deltas
            if row.get(f"delta_{metric}") is not None
        ]
        sep = round(mean(dvals), 4) if dvals else None
        lines.append(f"- Separation (personalized − generic), mean over cases with scores: **{sep}**")
        lines.append("")

    lines.extend([
        "## Per-case raw deltas",
        "",
        "| Case | Δ style_score (p−g) | Δ findings (diag) | Δ comp | Δ conc | Δ rel |",
        "|------|--------------------:|------------------:|-------:|-------:|------:|",
    ])
    for row in deltas:
        lines.append(
            f"| `{row['case']}` | {row.get('delta_style_score')} | "
            f"{row['delta_style_findings']} | "
            f"{row['delta_comprehensiveness']} | {row['delta_conciseness']} | "
            f"{row['delta_relevance']} |"
        )

    if not deltas:
        lines.append("| *(none yet)* | — | — | — | — |")

    remaining = max(target - n, 0)
    # Rough: ~2 arms × ~30s pace ≈ 1 min/case minimum; with retries more
    windows_note = (
        f"Need **{remaining}** more paired-clean cases to hit target {target}. "
        f"At ~1–2 clean cases per careful quota window (TPM-limited), "
        f"expect roughly **{max(remaining, 1)}–{max(remaining * 2, 2)}** additional runs "
        f"with `--max-cases 2` (or wait for daily reset if RPD exhausted)."
        if remaining
        else f"Target {target} reached; further runs optional to grow N toward all 10 cases."
    )

    lines.extend([
        "",
        "## Statistical power",
        "",
        power_note,
        "",
        "## What this does and does not demonstrate",
        "",
        (
            "This report shows observed **style_score** separation (primary) and "
            "finding-count separation (diagnostic only) between the personalized arm "
            "(requests fingerprint + live Chroma retrieval) and the generic arm "
            "(empty fingerprint, no collection). Finding counts alone previously "
            "flattened a real signal (see positive control). It does **not** prove "
            "production readiness and generalizes only to these hand-authored pairs "
            "against psf/requests. Throttled and `category=error` arms were never counted."
            if n > 0
            else
            "No paired-clean cases have completed yet. There is **no quantitative "
            "result** to report — only checkpoint infrastructure and a pending quota budget."
        ),
        "",
        "## Quota / remaining work",
        "",
        windows_note,
        "",
        f"Checkpoint file: `{CHECKPOINT.as_posix()}`",
        "",
    ])

    path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote report -> {path}")


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Minimal-A resumable personalization harness")
    p.add_argument(
        "--max-cases", type=int, default=None,
        help="Stop after this many NEW paired-clean cases complete in this run "
             "(already-checkpointed pairs do not count toward the cap).",
    )
    p.add_argument(
        "--time-budget", type=int, default=None,
        help="Stop cleanly after this many seconds (wall clock) for this run.",
    )
    p.add_argument(
        "--pace", type=float, default=SLEEP_BETWEEN_CALLS_S,
        help=f"Seconds between arm calls (default {SLEEP_BETWEEN_CALLS_S}).",
    )
    p.add_argument(
        "--target", type=int, default=TARGET_PAIRED_CLEAN,
        help=f"Paired-clean cases needed to consider experiment reportable (default {TARGET_PAIRED_CLEAN}).",
    )
    p.add_argument(
        "--write-report", action="store_true",
        help="Write evals/minimal_a_result.md from checkpoint (even if target not met).",
    )
    p.add_argument(
        "--report-only", action="store_true",
        help="Skip running arms; only aggregate checkpoint and write the report.",
    )
    p.add_argument(
        "--only-pair", type=str, default=None,
        help="Run only this pair id (e.g. pair_1_merge_headers).",
    )
    p.add_argument(
        "--force-pair", action="store_true",
        help="With --only-pair: ignore existing checkpoint rows for that pair and re-run.",
    )
    return p.parse_args()


async def main() -> None:
    args = _parse_args()

    if not os.environ.get("GROQ_API_KEY") and not args.report_only:
        raise SystemExit("GROQ_API_KEY not set.")
    if not FP_PATH.exists():
        raise SystemExit(f"Fingerprint file not found: {FP_PATH}\nRun minimal_a_setup.py first.")

    fp_data     = json.loads(FP_PATH.read_text(encoding="utf-8"))
    fingerprint = fp_data["fingerprint"]
    user_id     = fp_data["user_id"]
    repo_name   = fp_data["repo_name"]
    pairs_data  = json.loads(PAIRS_PATH.read_text(encoding="utf-8"))
    pairs       = pairs_data["pairs"]

    checkpoint = load_checkpoint()

    if args.only_pair:
        pairs = [p for p in pairs if p["id"] == args.only_pair]
        if not pairs:
            raise SystemExit(f"--only-pair {args.only_pair!r} not found in {PAIRS_PATH}")
        if args.force_pair:
            # Drop in-memory rows so arms re-run; new clean rows append to jsonl
            # (load_checkpoint last-wins on key).
            drop_keys = [
                k for k in list(checkpoint)
                if k.startswith(f"{args.only_pair}/")
            ]
            for k in drop_keys:
                del checkpoint[k]
            print(
                f"  --force-pair: cleared {len(drop_keys)} in-memory checkpoint "
                f"rows for {args.only_pair} (will re-run + append evidence)"
            )

    already_paired = paired_clean_cases(checkpoint)

    print(f"\nMinimal-A Personalization Experiment (resumable)")
    print(f"Repo:   psf/requests  (user_id={user_id})")
    print(f"Pairs:  {len(pairs)} × {{in_style, off_style}}")
    if args.only_pair:
        print(f"Filter: --only-pair {args.only_pair}  force={args.force_pair}")
    print(f"Pace:   {args.pace}s between arms | in-flight={MAX_IN_FLIGHT}")
    print(f"Target: {args.target} paired-clean cases")
    print(f"Checkpoint: {CHECKPOINT} ({len(checkpoint)} clean arm records, "
          f"{len(already_paired)} paired-clean)")
    print(f"Arm A:  personalized (fingerprint + live ChromaDB retrieval)")
    print(f"Arm B:  generic      (fingerprint={{}})")
    print("=" * 65)

    if args.report_only:
        agg = _aggregate_from_checkpoint(checkpoint)
        write_result_md(checkpoint, agg, target=args.target)
        return

    t0 = time.monotonic()
    new_paired_this_run = 0
    stop_reason = "completed_all_or_nothing_left"
    # When filtering to one pair, don't stop early on global N=target
    # (pair may already be counted in checkpoint from prior runs).
    honor_target = args.only_pair is None

    for pair in pairs:
        for version in ("in_style", "off_style"):
            case_id = _case_key(pair["id"], version)
            if case_id in paired_clean_cases(checkpoint):
                print(f"  [{case_id}] already paired-clean — skip")
                continue

            if args.time_budget is not None and (time.monotonic() - t0) >= args.time_budget:
                stop_reason = f"time_budget_{args.time_budget}s"
                print(f"\nStopping: time budget {args.time_budget}s reached.")
                break

            if args.max_cases is not None and new_paired_this_run >= args.max_cases:
                stop_reason = f"max_cases_{args.max_cases}"
                print(f"\nStopping: --max-cases {args.max_cases} new paired-clean reached.")
                break

            print(f"  [{case_id}]")
            before = set(paired_clean_cases(checkpoint))
            try:
                await _run_missing_arms_for_case(
                    pair, version, fingerprint, user_id, repo_name,
                    checkpoint, pace_s=args.pace,
                )
            except Exception as e:
                print(f"  [FATAL] {case_id}: {e}")
                continue

            after = set(paired_clean_cases(checkpoint))
            if case_id in after and case_id not in before:
                new_paired_this_run += 1
                print(f"    → paired-clean (+1 this run, total {len(after)})")

            if honor_target and len(after) >= args.target:
                stop_reason = f"target_{args.target}_met"
                print(f"\nTarget N={args.target} paired-clean reached.")
                break
        else:
            continue
        break

    if args.only_pair:
        _write_pair_evidence_sidecar(checkpoint, args.only_pair)
    else:
        # Write/refresh evidence sidecars for every pair that has checkpoint evidence
        pair_ids = sorted({rec.get("pair_id") for rec in checkpoint.values() if rec.get("pair_id")})
        for pid in pair_ids:
            keys = [
                k for k in checkpoint
                if k.startswith(f"{pid}/") and (checkpoint[k].get("evidence") or {}).get("style_analyst")
            ]
            if len(keys) >= 1:
                _write_pair_evidence_sidecar(checkpoint, pid)

    agg = _aggregate_from_checkpoint(checkpoint)

    print("\n" + "=" * 65)
    print("STYLE_SCORE SEPARATION (primary) + findings (diagnostic)")
    print("-" * 65)
    p, g = agg["personalized"], agg["generic"]
    print(f"  Paired-clean N: {agg['n_paired_clean']} / target {args.target}")
    print(f"  New this run:   {new_paired_this_run}  | stop: {stop_reason}")
    print(f"  {'':35} {'Personalized':>14} {'Generic':>10}")
    print(f"  {'Avg style_score IN-STYLE':35} {str(p.get('avg_style_score_in_style')):>14} {str(g.get('avg_style_score_in_style')):>10}")
    print(f"  {'Avg style_score OFF-STYLE':35} {str(p.get('avg_style_score_off_style')):>14} {str(g.get('avg_style_score_off_style')):>10}")
    print(f"  {'Separation style_score (off-in)':35} {str(p.get('separation')):>14} {str(g.get('separation')):>10}")
    print(f"  {'[diag] findings sep (off-in)':35} {str(p.get('separation_findings')):>14} {str(g.get('separation_findings')):>10}")
    print("=" * 65)

    RESULTS_DIR.mkdir(exist_ok=True)
    output = {
        "meta": {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "repo_url": fp_data["repo_url"],
            "commit_sha": fp_data["commit_sha"],
            "user_id": user_id,
            "repo_name": repo_name,
            "collection": fp_data["collection"],
            "n_pairs": len(pairs),
            "sleep_between_calls_s": args.pace,
            "target_paired_clean": args.target,
            "n_paired_clean": agg["n_paired_clean"],
            "new_paired_this_run": new_paired_this_run,
            "stop_reason": stop_reason,
            "checkpoint": str(CHECKPOINT),
            "arms_differ_by": (
                "fingerprint (personalized=requests FP + live ChromaDB) vs "
                "generic (fingerprint={}, user_id=__benchmark_generic__, no collection)"
            ),
            "groq_budget_note": (
                "llama-3.3-70b-versatile docs: 30 RPM / 1K RPD / 12K TPM / 100K TPD; "
                "TPM binding; ~1 arm/min with 25s pace"
            ),
        },
        "aggregate": agg,
        "per_case_deltas": _per_case_deltas(checkpoint),
    }
    out_path = RESULTS_DIR / "minimal_a.json"
    out_path.write_text(json.dumps(output, indent=2, default=str), encoding="utf-8")
    print(f"\nSaved snapshot -> {out_path}")

    if args.write_report or agg["n_paired_clean"] >= args.target or agg["n_paired_clean"] > 0:
        write_result_md(checkpoint, agg, target=args.target)


if __name__ == "__main__":
    asyncio.run(main())
