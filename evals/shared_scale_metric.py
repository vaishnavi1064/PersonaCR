"""
Shared-scale metric: feature-distance of submitted code vs fingerprint.

Framing (a) — see evals/shared_scale_framing.md (weights frozen before re-measure).
Uses backend pattern_extractor via import only; no backend edits.

Run from repo root:
    backend\\.venv\\Scripts\\python.exe evals\\shared_scale_metric.py
    backend\\.venv\\Scripts\\python.exe evals\\shared_scale_metric.py --control-only
    backend\\.venv\\Scripts\\python.exe evals\\shared_scale_metric.py --n6-only
"""
from __future__ import annotations

import argparse
import ast
import io
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
else:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from backend.src.core.github_ingestor import CodeChunk
from backend.src.core.pattern_extractor import extract_fingerprint
from backend.src.agents.style_analyst import filter_findings_by_fingerprint_direction
from backend.src.core.models import StyleFinding

HERE = Path(__file__).parent
RESULTS_DIR = HERE / "results"
FP_PATH = RESULTS_DIR / "minimal_a_fingerprint.json"
PAIRS_PATH = HERE / "minimal_a_pairs.json"
CONTROL_FIXTURES = HERE / "minimal_a_control_fixtures.json"
CONTROL_RAW = RESULTS_DIR / "minimal_a_control_raw.json"
OUT_JSON = RESULTS_DIR / "shared_scale_metric.json"
RESULT_MD = HERE / "minimal_a_result.md"
FRAMING_MD = HERE / "shared_scale_framing.md"

# ── Frozen weights (documented in shared_scale_framing.md) ───────────────────
# DO NOT change after seeing control / N=6 results.
WEIGHTS: dict[str, float] = {
    "type_hint_usage": 0.20,
    "naming_convention": 0.20,
    "docstring_coverage": 0.20,
    "error_handling_rate": 0.20,
    "comprehension_ratio": 0.20,
}
assert abs(sum(WEIGHTS.values()) - 1.0) < 1e-9

RATE_FEATURES = (
    "type_hint_usage",
    "docstring_coverage",
    "error_handling_rate",
    "comprehension_ratio",
)
MATERIAL_DEVIATION_THRESHOLD = 0.35  # frozen with weights

# Keyword cues for "does the review mention this true deviation?"
# Category tokens + description regexes — applied identically to both arms.
MENTION_CUES: dict[str, dict[str, Any]] = {
    "type_hint_usage": {
        "categories": {"type_safety", "type_hints", "typing", "type_hint"},
        "patterns": [
            r"\btype[- ]?hint",
            r"\btype[- ]?annotat",
            r"\bmissing (types|type hints|annotations)\b",
            r"\bno type hints?\b",
            r"\bwithout type hints?\b",
            r"\buntyped\b",
        ],
    },
    "naming_convention": {
        "categories": {"naming"},
        "patterns": [
            r"\bcamel[Cc]ase\b",
            r"\bPascal[Cc]ase\b",
            r"\bsnake_case\b",
            r"\bnaming convention\b",
            r"\bfunction name\b",
        ],
    },
    "docstring_coverage": {
        "categories": {"documentation", "docstring", "docs"},
        "patterns": [
            r"\bdocstring\b",
            r"\bdocumentation\b",
            r"\b:rtype:\b",
            r"\b:return:\b",
            r"\bArgs:\b",
            r"\bverbose (doc|documentation)\b",
        ],
    },
    "error_handling_rate": {
        "categories": {"error_handling", "exceptions"},
        "patterns": [
            r"\btry[- ]?except\b",
            r"\berror handl",
            r"\bexception\b",
            r"\btry/except\b",
            r"\bnested try\b",
        ],
    },
    "comprehension_ratio": {
        "categories": {"style", "complexity", "comprehension"},
        "patterns": [
            r"\bcomprehension\b",
            r"\bdict comprehens",
            r"\blist comprehens",
            r"\bgenerator express",
        ],
    },
}

# Historical N=6 pair ids (reportable set before expand). Metric weights unchanged.
N6_PAIR_IDS = (
    "pair_1_merge_headers",
    "pair_2_build_url",
    "pair_3_parse_status",
)


