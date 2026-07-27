"""
Diagnostic script for Minimal-A
"""
from __future__ import annotations

import asyncio
import io
import json
import os
import sys
from pathlib import Path

# Ensure repo root is on path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
else:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# Intercept Groq calls before importing anything else
import groq
captured_calls = []

class InterceptedGroq(groq.Groq):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        orig_create = self.chat.completions.create
        
        def wrapped_create(*args, **kwargs):
            res = orig_create(*args, **kwargs)
            messages = kwargs.get("messages", [])
            system_content = ""
            user_content = ""
            for m in messages:
                if m.get("role") == "system":
                    system_content = m.get("content", "")
                elif m.get("role") == "user":
                    user_content = m.get("content", "")
            
            captured_calls.append({
                "model": kwargs.get("model"),
                "system": system_content,
                "user": user_content,
                "raw_response": res.choices[0].message.content
            })
            return res
            
        self.chat.completions.create = wrapped_create

groq.Groq = InterceptedGroq

# Now import orchestrator and embedder
from backend.src.agents.orchestrator import run_review
from backend.src.core.embedder import query_similar_staged

HERE = Path(__file__).parent
PAIRS_PATH = HERE / "minimal_a_pairs.json"
FP_PATH = HERE / "results" / "minimal_a_fingerprint.json"

async def main():
    if not os.environ.get("GROQ_API_KEY"):
        print("ERROR: GROQ_API_KEY environment variable not set.")
        sys.exit(1)
        
    fp_data = json.loads(FP_PATH.read_text())
    fingerprint = fp_data["fingerprint"]
    user_id = fp_data["user_id"]
    repo_name = fp_data["repo_name"]
    pairs_data = json.loads(PAIRS_PATH.read_text())
    pair = pairs_data["pairs"][0] # First pair
    
    results = {}
    
    for version_key in ["off_style", "in_style"]:
        code = pair[version_key]
        print(f"\n======================================================================")
        print(f"DIAGNOSING VERSION: {version_key.upper()}")
        print(f"======================================================================")
        
        # 1. Capture retrieval directly
        staged = query_similar_staged(
            code=code,
            user_id=user_id,
            repo_name=repo_name,
            n_files=3,
            n_functions=8,
            language_filter="python",
        )
        funcs = staged.get("functions", [])
        print(f"STAGE 2 RETRIEVED FUNCTIONS COUNT: {len(funcs)}")
        for idx, f in enumerate(funcs):
            meta = f.get("metadata", {})
            print(f"  [{idx+1}] Function: {meta.get('function_name')} in {meta.get('file_path')}")
            # print first 2 lines
            src_lines = f.get("source", "").splitlines()[:2]
            print(f"      Code snippet: {' / '.join(src_lines)}")
            
        # Clear captured calls before running
        captured_calls.clear()
        
        # Run the full review code path (personalized arm)
        print("\nRunning run_review...")
        review_result = await run_review(
            code=code,
            language="python",
            fingerprint=fingerprint,
            user_id=user_id,
            repo_name=repo_name,
            max_iterations=1 # Only do 1 iteration for deterministic tracing
        )
        
        # Now find Style Analyst and QA Checker calls in captured_calls
        style_call = None
        qa_call = None
        for call in captured_calls:
            if "Style Analyst" in call["system"]:
                style_call = call
            elif "QA Checker" in call["system"]:
                qa_call = call
                
        if not style_call:
            print("ERROR: Did not find Style Analyst call in intercepted Groq calls!")
            continue
            
        print("\n--- STYLE ANALYST SYSTEM PROMPT ---")
        print(style_call["system"])
        
        print("\n--- STYLE ANALYST USER PROMPT ---")
        print(style_call["user"])
        
        print("\n--- RAW STYLE ANALYST LLM RESPONSE ---")
        print(style_call["raw_response"])
        
        # Parse the raw response
        import re
        json_match = re.search(r"\{.*\}", style_call["raw_response"], re.DOTALL)
        parsed_style = {}
        if json_match:
            try:
                parsed_style = json.loads(json_match.group())
            except Exception as e:
                print(f"Parsing Style Analyst JSON failed: {e}")
        
        print("\n--- PARSED STYLE ANALYST RESPONSE ---")
        print(json.dumps(parsed_style, indent=2))
        
        # Parse QA Checker if present
        parsed_qa = {}
        if qa_call:
            print("\n--- QA CHECKER USER PROMPT ---")
            print(qa_call["user"])
            print("\n--- RAW QA CHECKER RESPONSE ---")
            print(qa_call["raw_response"])
            qa_json_match = re.search(r"\{.*\}", qa_call["raw_response"], re.DOTALL)
            if qa_json_match:
                try:
                    parsed_qa = json.loads(qa_json_match.group())
                except Exception as e:
                    print(f"Parsing QA Checker JSON failed: {e}")
            print("\n--- PARSED QA CHECKER RESPONSE ---")
            print(json.dumps(parsed_qa, indent=2))
            
        # Findings count derivation
        style_findings = review_result.issues
        style_issues = [issue for issue in style_findings if issue.get("type") == "style"]
        print(f"\n--- DERIVED STYLE FINDINGS COUNT ---")
        print(f"Final style findings count (type == 'style'): {len(style_issues)}")
        print(f"Field counted: review_result.issues where type == 'style'")
        print(f"Values:")
        for idx, issue in enumerate(style_issues):
            print(f"  [{idx}] {json.dumps(issue)}")
            
        results[version_key] = {
            "retrieved_count": len(funcs),
            "prompt_length": len(style_call["user"]),
            "raw_response_length": len(style_call["raw_response"]),
            "findings_count": len(style_issues),
            "parsed_style": parsed_style,
            "parsed_qa": parsed_qa,
            "raw_response": style_call["raw_response"]
        }

    # Print side-by-side comparison
    print("\n======================================================================")
    print("SIDE-BY-SIDE COMPARISON (PAIR #1)")
    print("======================================================================")
    print(f"{'Metric':<30} {'In-Style':<20} {'Off-Style':<20}")
    print(f"{'-'*30} {'-'*20} {'-'*20}")
    print(f"{'Retrieved function count':<30} {results['in_style']['retrieved_count']:<20} {results['off_style']['retrieved_count']:<20}")
    print(f"{'Prompt length (chars)':<30} {results['in_style']['prompt_length']:<20} {results['off_style']['prompt_length']:<20}")
    print(f"{'Raw response length (chars)':<30} {results['in_style']['raw_response_length']:<20} {results['off_style']['raw_response_length']:<20}")
    print(f"{'Derived findings count':<30} {results['in_style']['findings_count']:<20} {results['off_style']['findings_count']:<20}")
    print(f"======================================================================")

if __name__ == "__main__":
    asyncio.run(main())
