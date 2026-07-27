# PersonaCR — Code Map (verification)

Accurate map of entry points used by the verification suite. Paths are relative to repo root.

---

## 1. Fingerprint (30 features)

| What | Where |
|------|--------|
| Entry | `backend/src/core/pattern_extractor.py` → `extract_fingerprint(chunks)` (L300–484) |
| Route call | `backend/src/routes/analyze_routes.py` → `analyze_repo` calls `extract_fingerprint` |
| Schema | `backend/src/core/models.py` → `FingerprintData` (L11–49) |
| CodeChunk type | `backend/src/core/github_ingestor.py` → `@dataclass CodeChunk` (L31–41) |

**AST helpers:** `_has_docstring` (L24–39, uses `ast.Constant`), `_has_type_hints` (L42–54), `_comprehension_ratio` (L182–202).

**Regex / non-AST:** `_has_error_handling` (L57–59), `_detect_naming_convention` (L62–72), `_estimate_complexity` (L75–83), `_detect_patterns` (L86–99), `_comment_stats`, `_conditional_stats`, `_loop_stats`, `_indentation_stats`, `_line_length_stats`, `_import_stats`, `_gini_coefficient`.

**30 return keys (L443–484):** `avg_function_length`, `max_function_length`, `docstring_coverage`, `naming_convention`, `error_handling_rate`, `type_hint_usage`, `avg_complexity`, `common_patterns`, `pattern_frequency`, `languages`, `language_distribution`, `total_functions`, `comment_density`, `inline_comment_ratio`, `comment_to_code_ratio`, `conditional_density`, `conditionals_per_100_lines`, `loop_density`, `for_to_while_ratio`, `comprehension_ratio`, `change_concentration_gini`, `indentation_consistency`, `primary_indent_depth`, `avg_line_length`, `max_line_length`, `std_line_length`, `lines_over_80`, `lines_over_120`, `import_density`, `wildcard_import_ratio`.

File-level chunks (`__file__`, `__file_summary__`) are skipped for per-function metrics.

---

## 2. Embeddings + ChromaDB

| What | Where |
|------|--------|
| Model | `backend/src/core/embedder.py` → `MODEL_NAME = "jinaai/jina-embeddings-v2-base-code"` (L26); `_get_model()` via `fastembed.TextEmbedding` (L33–39) |
| Persist dir | `CHROMA_DIR` → `backend/.chroma` (L25); `_get_client()` `PersistentClient` (L42–50) |
| Write | `embed_and_store` (L94–155) — delete/recreate collection, batch embed, `collection.add` |
| Collection name | `_collection_name` (L53–58) → `pcr-{safe_repo}-{md5[:16]}` |
| Flat query | `query_similar` (L158–213) — unused by Style Analyst |
| Two-stage | `query_similar_staged` (L216–319) |
| Delete | `delete_collection`, `delete_guest_collections` |

**Two-stage narrowing:** Stage 1 queries `granularity=="file"` → `top_file_paths`. Stage 2 queries `granularity=="function"` **and** `file_path $in top_file_paths` (L291–317). Caller: `style_analyst.analyze_style` (L41–50).

File-level chunks produced by `github_ingestor._create_file_level_chunk` (`function_name="__file_summary__"`, `granularity="file"`).

---

## 3. Agents (6) + orchestrator

| Agent | File | Entry | LLM? |
|-------|------|-------|------|
| Planner | `backend/src/agents/planner.py` | `plan_review` (L76); fast path `_rules_based_plan` (L22–73) | Hybrid |
| Style Analyst | `backend/src/agents/style_analyst.py` | `analyze_style` (L25–154) | Yes (+ Chroma) |
| Defect Hunter | `backend/src/agents/defect_hunter.py` | `hunt_defects` (L114–202); AST `_ast_analysis` (L25–111) | Yes (+ AST) |
| QA Checker | `backend/src/agents/qa_checker.py` | `check_quality` (L29–148) | Yes |
| Confidence Evaluator | `backend/src/agents/confidence_evaluator.py` | `evaluate_confidence` (L26–103); `is_confident = score >= 0.7` (L90) | No |
| Orchestrator | `backend/src/agents/orchestrator.py` | `run_review` (L49–416); `review_code_sync` (L419–427) | No |

**Parallel call:** `orchestrator.py` L93–106 (first pass) and L289–296 (Loop 2):
`asyncio.gather(style_future, defect_future)` via `_run_in_executor`.

---

## 4. Agentic loops