def _function_name(code: str) -> str:
    try:
        tree = ast.parse(code)
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                return node.name
    except SyntaxError:
        pass
    m = re.search(r"^\s*def\s+([A-Za-z_][A-Za-z0-9_]*)", code, re.MULTILINE)
    return m.group(1) if m else "unknown"


def extract_code_features(code: str, language: str = "python") -> dict[str, Any]:
    """Same extractor as Layer-1 fingerprint, on a single snippet."""
    name = _function_name(code)
    chunk = CodeChunk(
        file_path="eval_snippet.py",
        language=language,
        function_name=name,
        source=code,
        start_line=1,
        end_line=max(1, len(code.splitlines())),
    )
    return extract_fingerprint([chunk])


def _naming_distance(code_features: dict, fingerprint: dict) -> float:
    code_name = code_features.get("naming_convention")
    fp_name = fingerprint.get("naming_convention")
    if not code_name or not fp_name:
        return 0.0
    return 0.0 if code_name == fp_name else 1.0


def feature_distances(
    code_features: dict,
    fingerprint: dict,
    weights: dict[str, float] | None = None,
) -> dict[str, Any]:
    """
    Per-dimension and aggregate feature-distance on the frozen shared scale.
    Identical for personalized and generic arms (code+FP only).
    """
    w = weights or WEIGHTS
    per: dict[str, dict[str, Any]] = {}

    for key in RATE_FEATURES:
        code_v = float(code_features.get(key, 0.0) or 0.0)
        fp_v = float(fingerprint.get(key, 0.0) or 0.0)
        d = abs(code_v - fp_v)
        per[key] = {
            "code": code_v,
            "fingerprint": fp_v,
            "distance": round(d, 4),
            "weight": w[key],
            "weighted": round(w[key] * d, 4),
            "material": d >= MATERIAL_DEVIATION_THRESHOLD,
        }

    nd = _naming_distance(code_features, fingerprint)
    per["naming_convention"] = {
        "code": code_features.get("naming_convention"),
        "fingerprint": fingerprint.get("naming_convention"),
        "distance": round(nd, 4),
        "weight": w["naming_convention"],
        "weighted": round(w["naming_convention"] * nd, 4),
        "material": nd >= MATERIAL_DEVIATION_THRESHOLD,
    }

    total = sum(per[k]["weighted"] for k in w)
    match_score = 100.0 * (1.0 - total)
    material_dims = [k for k, v in per.items() if v["material"]]
    return {
        "per_feature": per,
        "feature_distance": round(total, 4),
        "feature_match_score": round(match_score, 2),
        "material_deviations": material_dims,
        "n_material": len(material_dims),
        "weights": dict(w),
        "material_threshold": MATERIAL_DEVIATION_THRESHOLD,
    }


_PRAISE_PATTERNS = (
    r"\bconsistent with\b",
    r"\bfollows the\b",
    r"\bmatches (the )?(developer|fingerprint|pattern)\b",
    r"\bin line with\b",
    r"\baligns with\b",
    r"\bno deviation\b",
)


def _is_praise_finding(finding: dict) -> bool:
    """Consistency/praise notes are not deviation flags (framing-a tracking)."""
    text = finding.get("description") or ""
    return any(re.search(p, text, re.I) for p in _PRAISE_PATTERNS)


def finding_mentions_dimension(finding: dict, dim: str) -> bool:
    """True if a finding flags this feature dimension as a deviation (not praise)."""
    if _is_praise_finding(finding):
        return False
    cues = MENTION_CUES[dim]
    cat = (finding.get("category") or "").strip().lower().replace(" ", "_")
    text = " ".join(
        [
            finding.get("description") or "",
            finding.get("submitted_value") or "",
            finding.get("fingerprint_value") or "",
        ]
    )
    pattern_hit = any(re.search(p, text, re.I) for p in cues["patterns"])
    # Broad categories (style/complexity) only count with a text cue — avoids
    # counting unrelated style nits as comprehension/error hits.
    broad = cat in {"style", "complexity"}
    if cat in cues["categories"] and not broad:
        return True
    if broad and cat in cues["categories"]:
        return pattern_hit
    return pattern_hit

