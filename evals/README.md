# PersonaCR Defect Hunter — Eval Harness

A test-set-based eval + prompt regression harness for the Defect Hunter agent.
Calls `hunt_defects()` directly, so it needs only `GROQ_API_KEY` — no Supabase,
no fingerprint, no orchestrator.

## Files
- `test_set.json` — labeled snippets with known defects (you fill this in)
- `run_eval.py` — runs the set, prints + saves catch-rate and false-positive rate
- `compare_runs.py` — compares two runs to catch prompt regressions
- `results/` — saved run summaries (created automatically)

## Setup
1. Drop the `evals/` folder at the PersonaCR repo root (same level as `backend/`).
2. Make sure `GROQ_API_KEY` is set: `export GROQ_API_KEY=gsk_...`
3. Confirm the import path works. From repo root:
   `python -c "from backend.src.agents.defect_hunter import hunt_defects; print('ok')"`
   If that fails, the folder layout differs — adjust the import at the top of `run_eval.py`.

## Step 1 — Build the test set (the real work)
Edit `test_set.json`. Add 15-20 cases total:
- ~12-15 snippets WITH known defects (bug / code_smell / security)
- ~2-3 CLEAN snippets (empty `expected_defects`) to measure false positives

For each defect, put 1-3 distinctive `keywords` a correct finding would contain.
Use real code — pull buggy snippets from your own past commits, Stack Overflow
bug reports, or write them. The more realistic, the more defensible in interview.

## Step 2 — Run the baseline
```
python evals/run_eval.py --version v1
```
This prints catch-rate + false-positive rate and saves `results/eval_v1.json`.
**Write down these two numbers — they are what goes on your resume.**

## Step 3 — Do a real regression test (this earns the "regression testing" claim)
1. Open `backend/src/agents/defect_hunter.py`
2. Change the `system_prompt` or `user_prompt` (e.g. make it terser, or add/remove guidance)
3. Re-run with a new version label:
   ```
   python evals/run_eval.py --version v2
   ```
4. Compare:
   ```
   python evals/compare_runs.py v1 v2
   ```
   This shows whether catch-rate went up or down, and names any case that newly
   missed a defect. If v2 is worse, you've literally caught a prompt regression —
   keep v1. If better, keep v2. Either way you now have a defensible story.

## What to bring back for the resume bullet
- Number of test cases (e.g. 18)
- Catch-rate % (from Step 2)
- False-positive rate %
- The regression you caught in Step 3 (e.g. "v2 prompt dropped catch-rate 8 points, reverted")
