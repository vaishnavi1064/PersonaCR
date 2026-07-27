"""
Re-score minimal_a checkpoint arms that have stored Style Analyst evidence.

Applies Defect A/B fixes without Groq:
  - filter_findings_by_fingerprint_direction
  - compute_style_score_from_findings

Appends new clean rows (load_checkpoint last-wins). Arms without evidence are
listed so the caller can force-rerun them with Groq.

Run from repo root:
    backend\\.venv\\Scripts\\python.exe evals\\rescore_minimal_a_from_evidence.py
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.src.agents.style_analyst import (
    compute_style_score_from_findings,
    filter_findings_by_fingerprint_direction,
)
from backend.src.core.models import StyleFinding
from evals.minimal_a import (
    CHECKPOINT,
    FP_PATH,
    RESULTS_DIR,
    append_checkpoint,
    load_checkpoint,
)

OUT = RESULTS_DIR / "minimal_a_rescore_from_evidence.json"


def _to_findings(raw: list[dict]) -> list[StyleFinding]:
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


def main() -> None:
    fp = json.loads(FP_PATH.read_text(encoding="utf-8"))["fingerprint"]
    ckpt = load_checkpoint(CHECKPOINT)

    rescored: list[dict] = []
    missing_evidence: list[str] = []

    for key, rec in sorted(ckpt.items()):
        evidence = rec.get("evidence") or {}
        sa = evidence.get("style_analyst") or {}
        raw = sa.get("raw_findings")
        if raw is None:
            missing_evidence.append(key)
            continue

        # Personalized arms use the requests fingerprint; generic uses {}.
        arm_fp = fp if rec.get("arm") == "personalized" else {}
        findings = _to_findings(raw)
        filtered = filter_findings_by_fingerprint_direction(findings, arm_fp)
        new_score = compute_style_score_from_findings(filtered)
        old_score = (rec.get("result") or {}).get("style_score")

        new_result = dict(rec["result"])
        new_result["style_score"] = new_score
        new_result["rescored_from_evidence"] = True
        new_result["style_score_before_rescore"] = old_score

        new_evidence = dict(evidence)
        new_sa = dict(sa)
        new_sa["style_score"] = new_score
        new_sa["style_score_before_rescore"] = old_score
        new_sa["raw_findings"] = [
            {
                "category": f.category,
                "severity": f.severity,
                "description": f.description,
                "fingerprint_value": f.fingerprint_value,
                "submitted_value": f.submitted_value,
            }
            for f in filtered
        ]
        new_sa["n_raw_findings_ex_error"] = sum(
            1 for f in filtered if f.category != "error"
        )
        new_sa["n_raw_findings_total"] = len(filtered)
        new_sa["findings_dropped_by_direction"] = len(findings) - len(filtered)
        new_evidence["style_analyst"] = new_sa
        new_evidence["note"] = (
            "Re-scored from stored evidence with Defect A/B fixes "
            "(direction filter + severity-weighted score). No Groq call."
        )

        new_rec = {
            "key": key,
            "pair_id": rec.get("pair_id"),
            "version": rec.get("version"),
            "arm": rec.get("arm"),
            "task": rec.get("task"),
            "violations": rec.get("violations"),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "result": new_result,
            "evidence": new_evidence,
            "rescored_from_evidence": True,
        }
        append_checkpoint(new_rec)
        rescored.append(
            {
                "key": key,
                "old_style_score": old_score,
                "new_style_score": new_score,
                "n_findings_before": len(findings),
                "n_findings_after": len(filtered),
                "dropped": len(findings) - len(filtered),
            }
        )
        print(
            f"  {key}: {old_score} → {new_score} "
            f"(findings {len(findings)}→{len(filtered)})"
        )

    payload = {
        "written_at": datetime.now(timezone.utc).isoformat(),
        "severity_penalty": {"high": 25.0, "medium": 12.0, "low": 5.0},
        "rescored": rescored,
        "missing_evidence_need_groq": missing_evidence,
    }
    RESULTS_DIR.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"\nRescored {len(rescored)} arms → {OUT}")
    print(f"Need Groq re-run ({len(missing_evidence)} arms):")
    for k in missing_evidence:
        print(f"  - {k}")


if __name__ == "__main__":
    main()