def tracking_for_arm(
    findings: list[dict],
    distance_result: dict[str, Any],
) -> dict[str, Any]:
    """
    Recall of material deviations in findings; false-alarm dims mentioned
    when not material. Same rules for both arms.
    """
    material = set(distance_result["material_deviations"])
    all_dims = list(WEIGHTS.keys())
    mentioned = {d: False for d in all_dims}
    for f in findings or []:
        if (f.get("category") or "").lower() == "error":
            continue
        for d in all_dims:
            if finding_mentions_dimension(f, d):
                mentioned[d] = True

    true_pos = sorted(d for d in material if mentioned[d])
    false_neg = sorted(d for d in material if not mentioned[d])
    false_pos = sorted(d for d in all_dims if d not in material and mentioned[d])
    recall = (len(true_pos) / len(material)) if material else None
    return {
        "material_deviations": sorted(material),
        "mentioned": {k: v for k, v in mentioned.items() if v},
        "true_positives": true_pos,
        "false_negatives": false_neg,
        "false_positives": false_pos,
        "recall_material": recall,
        "n_material": len(material),
        "n_tp": len(true_pos),
        "n_fp": len(false_pos),
        "n_findings_ex_error": sum(
            1 for f in (findings or []) if (f.get("category") or "").lower() != "error"
        ),
    }


def _load_fp() -> dict:
    data = json.loads(FP_PATH.read_text(encoding="utf-8"))
    return data["fingerprint"]


def _to_style_findings(raw: list[dict]) -> list[StyleFinding]:
    out: list[StyleFinding] = []
    for f in raw or []:
        out.append(
            StyleFinding(
                category=f.get("category") or "",
                severity=f.get("severity") or "medium",
                description=f.get("description") or "",
                fingerprint_value=f.get("fingerprint_value") or "",
                submitted_value=f.get("submitted_value") or "",
            )
        )
    return out


def _findings_as_dicts(findings: list[StyleFinding]) -> list[dict]:
    return [
        {
            "category": f.category,
            "severity": f.severity,
            "description": f.description,
            "fingerprint_value": f.fingerprint_value,
            "submitted_value": f.submitted_value,
        }
        for f in findings
    ]


def _load_evidence_findings(
    pair_id: str,
    version: str,
    arm: str,
    fingerprint: dict | None = None,
) -> list[dict] | None:
    """
    Load stored Style Analyst findings. Personalized arm applies Defect B
    direction filter against the requests fingerprint (same as production
    post-fix) so tracking reflects the fixed system without new Groq calls.

    Prefer pair sidecar JSON; fall back to minimal_a_checkpoint.jsonl evidence.
    """
    raw = None
    path = RESULTS_DIR / f"minimal_a_{pair_id}_evidence.json"
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
        key = f"{version}/{arm}"
        arm_block = (data.get("arms") or {}).get(key)
        if arm_block:
            sa = (arm_block.get("evidence") or {}).get("style_analyst") or {}
            raw = sa.get("raw_findings")

    if raw is None:
        from evals.minimal_a import load_checkpoint, _ckpt_key

        ckpt = load_checkpoint()
        rec = ckpt.get(_ckpt_key(pair_id, version, arm))
        if rec:
            sa = (rec.get("evidence") or {}).get("style_analyst") or {}
            raw = sa.get("raw_findings")

    if raw is None:
        return None
    findings = _to_style_findings(list(raw))
    if arm == "personalized" and fingerprint is not None:
        findings = filter_findings_by_fingerprint_direction(findings, fingerprint)
    return _findings_as_dicts(findings)


def _control_findings_from_raw(arm: str, case_id: str) -> list[dict] | None:
    """
    Pull findings from control raw JSON.
    Personalized Style Analyst probe → cases[].instrumentation.raw_findings.
    Generic arm → style issues under cases[].arms.generic_meta.issues.
    """
    if not CONTROL_RAW.exists():
        return None
    data = json.loads(CONTROL_RAW.read_text(encoding="utf-8"))
    for block in data.get("cases") or []:
        if block.get("id") != case_id:
            continue
        if arm == "personalized":
            raw = (block.get("instrumentation") or {}).get("raw_findings")
            return list(raw) if raw is not None else None
        if arm == "generic":
            issues = (block.get("arms") or {}).get("generic_meta", {}).get("issues")
            if issues is None:
                return None
            return [
                {
                    "category": i.get("category") or "",
                    "severity": i.get("severity") or "medium",
                    "description": i.get("description") or "",
                    "fingerprint_value": "",
                    "submitted_value": "",
                }
                for i in issues
                if (i.get("type") or "") == "style"
            ]
    return None


