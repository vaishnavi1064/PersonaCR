# PersonaCR — TEST MATRIX

**Run:** `backend\.venv\Scripts\python.exe -m pytest tests -m "not groq" -v`  
**Result (this pass):** 30 passed · 3 failed · 1 deselected (`@pytest.mark.groq`)

## Summary (what tests demonstrate)

| Status | Stages |
|--------|--------|
| **Verified-correct** | Fingerprint key rates + edge cases; Jina/Chroma nearest-neighbor + adversarial discrimination + two-stage narrowing; Planner rules path; Defect Hunter AST; Confidence evaluator (high / low cases); QA filter parsing (mocked LLM); Style Analyst JSON parsing (mocked LLM + retrieval); Orchestrator parallel gather + issue aggregation; minimal_a honesty guards (error exclusion, backoff, throttle exclusion) |
| **Broken (failing tests)** | Loop 2 destructive overwrite of first-pass findings; ChatPage review target ignores selected-repos when primary/legacy is null (WIP: `primaryRepoUrlByChatId` only; HEAD: `lastAnalyzedRepo`) |
| **Blocked** | minimal_a quantitative personalization result (Groq rate limits / call budget — harness intact, not “broken”); live Groq agent smoke (`@pytest.mark.groq`, not run in fast suite) |
| **Characterized (passes, documents weakness)** | Confidence can be `is_confident=True` at exactly 0.7 with **zero** Chroma hits if other factors fill the score |

Do not read “30 passed” as “the product works end-to-end.” The three failures are intentional bug characterizations.

---

## Matrix

| Component | What “correct” means | Test status | If failing / notes |
|-----------|----------------------|-------------|--------------------|
| **CODE_MAP / Step 0** | Map matches real paths & names | **pass** (artifact) | See `docs/CODE_MAP.md` |
| **Fingerprint rates** | Hand-counts: docstring 0.7, type hints 0.5, error handling 0.3, snake_case, length stats | **pass** | `tests/test_fingerprint.py` |
| **Fingerprint edges** | Empty / syntax-error / `ast.Constant` docstring / `match` statement | **pass** | No `ast.Str` regression on 3.14 |
| **Retrieval NN** | Query returns nearest, sorted distances, auth helpers for auth-like query | **pass** | `tests/test_retrieval.py` (slow; local Jina) |
| **Retrieval adversarial** | Matching query closer / more on-corpus than unlike UI-style query | **pass** | RAG not collapsed |
| **Two-stage retrieval** | Stage-2 function `file_path` ⊆ stage-1 file set | **pass** | Narrowing works |
| **Planner (rules)** | ≥2 fingerprint deviations → focus areas; no Groq | **pass** | |
| **Defect Hunter AST** | Bare except + mutable default caught; clean code empty | **pass** | LLM phase not required for these |
| **Defect Hunter live Groq** | Planted bugs still caught via full `hunt_defects` | **blocked** (deselected) | `@pytest.mark.groq` |
| **Style Analyst (mocked)** | Parses type_safety deviation from mocked LLM JSON | **pass** | Does not prove live personalization quality |
| **QA Checker (mocked)** | Drops findings at mocked `irrelevant_indices_style` | **pass** | |
| **Confidence Evaluator** | High evidence → confident; zero retrieval + zero findings → not | **pass** | |
| **Confidence zero-retrieval quirk** | Zero Chroma hits + other factors → score 0.7 / confident | **pass (characterization)** | Loop 1 may skip re-plan despite weak retrieval |
| **Orchestrator parallelism** | Style+Defect wall time &lt; sequential sum; both findings present | **pass** | `asyncio.gather` path exercised |
| **Orchestrator aggregation** | No drop/dupe of style+defect issues | **pass** | First-pass only (gate passes) |
| **Loop 2 overwrite** | First-pass findings preserved if re-review empty | **fail** | `all_issues = []` then rebuild in `orchestrator.py` ~L340; returned `issues=[]` |
| **ChatPage repo selection** | Selected repos ⇒ review target resolves (fallback to `selected[0]`) | **fail** | WIP: `reviewTarget = primaryRepoUrlByChatId[cid]` only (~L348); Q&A uses `selectedRepoUrls`. HEAD bug was `lastAnalyzedRepo` vs selection |
| **minimal_a honesty** | `category=error` excluded; backoff 5/15/45/90; throttled excluded from means | **pass** | Regression guard for flat-1.0 corruption |
| **minimal_a quantitative result** | Personalized vs generic style separation landed in JSON | **blocked** | Needs batching / overnight chunking / higher Groq budget — not a harness bug |

---

## Known bugs (characterized, not fixed)

### 4a. Loop 2 destructive overwrite
- **Where:** `backend/src/agents/orchestrator.py` — Loop 2 block assigns `all_issues = []` (~L340) and overwrites `style_output` / `defect_output` / `qa_output` (~L294–321).
- **Test:** `tests/test_loop2_overwrite.py::test_loop2_preserves_first_pass_findings_when_rereview_empty` → **FAIL** (`issues=[]`).

### 4b. ChatPage repo-selection divergence
- **HEAD:** review gated on `lastAnalyzedRepo`; UI selection is `selectedRepoUrls`.
- **WIP disk:** review gated on `primaryRepoUrlByChatId`; Q&A on `selectedRepoUrls`; no fallback when primary is null and selection is non-empty.
- **Tests:** `tests/test_chatpage_repo_selection.py` → **FAIL** (2 assertions).

---

## minimal_a — recommendation (not a code change)

Harness honesty guards are intact. To land a quantitative result:
1. Run overnight with higher inter-call sleep and/or smaller pair batches.
2. Cap concurrent Groq calls (already serial per arm; keep `max_iterations=1`).
3. Resume from partial `evals/results/minimal_a.json` if interrupted (not implemented — would be a harness enhancement later).
4. Do not treat throttle/`category=error` rows as real findings (guards already enforce this).

---

## How to run

```bash
# Fast / CI (no Groq)
backend\.venv\Scripts\python.exe -m pytest tests -m "not groq" -v

# Include live Groq smoke
backend\.venv\Scripts\python.exe -m pytest tests -v

# Skip slow embedding tests
backend\.venv\Scripts\python.exe -m pytest tests -m "not groq and not slow" -v
```

Artifacts: `docs/CODE_MAP.md`, `tests/`, `docs/TEST_MATRIX.md`, `pytest.ini`.
