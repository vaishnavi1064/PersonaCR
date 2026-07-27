"""Diagnosis-only: generic-arm scoring under Defect A/B scorer. No logic changes."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.src.agents.style_analyst import (
    SEVERITY_PENALTY,
    compute_style_score_from_findings,
    filter_findings_by_fingerprint_direction,
)
from backend.src.core.models import StyleFinding
from evals.minimal_a import load_checkpoint, _ckpt_key


def dump_findings(label: str, raw: list[dict], fp: dict) -> None:
    findings = [StyleFinding(**f) for f in raw]
    filtered = filter_findings_by_fingerprint_direction(findings, fp)
    print(f"\n### {label}")
    print(f"n_raw={len(findings)} after_direction_filter(fp={'empty' if not fp else 'set'})={len(filtered)}")
    total = 0.0
    print("Arithmetic from 100:")
    for f in filtered:
        cat = (f.category or "").lower()
        sev = (f.severity or "medium").lower()
        pen = 0.0 if cat == "error" else SEVERITY_PENALTY.get(sev, SEVERITY_PENALTY["medium"])
        total += pen
        print(f"  - [{cat}/{sev}] −{pen}")
        print(f"    desc: {f.description}")
        print(f"    fingerprint_value: {f.fingerprint_value!r}")
        print(f"    submitted_value: {f.submitted_value!r}")
    score = compute_style_score_from_findings(filtered)
    print(f"  => 100 − {total} = {score}")


def main() -> None:
    print("SEVERITY_PENALTY", SEVERITY_PENALTY)
    ckpt = load_checkpoint()

    print("\n" + "=" * 72)
    print("STEP 1 — pair1 generic IN/OFF (stored evidence, post-rescore findings)")
    for version in ("in_style", "off_style"):
        key = _ckpt_key("pair_1_merge_headers", version, "generic")
        rec = ckpt[key]
        sa = (rec.get("evidence") or {}).get("style_analyst") or {}
        dump_findings(
            f"{key} checkpoint_score={rec['result'].get('style_score')} "
            f"before_rescore={rec['result'].get('style_score_before_rescore')}",
            sa.get("raw_findings") or [],
            {},  # generic
        )

    print("\n" + "=" * 72)
    print("STEP 1b — pair2/3 generic (live re-run under new scorer)")
    for pid in ("pair_2_build_url", "pair_3_parse_status"):
        for version in ("in_style", "off_style"):
            key = _ckpt_key(pid, version, "generic")
            rec = ckpt[key]
            sa = (rec.get("evidence") or {}).get("style_analyst") or {}
            raw = sa.get("raw_findings") or []
            print(
                f"\n{key}: style_score={rec['result'].get('style_score')} "
                f"n_raw={len(raw)} n_style_findings={rec['result'].get('n_style_findings')}"
            )
            dump_findings(key, raw, {})

    print("\n" + "=" * 72)
    print("STEP 2 — control generic MAX-IN / MAX-OFF (post-fix force re-run)")
    raw_path = ROOT / "evals" / "results" / "minimal_a_control_raw.json"
    raw = json.loads(raw_path.read_text(encoding="utf-8"))
    ctrl_ckpt = load_checkpoint(ROOT / "evals" / "minimal_a_control_checkpoint.jsonl")

    for case in raw["cases"]:
        cid = case["id"]
        print(f"\n## {cid} ({case.get('label')})")
        for arm in ("personalized", "generic"):
            a = case["arms"][arm]
            print(
                f"  {arm}: style_score={a.get('style_score')} "
                f"n_style_findings={a.get('n_style_findings')}"
            )
            issues = [i for i in (a.get("issues") or []) if i.get("type") == "style"]
            print(f"  pipeline style issues ({len(issues)}):")
            for i in issues:
                print(
                    f"    [{i.get('category')}/{i.get('severity')}] "
                    f"{i.get('description')}"
                )

        # Reconstruct generic score from pipeline style issues if present
        # Official score comes from Style Analyst inside run_review — pipeline
        # issues are post-QA. Prefer checkpoint issues + recompute from them
        # ONLY as diagnostic of what survived; also show if we can get raw.
        gkey = f"{cid}/generic" if False else None

    print("\nControl checkpoint (generic keys):")
    for k, rec in sorted(ctrl_ckpt.items()):
        if "/generic" not in k and not k.endswith("/generic"):
            # control keys look like control_max_in_style/in? check
            pass
        r = rec["result"]
        print(
            f"  {k}: style_score={r.get('style_score')} "
            f"n_style={r.get('n_style_findings')}"
        )
        style_issues = [i for i in (rec.get("issues") or []) if i.get("type") == "style"]
        if style_issues:
            # Recompute what score WOULD be if these were Style Analyst findings
            findings = [
                StyleFinding(
                    category=i.get("category") or "",
                    severity=i.get("severity") or "medium",
                    description=i.get("description") or "",
                )
                for i in style_issues
            ]
            # NOTE: official style_score is from Style Analyst BEFORE QA;
            # pipeline issues may differ. Show both.
            print(f"    pipeline-style recomputed score (diagnostic only)="
                  f"{compute_style_score_from_findings(findings)}")
            for f in findings:
                sev = (f.severity or "medium").lower()
                pen = SEVERITY_PENALTY.get(sev, 12.0)
                print(f"    - [{f.category}/{f.severity}] −{pen}: {f.description[:100]}")


if __name__ == "__main__":
    main()