def measure_snippet(
    code: str,
    fingerprint: dict,
    findings: list[dict] | None = None,
) -> dict[str, Any]:
    feats = extract_code_features(code)
    dist = feature_distances(feats, fingerprint)
    out: dict[str, Any] = {
        "code_features_selected": {k: feats.get(k) for k in WEIGHTS},
        "distance": dist,
    }
    if findings is not None:
        out["tracking"] = tracking_for_arm(findings, dist)
    return out


def run_control(fingerprint: dict) -> dict[str, Any]:
    fixtures = json.loads(CONTROL_FIXTURES.read_text(encoding="utf-8"))
    cases_out = {}
    for case in fixtures["cases"]:
        cid = case["id"]
        measured = measure_snippet(case["code"], fingerprint)
        # Arm-independent distance; optional tracking from stored control raw
        tracking_by_arm = {}
        for arm in ("personalized", "generic"):
            findings = _control_findings_from_raw(arm, cid)
            if findings is not None:
                tracking_by_arm[arm] = tracking_for_arm(
                    findings, measured["distance"]
                )
        cases_out[cid] = {
            "label": case.get("label"),
            "task": case.get("task"),
            **measured,
            "tracking_by_arm": tracking_by_arm or None,
        }

    max_in = cases_out["control_max_in_style"]["distance"]["feature_distance"]
    max_off = cases_out["control_max_off_style"]["distance"]["feature_distance"]
    gate_ok = max_in < max_off
    return {
        "cases": cases_out,
        "summary": {
            "max_in_distance": max_in,
            "max_off_distance": max_off,
            "sep_off_minus_in": round(max_off - max_in, 4),
            "max_in_match_score": cases_out["control_max_in_style"]["distance"][
                "feature_match_score"
            ],
            "max_off_match_score": cases_out["control_max_off_style"]["distance"][
                "feature_match_score"
            ],
            "gate_max_in_lt_max_off": gate_ok,
        },
    }