### Loop 1 — confidence re-plan
- `while iteration < max_iterations` (orchestrator L78–181)
- After QA + confidence: break if `conf_output.is_confident or iteration >= max_iterations` (L179–180)
- Threshold defined in `confidence_evaluator.py` L90 (`>= 0.7`)
- **Gap:** docstring claims Planner receives `ConfidenceOutput.suggestion`; no code injects `suggestion` into the next `plan_review` call

### Loop 2 — quality-gate re-review
- After Layer 3: `if gate_result.should_re_review and iteration < max_iterations` (L255)
- Gate: `backend/src/evaluation/quality_gate.py` → `evaluate_quality` (`should_re_review=not passed`)
- Re-runs plan → gather(style,defect) → QA → confidence → **rebuilds `all_issues = []`** (L340–351) → re-runs Layer 3

### Loop 2 destructive overwrite (known bug)
First-pass `all_issues` built at L184–203. On re-review, L340 assigns `all_issues = []` then rebuilds from the *new* QA only. `style_output` / `defect_output` / `qa_output` are also overwritten (L294–321). Final return uses overwritten vars (L383–416). **No snapshot/merge/rollback** if re-review is worse or empty.

---

## 5. Evaluation stack (CRScore-style)

| Component | File | Entry |
|-----------|------|-------|
| Pseudo-refs | `backend/src/evaluation/pseudo_ref_gen.py` | `generate_pseudo_references` (L178); `_ast_pseudo_refs`, `_llm_pseudo_refs` |
| STS | `backend/src/evaluation/sts_scorer.py` | `compute_sts_scores` (L47); model `all-MiniLM-L6-v2` |
| Quality gate | `backend/src/evaluation/quality_gate.py` | `evaluate_quality` (L22); thresholds comp≥0.4, conc≥0.3, rel≥0.35 |

Startup warmup of MiniLM: `backend/src/main.py` → `warmup_models` (L75–85).

---

## 6. Supabase SHA fingerprint cache

| What | Where |
|------|--------|
| Get + stale check | `backend/src/core/cache_manager.py` → `get_cached_fingerprint` (L30–65) |
| SHA fetch | `_get_latest_sha` (L16–27) via PyGithub |
| Save | `save_fingerprint` (L68–111) upsert by `repo_url` |
| DB client | `backend/src/db/supabase_rest.py` → `SupabaseREST` |

Stale when `existing["last_commit_sha"] != latest_sha` → `_cache_status: "stale"`.

---

## 7. `evals/` (esp. minimal-A)

| File | Role |
|------|------|
| `evals/minimal_a.py` | Two-arm personalization harness |
| `evals/minimal_a_setup.py` | Fingerprint + Chroma setup for requests |
| `evals/minimal_a_pairs.json` | In-style / off-style pairs |
| `evals/run_eval.py` | Defect Hunter catch-rate harness |
| `evals/compare_runs.py` | Prompt regression compare |
| `evals/benchmark_personalization.py` | Broader personalization benchmark |
| `evals/diagnose_minimal_a.py` | Diagnostics |

**Honesty guards in `minimal_a.py`:**
- `_count_style_findings` (L74–79): counts `type=="style"` and **excludes** `category=="error"`
- `_run_arm` (L109–112): any `category=="error"` → retry as throttle
- `BACKOFF_SLEEPS = (5, 15, 45, 90)` (L54); applied L138–141
- `_aggregate` (L220–276): throttled cases excluded from averages

---

## 8. Frontend repo-selection bug

### Committed HEAD (`lastAnalyzedRepo`)
- Competing fields: `useStore.lastAnalyzedRepo` vs `selectedRepoUrls` / `selectedRepoUrlsByChatId`
- Review gated on `if (!lastAnalyzedRepo)` then `reviewCode(lastAnalyzedRepo, …)`
- Q&A gated on `selectedRepoUrls.length === 0` then `chatWithInsights(…, selectedRepoUrls, …)`
- Selecting chips never updates `lastAnalyzedRepo` → false “analyze a repo first”

### Working tree (current disk — partial change, not verification of a fix)
- `lastAnalyzedRepo` removed from store
- Review target: `primaryRepoUrlByChatId[cid]` (`ChatPage.tsx` ~L348–355)
- Q&A still: `selectedRepoUrls` (~L374–380)
- `handleSelectionChange` updates selected only; primary set only via `RepoSelector.toggleRepo` when first selected, or `handlePrimaryChange`
- Remaining divergence: **selected repos non-empty + `primary_repo_url` null** (e..g. restored chats) → Q&A works, review blocked with “Select a repo…”

`RepoSelector.tsx` never references `lastAnalyzedRepo`; wires `selectedUrls` + `primaryUrl` only.
