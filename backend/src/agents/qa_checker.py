"""
QA Checker Agent — validates Style Analyst and Defect Hunter outputs.

Inspired by CodeAgent's QA-Checker (Tang et al., EMNLP 2024), which proved
that removing the supervisory QA step substantially reduces review effectiveness
by allowing hallucinated and off-topic findings to reach the user.

Single focused LLM call — kept lightweight so it doesn't dominate latency.
"""
from __future__ import annotations

import json
import re
import time

from dotenv import load_dotenv

from backend.src.core.models import (
    DefectHunterOutput,
    QACheckerOutput,
    StyleAnalysisOutput,
)

load_dotenv("backend/.env")


def check_quality(
    code: str,
    style_output: StyleAnalysisOutput,
    defect_output: DefectHunterOutput,
) -> tuple[QACheckerOutput, int]:
    """
    Validate agent outputs are relevant to the submitted code.
    Filters out hallucinated or off-topic findings.
    Returns (QACheckerOutput, execution_time_ms).
    """
    start = time.time()

    # If both outputs are empty, nothing to check
    if not style_output.findings and not defect_output.bugs and not defect_output.code_smells:
        result = QACheckerOutput(
            style_relevant=True,
            defect_relevant=True,
            issues_flagged=[],
            filtered_style_findings=[],
            filtered_defect_findings=[],
        )
        return result, int((time.time() - start) * 1000)

    # Build compact summaries for the LLM
    style_summary = [
        {"cat": f.category, "desc": f.description[:100]}
        for f in style_output.findings[:10]
    ]
    defect_summary = [
        {"cat": f.category, "desc": f.description[:100]}
        for f in (defect_output.bugs + defect_output.code_smells + defect_output.security_issues)[:10]
    ]

    from groq import Groq

    client = Groq()

    system_prompt = (
        "You are a QA Checker for a code review system. Your job: verify that review findings "
        "are RELEVANT to the actual submitted code.\n\n"
        "For each finding, check:\n"
        "1. Does it reference something actually present in the code?\n"
        "2. Is it about the submitted code or something unrelated?\n"
        "3. Is it a hallucination (mentioning functions/variables that don't exist)?\n\n"
        "Return ONLY valid JSON:\n"
        "{\n"
        '  "style_relevant": true/false,\n'
        '  "defect_relevant": true/false,\n'
        '  "irrelevant_indices_style": [0, 2],\n'
        '  "irrelevant_indices_defect": [1],\n'
        '  "issues_flagged": ["reason1", "reason2"]\n'
        "}\n\n"
        "irrelevant_indices = indices of findings that should be REMOVED (0-based)."
    )

    user_prompt = (
        f"Submitted code:\n{code[:2000]}\n\n"
        f"Style findings: {json.dumps(style_summary, default=str)}\n"
        f"Defect findings: {json.dumps(defect_summary, default=str)}\n\n"
        "Check if each finding is relevant to the actual code above. Return JSON only."
    )

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.1,
            max_tokens=800,
        )
        raw = response.choices[0].message.content.strip()
        json_match = re.search(r"\{.*\}", raw, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group())
            bad_style = set(data.get("irrelevant_indices_style", []))
            bad_defect = set(data.get("irrelevant_indices_defect", []))

            filtered_style = [
                f for i, f in enumerate(style_output.findings) if i not in bad_style
            ]
            all_defects = (
                defect_output.bugs + defect_output.code_smells + defect_output.security_issues
            )
            filtered_defects = [
                f for i, f in enumerate(all_defects) if i not in bad_defect
            ]

            result = QACheckerOutput(
                style_relevant=data.get("style_relevant", True),
                defect_relevant=data.get("defect_relevant", True),
                issues_flagged=data.get("issues_flagged", []),
                filtered_style_findings=filtered_style,
                filtered_defect_findings=filtered_defects,
            )
        else:
            # Parsing failed — pass through all findings unfiltered
            all_defects = (
                defect_output.bugs + defect_output.code_smells + defect_output.security_issues
            )
            result = QACheckerOutput(
                style_relevant=True,
                defect_relevant=True,
                filtered_style_findings=style_output.findings,
                filtered_defect_findings=all_defects,
            )
    except Exception as e:
        from backend.src.core.metrics import maybe_record_groq_throttle

        maybe_record_groq_throttle(e)
        all_defects = (
            defect_output.bugs + defect_output.code_smells + defect_output.security_issues
        )
        result = QACheckerOutput(
            style_relevant=True,
            defect_relevant=True,
            filtered_style_findings=style_output.findings,
            filtered_defect_findings=all_defects,
        )

    elapsed = int((time.time() - start) * 1000)
    return result, elapsed