def run_pairs(
    fingerprint: dict,
    pair_ids: tuple[str, ...] | list[str] | None = None,
) -> dict[str, Any]:
    """
    Feature-distance + framing-(a) tracking for the given pair ids.
    Weights / mention rules / verdict rule unchanged from N=6 freeze.
    Default: every pair listed in minimal_a_pairs.json.
    """
    pairs = json.loads(PAIRS_PATH.read_text(encoding="utf-8"))["pairs"]
    by_id = {p["id"]: p for p in pairs}
    if pair_ids is None:
        pair_ids = tuple(p["id"] for p in pairs)
    else:
        pair_ids = tuple(pair_ids)

    per_case: list[dict] = []
    per_pair_sep: list[dict] = []
    missing_evidence: list[str] = []

    for pid in pair_ids:
        if pid not in by_id:
            raise SystemExit(f"Unknown pair id: {pid}")
        pair = by_id[pid]
        pair_row: dict[str, Any] = {"pair_id": pid, "versions": {}}
        for version, code_key in (("in_style", "in_style"), ("off_style", "off_style")):
            code = pair[code_key]
            base = measure_snippet(code, fingerprint)
            arms_track: dict[str, Any] = {}
            for arm in ("personalized", "generic"):
                findings = _load_evidence_findings(pid, version, arm, fingerprint)
                if findings is None:
                    arms_track[arm] = {"error": "missing_evidence_findings"}
                    missing_evidence.append(f"{pid}/{version}/{arm}")
                else:
                    arms_track[arm] = tracking_for_arm(findings, base["distance"])
            row = {
                "pair_id": pid,
                "version": version,
                "violations_designed": pair.get("violations_in_off_style")
                if version == "off_style"
                else [],
                **base,
                "tracking_by_arm": arms_track,
            }
            per_case.append(row)
            pair_row["versions"][version] = {
                "feature_distance": base["distance"]["feature_distance"],
                "feature_match_score": base["distance"]["feature_match_score"],
                "material_deviations": base["distance"]["material_deviations"],
                "tracking_by_arm": arms_track,
            }
        in_d = pair_row["versions"]["in_style"]["feature_distance"]
        off_d = pair_row["versions"]["off_style"]["feature_distance"]
        pair_row["sep_off_minus_in"] = round(off_d - in_d, 4)
        pair_row["off_farther_than_in"] = off_d > in_d

        # Per-case arm comparison under framing (a): OFF recall + IN FP restraint
        def _case_arm_stats(arm: str) -> dict[str, Any]:
            tin = pair_row["versions"]["in_style"]["tracking_by_arm"].get(arm) or {}
            toff = pair_row["versions"]["off_style"]["tracking_by_arm"].get(arm) or {}
            if "error" in tin or "error" in toff:
                return {"error": "missing_evidence"}
            return {
                "off_recall": toff.get("recall_material"),
                "off_tp": toff.get("n_tp"),
                "off_material": toff.get("n_material"),
                "in_fp": tin.get("n_fp"),
                "in_n_material": tin.get("n_material"),
            }

        p_stats = _case_arm_stats("personalized")
        g_stats = _case_arm_stats("generic")
        case_verdict = "missing_evidence"
        if "error" not in p_stats and "error" not in g_stats:
            p_off_r = p_stats["off_recall"]
            g_off_r = g_stats["off_recall"]
            # Treat None recall (0 material) as 1.0 for OFF? Prefer None → skip
            if p_off_r is None and g_off_r is None:
                case_verdict = "no_material_off"
            elif p_off_r is None or g_off_r is None:
                case_verdict = "inconclusive"
            else:
                better_off = p_off_r > g_off_r
                equal_off = p_off_r == g_off_r
                better_in_fp = p_stats["in_fp"] <= g_stats["in_fp"]
                worse_off = p_off_r < g_off_r
                if better_off and better_in_fp:
                    case_verdict = "personalized_better"
                elif worse_off and p_stats["in_fp"] >= g_stats["in_fp"]:
                    case_verdict = "generic_better"  # wrong-way for thesis
                elif equal_off and p_stats["in_fp"] == g_stats["in_fp"]:
                    case_verdict = "tie"
                else:
                    case_verdict = "mixed"
        pair_row["per_case_arm_comparison"] = {
            "personalized": p_stats,
            "generic": g_stats,
            "case_verdict": case_verdict,
        }
        per_pair_sep.append(pair_row)

    in_dists = [
        c["distance"]["feature_distance"] for c in per_case if c["version"] == "in_style"
    ]
    off_dists = [
        c["distance"]["feature_distance"]
        for c in per_case
        if c["version"] == "off_style"
    ]

    def _avg(xs: list[float]) -> float:
        return round(sum(xs) / len(xs), 4) if xs else float("nan")

    def _agg_tracking(arm: str, version: str) -> dict[str, Any]:
        recalls = []
        tp = fp = mat = 0
        n = 0
        for c in per_case:
            if c["version"] != version:
                continue
            t = c["tracking_by_arm"].get(arm) or {}
            if "error" in t:
                continue
            n += 1
            mat += t.get("n_material", 0)
            tp += t.get("n_tp", 0)
            fp += t.get("n_fp", 0)
            if t.get("recall_material") is not None:
                recalls.append(t["recall_material"])
        return {
            "n_cases": n,
            "mean_recall_material": round(sum(recalls) / len(recalls), 4)
            if recalls
            else None,
            "total_material": mat,
            "total_tp": tp,
            "total_fp": fp,
            "pooled_recall": round(tp / mat, 4) if mat else None,
        }

    tracking_summary = {
        arm: {
            "in_style": _agg_tracking(arm, "in_style"),
            "off_style": _agg_tracking(arm, "off_style"),
        }
        for arm in ("personalized", "generic")
    }

    p_off = tracking_summary["personalized"]["off_style"]["pooled_recall"]
    g_off = tracking_summary["generic"]["off_style"]["pooled_recall"]
    p_in_fp = tracking_summary["personalized"]["in_style"]["total_fp"]
    g_in_fp = tracking_summary["generic"]["in_style"]["total_fp"]
    p_in_n = tracking_summary["personalized"]["in_style"]["n_cases"] or 1
    g_in_n = tracking_summary["generic"]["in_style"]["n_cases"] or 1
    p_in_fp_rate = p_in_fp / p_in_n
    g_in_fp_rate = g_in_fp / g_in_n

    if p_off is None or g_off is None:
        verdict = "inconclusive"
        verdict_reason = "missing evidence for tracking comparison"
    else:
        better_off_recall = p_off > g_off
        better_or_equal_in_fp = p_in_fp_rate <= g_in_fp_rate
        worse_off = p_off < g_off
        if better_off_recall and better_or_equal_in_fp:
            verdict = "yes"
            verdict_reason = (
                f"personalized OFF material-recall {p_off} > generic {g_off}; "
                f"IN false-alarm rate {p_in_fp_rate:.2f} <= generic {g_in_fp_rate:.2f}"
            )
        elif worse_off and (p_in_fp_rate >= g_in_fp_rate):
            verdict = "no"
            verdict_reason = (
                f"personalized OFF material-recall {p_off} < generic {g_off}; "
                f"no IN-FP advantage"
            )
        elif p_off == g_off and abs(p_in_fp_rate - g_in_fp_rate) < 1e-9:
            verdict = "inconclusive"
            verdict_reason = "identical OFF recall and IN false-alarm rates"
        else:
            verdict = "inconclusive"
            verdict_reason = (
                f"mixed: OFF recall p={p_off} g={g_off}; "
                f"IN FP-rate p={p_in_fp_rate:.2f} g={g_in_fp_rate:.2f}"
            )

    wrong_way = [
        p["pair_id"]
        for p in per_pair_sep
        if p["per_case_arm_comparison"]["case_verdict"] == "generic_better"
    ]
    personalized_better = [
        p["pair_id"]
        for p in per_pair_sep
        if p["per_case_arm_comparison"]["case_verdict"] == "personalized_better"
    ]

    return {
        "n_pairs": len(pair_ids),
        "n_cases": len(per_case),
        "pair_ids": list(pair_ids),
        "missing_evidence": missing_evidence,
        "per_case": per_case,
        "per_pair": per_pair_sep,
        "distance_summary": {
            "avg_in_distance": _avg(in_dists),
            "avg_off_distance": _avg(off_dists),
            "sep_off_minus_in": round(_avg(off_dists) - _avg(in_dists), 4),
            "pairs_off_farther_than_in": sum(
                1 for p in per_pair_sep if p["off_farther_than_in"]
            ),
            "n_pairs": len(per_pair_sep),
        },
        "tracking_summary": tracking_summary,
        "robustness": {
            "personalized_better_pairs": personalized_better,
            "generic_better_wrong_way_pairs": wrong_way,
            "n_personalized_better": len(personalized_better),
            "n_generic_better": len(wrong_way),
            "n_pairs_scored": sum(
                1
                for p in per_pair_sep
                if p["per_case_arm_comparison"]["case_verdict"]
                not in ("missing_evidence",)
            ),
        },
        "framing_a_verdict": {
            "verdict": verdict,
            "reason": verdict_reason,
            "personalized_off_pooled_recall": p_off,
            "generic_off_pooled_recall": g_off,
            "personalized_in_fp_rate": round(p_in_fp_rate, 4),
            "generic_in_fp_rate": round(g_in_fp_rate, 4),
        },
    }


