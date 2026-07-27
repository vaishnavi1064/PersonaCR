# pair1 instrumentation diagnosis — evidence-backed verdict

**Date:** 2026-07-27  
**Pair:** `pair_1_merge_headers`  
**Run:** `minimal_a.py --only-pair pair_1_merge_headers --force-pair --pace 25`  
**Sidecar:** `evals/results/minimal_a_pair_1_merge_headers_evidence.json`  
**Constraint honored:** logging only; no scorer / retrieval / prompt / fingerprint changes.

---

## Part 1 — Instrumentation

`evals/minimal_a.py` now wraps the live `run_review` path and persists, per clean arm:

- retrieval neighbors (names, paths, distances, prompt-inclusion confirmation)
- raw Style Analyst findings + `style_score`
- pipeline issues (post-QA)

Stored on the checkpoint row (`evidence` field) and written to the sidecar above.

**Honesty guards:** `pytest tests/test_minimal_a_guards.py` → **6 passed**.  
(`pytest tests -m "not groq"` still has pre-existing ChatPage / fastembed / StyleAnalyst patch failures unrelated to this change.)

---

## Part 2 — pair1 re-run scores (personalized)

| Version | style_score | n_style_findings (pipeline) | similar_functions_found |
|---------|-------------|-----------------------------|-------------------------|
| IN-style | **80.0** | 3 | 8 |
| OFF-style | **80.0** | 2 | 8 |

Separation (off − in) = **0**. Prior checkpoint had IN=70 / OFF=80 (inverted); this re-run ties at 80. Either way personalized does not prefer IN.

Generic both arms: style_score **50.0** (empty FP).

### Groq cost (this re-run only)

- **4 clean arms** (personalized+generic × in+off), **0 throttled**
- Wall clock ≈ **163 s** (pace 25s; first arm cold-loaded MiniLM)
- ≈ one `run_review` per arm (`max_iterations=1` → planner + style + defect + QA)

---

## 1. Retrieval IN vs OFF (logged)

Both arms: `n_retrieved_functions=8`, `prompt_would_include_similar=true`. Stage-1 files overlap strongly (`hooks.py`, `utils.py`, `structures.py`).

**IN top-5 (distance):**

| rank | function | path | distance |
|------|----------|------|----------|
| 1 | `default_headers` | `src/requests/utils.py` | 0.423 |
| 2 | `__eq__` | `src/requests/structures.py` | 0.699 |
| 3 | `default_hooks` | `src/requests/hooks.py` | 0.706 |
| 4 | `parse_dict_header` | `src/requests/utils.py` | 0.713 |
| 5 | `copy` | `src/requests/structures.py` | 0.721 |

**OFF top-5 (distance):**

| rank | function | path | distance |
|------|----------|------|----------|
| 1 | `default_headers` | `src/requests/utils.py` | 0.432 |
| 2 | `parse_dict_header` | `src/requests/utils.py` | 0.700 |
| 3 | `prepend_scheme_if_needed` | `src/requests/utils.py` | 0.706 |
| 4 | `get_encoding_from_headers` | `src/requests/utils.py` | 0.713 |
| 5 | `resolve_proxies` | `src/requests/utils.py` | 0.717 |

**Assessment:** Neighbors are **sensible** (header/utils/structures from requests), not degenerate. IN and OFF share rank-1 `default_headers` but the rest of the top-5 **differs** — not near-identical. Retrieval supplied usable personalized context to both sides.

→ **Not (ii).**

---

## 2. Raw Style Analyst text (logged — not inferred)

### IN (`style_score=80`, 3 findings)

1. **naming / low** — *"uses 'merge_headers'… snake_case, but it does not follow the conventional naming pattern of having a docstring or type hints for the dictionary values."*  
   FP: `"snake_case with type hints and docstrings"` · submitted: `"snake_case without type hints for dictionary values and no docstring"`
2. **complexity / medium** — *"complexity… lower than the developer's average… can be simplified further."*  
   FP: `avg_complexity: 5.22`
3. **documentation / high** — *"lacks a docstring, which is not consistent with… docstring_coverage of 0.246."*  
   FP: `docstring_coverage: 0.246` · submitted: `"no docstring"`

### OFF (`style_score=80`, 3 raw findings; 2 survived QA)

1. **naming / high** — *"The function name 'mergeHeaders' does not follow the snake_case convention."*  
   FP: `snake_case` · submitted: `camelCase`
2. **documentation / medium** — *"The docstring does not include a ':rtype:' or ':return:' directive…"*  
   (OFF has a verbose Args/Returns docstring; analyst did **not** flag verbosity vs low FP docstring rate.)
3. **complexity / low** — *"can be simplified further by using the dictionary unpacking operator…"*  
   (dropped by QA; not in pipeline issues)

**What OFF was designed to violate:** camelCase, no types, verbose docstring, comprehensions.  
**What the analyst actually flagged:** camelCase ✓; missing `:rtype:` (wrong axis); did **not** flag missing type hints, excess docstring vs 0.246 coverage, or comprehensions.  
**Score:** still **80**, same as IN, despite a **high**-severity naming deviation on OFF.

→ Scorer named a real OFF deviation and still did not lower the score relative to IN. That is score/finding inconsistency, not missing retrieval.

---

## 3. Verdict

### **(iii) Genuine scorer mis-score** (primary)

Evidence:

1. Retrieval was relevant and differentiated → not an input/context vacuum.
2. Analyst **did** identify OFF camelCase as high-severity deviation.
3. `overall_style_score` remained **80** for both IN and OFF (prior run: OFF scored *higher*).
4. IN was **penalized for lacking a docstring** against a fingerprint with **docstring_coverage=0.246** — reasoning misreads rates.

Secondary notes (not alternative primary causes):

- Finding set incomplete on OFF (types / verbose docs / comprehensions under-flagged).
- QA dropped one OFF style finding; score comes from Style Analyst JSON, not finding count.

**Not (ii).** Not primarily mixed: retrieval did its job; the style_score emitter did not.

### Next fix implied (do **not** execute in this pass)

Calibrate **Style Analyst score generation** so `overall_style_score` is forced to track severity/count of named personal-pattern deviations (and so FP rates like low docstring coverage are not inverted into “must have docstring”). Retrieval is not the first lever for pair1.
