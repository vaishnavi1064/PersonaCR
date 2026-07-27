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

# Pairs used in the reportable N=6 set (3 pairs × in/off).
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
    """
    path = RESULTS_DIR / f"minimal_a_{pair_id}_evidence.json"
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    key = f"{version}/{arm}"
    arm_block = (data.get("arms") or {}).get(key)
    if not arm_block:
        return None
    sa = (arm_block.get("evidence") or {}).get("style_analyst") or {}
    raw = sa.get("raw_findings")
    if raw is None:
        return None
    findings = _to_style_findings(list(raw))
    if arm == "personalized" and fingerprint is not None:
        findings = filter_findings_by_fingerprint_direction(findings, fingerprint)
    # generic: empty FP → filter is a no-op; leave raw as stored
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


def run_n6(fingerprint: dict) -> dict[str, Any]:
    pairs = json.loads(PAIRS_PATH.read_text(encoding="utf-8"))["pairs"]
    by_id = {p["id"]: p for p in pairs}
    per_case: list[dict] = []
    per_pair_sep: list[dict] = []

    for pid in N6_PAIR_IDS:
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

    # Arm tracking aggregates
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

    # Framing (a): net tracking advantage on OFF recall + IN false-positive restraint
    p_off = tracking_summary["personalized"]["off_style"]["pooled_recall"]
    g_off = tracking_summary["generic"]["off_style"]["pooled_recall"]
    p_in_fp = tracking_summary["personalized"]["in_style"]["total_fp"]
    g_in_fp = tracking_summary["generic"]["in_style"]["total_fp"]
    p_in_n = tracking_summary["personalized"]["in_style"]["n_cases"] or 1
    g_in_n = tracking_summary["generic"]["in_style"]["n_cases"] or 1
    # Lower false-positive rate on IN is better
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
            # Mixed signals
            verdict = "inconclusive"
            verdict_reason = (
                f"mixed: OFF recall p={p_off} g={g_off}; "
                f"IN FP-rate p={p_in_fp_rate:.2f} g={g_in_fp_rate:.2f}"
            )

    return {
        "n_pairs": len(N6_PAIR_IDS),
        "n_cases": len(per_case),
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
        "framing_a_verdict": {
            "verdict": verdict,
            "reason": verdict_reason,
            "personalized_off_pooled_recall": p_off,
            "generic_off_pooled_recall": g_off,
            "personalized_in_fp_rate": round(p_in_fp_rate, 4),
            "generic_in_fp_rate": round(g_in_fp_rate, 4),
        },
    }


def append_result_md(payload: dict[str, Any]) -> None:
    """Append shared-scale section; do not overwrite prior diagnoses."""
    control = payload["control"]["summary"]
    n6 = payload["n6"]
    ts = payload["generated_at"]
    v = n6["framing_a_verdict"]

    lines = [
        "",
        "---",
        "",
        "## Shared-scale metric (feature-distance) — APPEND",
        "",
        f"**Generated:** {ts}  ",
        f"**Framing:** (a) — personalized review track of objective feature-distance "
        f"(see `{FRAMING_MD.name}`).  ",
        "**Primary shared metric:** `feature_distance(code, fingerprint)` via "
        "`pattern_extractor.extract_fingerprint` on one CodeChunk.  ",
        "**Findings-based style_score:** diagnostic only (not used for this verdict).  ",
        f"**Groq cost this pass:** **{payload['groq_cost']}** "
        "(re-scored from stored fixtures + evidence).",
        "",
        "### Frozen weights (locked before re-measure)",
        "",
        "| Feature | Weight |",
        "|---------|-------:|",
    ]
    for k, w in WEIGHTS.items():
        lines.append(f"| `{k}` | {w:.2f} |")
    lines += [
        "",
        f"Material deviation threshold: **{MATERIAL_DEVIATION_THRESHOLD}**. "
        "Weights were **not** adjusted after seeing results.",
        "",
        "### Control FIRST (arm-independent distance gate)",
        "",
        "| Fixture | feature_distance | feature_match_score |",
        "|---------|-----------------:|--------------------:|",
        f"| MAX-IN | {control['max_in_distance']} | {control['max_in_match_score']} |",
        f"| MAX-OFF | {control['max_off_distance']} | {control['max_off_match_score']} |",
        "",
        f"sep (off − in distance) = **{control['sep_off_minus_in']}**  ",
        f"Gate MAX-IN < MAX-OFF: **{control['gate_max_in_lt_max_off']}**",
        "",
        "### N=6 — per-pair feature-distance",
        "",
        "| Pair | IN dist | OFF dist | sep (off−in) | OFF farther? |",
        "|------|--------:|---------:|-------------:|:------------:|",
    ]
    for p in n6["per_pair"]:
        vin = p["versions"]["in_style"]["feature_distance"]
        voff = p["versions"]["off_style"]["feature_distance"]
        lines.append(
            f"| {p['pair_id']} | {vin} | {voff} | {p['sep_off_minus_in']} | "
            f"{'yes' if p['off_farther_than_in'] else 'no'} |"
        )
    ds = n6["distance_summary"]
    lines += [
        "",
        f"Avg IN dist **{ds['avg_in_distance']}**, avg OFF dist **{ds['avg_off_distance']}**, "
        f"sep **{ds['sep_off_minus_in']}** "
        f"({ds['pairs_off_farther_than_in']}/{ds['n_pairs']} pairs OFF farther).",
        "",
        "### Framing (a) — review tracking of material deviations",
        "",
        "Pooled recall of material feature deviations in Style Analyst findings "
        "(stored evidence; same mention rules both arms):",
        "",
        "| Arm | OFF pooled recall | IN false-alarm rate (dims/case) |",
        "|-----|------------------:|--------------------------------:|",
    ]
    for arm in ("personalized", "generic"):
        off_r = n6["tracking_summary"][arm]["off_style"]["pooled_recall"]
        in_fp = n6["framing_a_verdict"][
            "personalized_in_fp_rate"
            if arm == "personalized"
            else "generic_in_fp_rate"
        ]
        lines.append(f"| {arm} | {off_r} | {in_fp} |")
    lines += [
        "",
        f"**Reason:** {v['reason']}",
        "",
        "### One-line verdict",
        "",
        f"**On a fair scale, does personalization separate in/off better than generic: "
        f"{v['verdict']}.**",
        "",
        "Artifacts: `evals/results/shared_scale_metric.json`, "
        "`evals/shared_scale_framing.md`, `evals/shared_scale_metric.py`.",
        "",
    ]
    with RESULT_MD.open("a", encoding="utf-8") as f:
        f.write("\n".join(lines))


def main() -> None:
    parser = argparse.ArgumentParser(description="Shared-scale feature-distance metric")
    parser.add_argument("--control-only", action="store_true")
    parser.add_argument("--n6-only", action="store_true")
    parser.add_argument(
        "--no-append-md",
        action="store_true",
        help="Skip appending to minimal_a_result.md",
    )
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
    n6 = None
    if not args.n6_only:
        print("=== CONTROL FIRST (feature-distance, arm-independent) ===")
        control = run_control(fingerprint)
        s = control["summary"]
        print(
            f"  MAX-IN dist={s['max_in_distance']} match={s['max_in_match_score']} | "
            f"MAX-OFF dist={s['max_off_distance']} match={s['max_off_match_score']} | "
            f"sep={s['sep_off_minus_in']} gate_ok={s['gate_max_in_lt_max_off']}"
        )
        for cid, case in control["cases"].items():
            mats = case["distance"]["material_deviations"]
            print(f"  {cid}: material={mats}")
        if not s["gate_max_in_lt_max_off"]:
            print("CONTROL GATE FAILED — feature-distance does not separate extremes.")

    if not args.control_only:
        if control is None:
            # still need control in full payload if only n6 requested? allow partial
            pass
        print("\n=== N=6 feature-distance + framing-(a) tracking ===")
        n6 = run_n6(fingerprint)
        ds = n6["distance_summary"]
        print(
            f"  avg IN={ds['avg_in_distance']} OFF={ds['avg_off_distance']} "
            f"sep={ds['sep_off_minus_in']} "
            f"({ds['pairs_off_farther_than_in']}/{ds['n_pairs']} OFF farther)"
        )
        v = n6["framing_a_verdict"]
        print(f"  framing-(a) verdict: {v['verdict']} — {v['reason']}")

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
            "through filter_findings_by_fingerprint_direction (Defect B) to match "
            "post-fix production. No Groq calls."
        ),
        "control": control,
        "n6": n6,
    }
    RESULTS_DIR.mkdir(exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    print(f"\nWrote {OUT_JSON}")

    if control and n6 and not args.no_append_md:
        append_result_md(payload)
        print(f"Appended section to {RESULT_MD}")


if __name__ == "__main__":
    main()