def run_n6(fingerprint: dict) -> dict[str, Any]:
    """Backward-compatible alias for the original N=6 pair set. """
    return run_pairs(fingerprint, N6_PAIR_IDS)


def append_expand_result_md(
    payload: dict[str, Any],
    *,
    n_paired_clean: int,
    n_throttled_excluded: int,
    groq_cost_note: str,
    n_runs: int,
) -> None:
    """Append expand-N section; never overwrite prior diagnoses or N=6 section."""
    n_block = payload.get("n_full") or payload.get("n6")
    if not n_block:
        return
    ts = payload["generated_at"]
    v = n_block["framing_a_verdict"]
    ds = n_block["distance_summary"]
    rob = n_block.get("robustness") or {}

    lines = [
        "",
        "---",
        "",
        f"## Shared-scale expand — N={n_paired_clean} paired-clean (APPEND)",
        "",
        f"**Generated:** {ts}  ",
        "**Metric:** frozen fair shared-scale (framing a) — weights/thresholds unchanged.  ",
        f"**Paired-clean N:** {n_paired_clean} "
        f"({n_block['n_pairs']} pairs × in/off).  ",
        f"**Throttled/errored arms excluded from averages:** {n_throttled_excluded} "
        "(honesty: never checkpointed).  ",
        f"**Groq / runs:** {groq_cost_note}  ",
        f"**Harness runs this expand:** {n_runs}.  ",
        "New-case construction: `evals/minimal_a_pairs_construction.md`.",
        "",
        "### Per-pair feature-distance (arm-identical)",
        "",
        "| Pair | IN dist | OFF dist | sep (off−in) | OFF farther? |",
        "|------|--------:|---------:|-------------:|:------------:|",
    ]
    for p in n_block["per_pair"]:
        vin = p["versions"]["in_style"]["feature_distance"]
        voff = p["versions"]["off_style"]["feature_distance"]
        lines.append(
            f"| {p['pair_id']} | {vin} | {voff} | {p['sep_off_minus_in']} | "
            f"{'yes' if p['off_farther_than_in'] else 'no'} |"
        )
    lines += [
        "",
        f"Mean IN dist **{ds['avg_in_distance']}**, mean OFF dist "
        f"**{ds['avg_off_distance']}**, mean sep **{ds['sep_off_minus_in']}** "
        f"({ds['pairs_off_farther_than_in']}/{ds['n_pairs']} pairs OFF farther).",
        "",
        "### Per-pair framing-(a) arm tracking",
        "",
        "| Pair | p OFF recall | g OFF recall | p IN FP | g IN FP | case verdict |",
        "|------|-------------:|-------------:|--------:|--------:|--------------|",
    ]
    for p in n_block["per_pair"]:
        cmp_ = p["per_case_arm_comparison"]
        ps, gs = cmp_["personalized"], cmp_["generic"]
        if "error" in ps or "error" in gs:
            lines.append(
                f"| {p['pair_id']} | — | — | — | — | {cmp_['case_verdict']} |"
            )
            continue
        lines.append(
            f"| {p['pair_id']} | {ps.get('off_recall')} | {gs.get('off_recall')} | "
            f"{ps.get('in_fp')} | {gs.get('in_fp')} | {cmp_['case_verdict']} |"
        )
    lines += [
        "",
        "### Pooled means (framing a)",
        "",
        "| Arm | OFF pooled recall | IN FP-rate (dims/case) |",
        "|-----|------------------:|-----------------------:|",
        f"| personalized | {v['personalized_off_pooled_recall']} | "
        f"{v['personalized_in_fp_rate']} |",
        f"| generic | {v['generic_off_pooled_recall']} | {v['generic_in_fp_rate']} |",
        "",
        f"**Reason:** {v['reason']}",
        "",
        "### Robustness / consistency",
        "",
        f"- Personalized-better pairs: **{rob.get('n_personalized_better')}** "
        f"`{rob.get('personalized_better_pairs')}`",
        f"- Wrong-way (generic better): **{rob.get('n_generic_better')}** "
        f"`{rob.get('generic_better_wrong_way_pairs')}`",
        "",
        "### Honest verdict (expand-N)",
        "",
        f"**Framing-(a) one-line:** personalization separates/tracks better than "
        f"generic on this fair scale: **{v['verdict']}**.",
        "",
        "N≈12–15 remains modest — directional + consistency only; "
        "**not** strong statistical significance. "
        "Compare to the prior N=6 append above for held / strengthened / weakened.",
        "",
        "Artifacts: `evals/results/shared_scale_metric.json`, "
        "`evals/minimal_a_pairs_construction.md`.",
        "",
    ]
    with RESULT_MD.open("a", encoding="utf-8") as f:
        f.write("\n".join(lines))


def main() -> None:
    parser = argparse.ArgumentParser(description="Shared-scale feature-distance metric")
    parser.add_argument("--control-only", action="store_true")
    parser.add_argument("--n6-only", action="store_true", help="Only original 3 pairs")
    parser.add_argument(
        "--full-n",
        action="store_true",
        help="Measure all pairs in minimal_a_pairs.json (expand-N)",
    )
    parser.add_argument(
        "--no-append-md",
        action="store_true",
        help="Skip appending to minimal_a_result.md",
    )
    parser.add_argument(
        "--append-expand",
        action="store_true",
        help="Append expand-N section (does not overwrite N=6 append)",
    )
    parser.add_argument("--groq-cost-note", type=str, default="0 (measurement only)")
    parser.add_argument("--n-runs", type=int, default=0)
    parser.add_argument("--n-throttled-excluded", type=int, default=0)
    args = parser.parse_args()

    if not FP_PATH.exists():
        raise SystemExit(f"Missing fingerprint: {FP_PATH}")
    if not FRAMING_MD.exists():
        raise SystemExit(
            f"Framing doc missing ({FRAMING_MD}) — freeze framing/weights before running."
        )

    fingerprint = _load_fp()
    generated_at = datetime.now(timezone.utc).isoformat()

    control = None
    n_block = None
    if not args.n6_only and not args.full_n:
        # default historical behavior: control + n6
        pass

    if not args.n6_only and not args.full_n:
        print("=== CONTROL FIRST (feature-distance, arm-independent) ===")
        control = run_control(fingerprint)
        s = control["summary"]
        print(
            f"  MAX-IN dist={s['max_in_distance']} match={s['max_in_match_score']} | "
            f"MAX-OFF dist={s['max_off_distance']} match={s['max_off_match_score']} | "
            f"sep={s['sep_off_minus_in']} gate_ok={s['gate_max_in_lt_max_off']}"
        )
        if not s["gate_max_in_lt_max_off"]:
            print("CONTROL GATE FAILED — feature-distance does not separate extremes.")
        print("\n=== N=6 feature-distance + framing-(a) tracking ===")
        n_block = run_n6(fingerprint)
        key = "n6"
    elif args.n6_only:
        print("\n=== N=6 feature-distance + framing-(a) tracking ===")
        n_block = run_n6(fingerprint)
        key = "n6"
    else:
        # --full-n
        print("=== CONTROL FIRST (feature-distance, arm-independent) ===")
        control = run_control(fingerprint)
        s = control["summary"]
        print(
            f"  MAX-IN dist={s['max_in_distance']} | MAX-OFF dist={s['max_off_distance']} | "
            f"sep={s['sep_off_minus_in']} gate_ok={s['gate_max_in_lt_max_off']}"
        )
        print("\n=== FULL-N feature-distance + framing-(a) tracking ===")
        n_block = run_pairs(fingerprint, pair_ids=None)
        key = "n_full"

    ds = n_block["distance_summary"]
    print(
        f"  avg IN={ds['avg_in_distance']} OFF={ds['avg_off_distance']} "
        f"sep={ds['sep_off_minus_in']} "
        f"({ds['pairs_off_farther_than_in']}/{ds['n_pairs']} OFF farther)"
    )
    v = n_block["framing_a_verdict"]
    print(f"  framing-(a) verdict: {v['verdict']} — {v['reason']}")
    if n_block.get("missing_evidence"):
        print(f"  missing evidence: {n_block['missing_evidence']}")
    if n_block.get("robustness"):
        rob = n_block["robustness"]
        print(
            f"  robustness: personalized_better={rob['n_personalized_better']} "
            f"wrong_way={rob['n_generic_better']} {rob['generic_better_wrong_way_pairs']}"
        )

    payload = {
        "generated_at": generated_at,
        "framing": "a",
        "framing_doc": str(FRAMING_MD.as_posix()),
        "weights": dict(WEIGHTS),
        "material_threshold": MATERIAL_DEVIATION_THRESHOLD,
        "groq_cost": 0,
        "note": (
            "Feature-distance from pattern_extractor on submitted code vs requests FP. "
            "Tracking from stored Style Analyst evidence; personalized findings passed "
            "through filter_findings_by_fingerprint_direction (Defect B). "
            "Weights frozen — expand-N only adds cases."
        ),
        "control": control,
        "n6": n_block if key == "n6" else None,
        "n_full": n_block if key == "n_full" else None,
    }
    RESULTS_DIR.mkdir(exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    print(f"\nWrote {OUT_JSON}")

    if args.append_expand and key == "n_full" and control and n_block:
        if n_block.get("missing_evidence"):
            print("Refusing to append expand MD while evidence missing:", n_block["missing_evidence"])
        else:
            append_expand_result_md(
                payload,
                n_paired_clean=n_block["n_cases"],
                n_throttled_excluded=args.n_throttled_excluded,
                groq_cost_note=args.groq_cost_note,
                n_runs=args.n_runs,
            )
            print(f"Appended expand section to {RESULT_MD}")
    elif control and key == "n6" and n_block and not args.no_append_md and not args.append_expand:
        # preserve old N=6 append path only when explicitly re-running legacy
        pass


if __name__ == "__main__":
    main()
