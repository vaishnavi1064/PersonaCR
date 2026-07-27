# Minimal-A Result — after Style Analyst Defect A/B fix

**Generated:** 2026-07-27T22:24:00Z  
**Target N (paired-clean):** 6  
**Achieved N:** 6  
**Status:** TARGET MET — reportable (directional / preliminary only)  
**Primary metric:** `style_score` = Style Analyst `overall_style_score` (0–100). Separation = off − in (more negative ⇒ OFF more deviant).

pair1 pre-fix diagnosis is preserved at `evals/minimal_a_pair1_diagnosis.md` (do not treat this file as erasing that record).

---

## Trace notes — roots of Defects A & B (read from code)

### Defect A — score ignored findings

In `backend/src/agents/style_analyst.py` (pre-fix), `overall_style_score` was taken **verbatim** from the LLM JSON field:

```python
score = float(data.get("overall_style_score", 50))
```

Findings were parsed separately and never used to compute or bound the score. That is why OFF could emit a HIGH-severity `mergeHeaders` finding and still return `style_score=80`.

### Defect B — fingerprint direction inverted

Findings were produced only by the LLM against a dumped fingerprint + similar snippets. The prompt said “deviations from personal patterns” but **did not** encode rate-feature direction. Frequency fields available at scoring time included (among others):

| Fingerprint field | requests value | meaning |
|-------------------|---------------:|---------|
| `docstring_coverage` | 0.246 | rare — missing docs is normal |
| `type_hint_usage` | 0.993 | common — missing hints is a deviation |
| `error_handling_rate` | 0.131 | rare |
| `comprehension_ratio` | 0.016 | rare |
| `comment_density` | 0.145 | rare |
| `naming_convention` | snake_case | categorical |

The model applied a generic “docstrings are good” prior and flagged missing docstrings on IN samples against 0.246 coverage. No code path consulted rarity vs commonness before accepting a finding.

---

## Severity-weight mapping (set once, before re-measure)

**Defect A mapping** (deterministic; LLM `overall_style_score` ignored):

| Severity | Penalty |
|----------|--------:|
| high | **25** |
| medium | **12** |
| low | **5** |

`score = max(0, 100 − Σ penalties)` over findings with `category != "error"`.

**Principle (not tuned to a target number):** one HIGH personal-pattern break costs a quarter of the scale; MEDIUM ≈ half of HIGH; LOW is a small ding. Penalties stack. Invariant: more / severer named deviations ⇒ strictly lower score.

**Defect B thresholds:** rate ≤ **0.35** = rare (drop under-use / “missing X” findings); rate ≥ **0.65** = common (drop over-use / “has X” praise-as-deviation). Applied generally across rate features (`docstring_coverage`, `type_hint_usage`, `error_handling_rate`, `comprehension_ratio`, `comment_density`), plus prompt direction guidance. Not a docstring special-case.

Weights were **not** adjusted after seeing control or N=6 results.

---

## Control re-run (fixed scorer) — FIRST gate

Command: `minimal_a_control.py --force --pace 25`  
Groq: ~4 arms + 2 Style Analyst probes; wall ≈ **195 s**; 0 throttled.

| Arm | MAX-IN style_score | MAX-OFF style_score | sep (off−in) |
|-----|-------------------:|--------------------:|-------------:|
| **Personalized** | **95.0** | **63.0** | **−32.0** |
| Generic | 100.0 | 51.0 | −49.0 |

**Before fix (prior control):** personalized IN=80 / OFF=60 / sep=**−20**.  
**After fix:** sep=**−32** — still separates correctly, **more cleanly** on the personalized arm. Control did **not** break → proceed to N=6.

Residual: MAX-IN can still emit “consistent with…” non-deviations as findings (Bug2-ish); QA may drop some OFF type_safety findings from the pipeline count while style_score still reflects Style Analyst findings.

---

## N=6 re-measure

### How scores were obtained

| Pairs | Method | Groq |
|-------|--------|------|
| pair1 | Re-scored from stored evidence (`rescore_minimal_a_from_evidence.py`): direction filter + severity-weighted score | **0** |
| pair2, pair3 | Full arm re-run under fixed scorer (`--force-pair`) | **8 arms**, wall ≈ **261 s**, 0 throttled |

### Primary — style_score separation

| Arm | Avg IN | Avg OFF | Separation (off − in) | n_in | n_off |
|-----|-------:|--------:|----------------------:|-----:|------:|
| **Personalized** | **91.0** | **44.667** | **−46.333** | 3 | 3 |
| Generic | 92.667 | 92.667 | **0.0** | 3 | 3 |

### Before → after (same N=6 pairs, prior report)

| Arm | Prev sep | New sep |
|-----|---------:|--------:|
| Personalized | −17.333 | **−46.333** |
| Generic | −50.0 | **0.0** |

Generic sep collapsing to ~0 is expected under the fixed scorer: with `fingerprint={}`, there are no personal rates to deviate from, so findings (and thus the derived score) no longer invent a large IN/OFF gap. Personalized separation is now the meaningful comparison.

### Per-pair personalized style_score

| Pair | IN | OFF | sep (off−in) |
|------|---:|----:|-------------:|
| pair_1_merge_headers | 88.0 | 58.0 | **−30.0** |
| pair_2_build_url | 95.0 | 38.0 | −57.0 |
| pair_3_parse_status | 90.0 | 38.0 | −52.0 |

### pair1 before / after (explicit)

| | IN | OFF | note |
|--|---:|----:|------|
| Original clean run (pre-instrumentation) | 70 | 80 | inverted |
| Instrumented re-run (pre-fix) | 80 | 80 | tied; verdict (iii) |
| **After Defect A/B fix (evidence rescore)** | **88** | **58** | **inversion resolved** |

Evidence rescore detail: IN findings 3→1 (dropped inverted “missing docstring” / bundled docstring-under-use); OFF kept HIGH camelCase (+ other findings) → 100−25−12−5=58.

### Per-case Δ style_score (personalized − generic)

| Case | p | g | Δ (p−g) |
|------|--:|--:|-------:|
| pair_1_merge_headers/in_style | 88 | 78 | +10 |
| pair_1_merge_headers/off_style | 58 | 78 | −20 |
| pair_2_build_url/in_style | 95 | 100 | −5 |
| pair_2_build_url/off_style | 38 | 100 | −62 |
| pair_3_parse_status/in_style | 90 | 100 | −10 |
| pair_3_parse_status/off_style | 38 | 100 | −62 |

---

## Honest verdict

**N=6 is small → directional / preliminary, not statistically significant.**

Under the fixed scorer on this hand-authored requests pair set:

- Personalized separation (**−46.3**) is **larger** than generic (**0.0**).
- pair1’s IN↔OFF inversion is **gone** (88 vs 58).
- Control still separates and is cleaner than before (−32 vs −20).

**Caveats held firm:**

1. This improvement **followed a demonstrated bug fix** (Defects A & B). It is **not** a fresh independent confirmation of personalization on a clean metric.
2. The fix is justified because it corrects score↔findings causality and fingerprint direction — **not** because the headline number improved.
3. Generic’s previous large separation (−50) was partly an artifact of a free LLM scalar with an empty fingerprint; under findings-derived scoring it no longer fabricates that gap.
4. Do not claim production readiness or significance from N=6.

**Bottom line (preliminary):** after correcting A & B, personalized style_score separates IN vs OFF on this set and does so more than the generic arm. Treat as directional evidence post-fix, not vindication.

---

## Groq cost (this pass)

| Step | Cost |
|------|------|
| Control force re-run | ~4 `run_review` + 2 Style Analyst probes; ≈195 s wall; 0 throttled |
| pair1 | **0** (evidence rescore) |
| pair2 + pair3 force | **8** clean arms; ≈261 s wall; 0 throttled |

## Checkpoint / artifacts

- Scorer: `backend/src/agents/style_analyst.py`
- Evidence rescore log: `evals/results/minimal_a_rescore_from_evidence.json`
- Control: `evals/minimal_a_control.md`, `evals/results/minimal_a_control_raw.json`
- Main checkpoint: `evals/minimal_a_checkpoint.jsonl`
- pair1 bug record (preserved): `evals/minimal_a_pair1_diagnosis.md`

---

## Shared-scale metric (feature-distance) — APPEND

**Generated:** 2026-07-27T22:53:00Z (re-emit after applying production Defect B filter to stored personalized findings)  
**Framing:** (a) — personalized review track of objective feature-distance (see `shared_scale_framing.md`).  
**Primary shared metric:** `feature_distance(code, fingerprint)` via `pattern_extractor.extract_fingerprint` on one CodeChunk.  
**Findings-based style_score:** diagnostic only (not used for this verdict).  
**Groq cost this pass:** **0** (fixtures + stored evidence; personalized findings re-filtered with `filter_findings_by_fingerprint_direction` to match post-fix production — no new LLM calls).

### Frozen weights (locked before re-measure)

| Feature | Weight |
|---------|-------:|
| `type_hint_usage` | 0.20 |
| `naming_convention` | 0.20 |
| `docstring_coverage` | 0.20 |
| `error_handling_rate` | 0.20 |
| `comprehension_ratio` | 0.20 |

Material deviation threshold: **0.35**. Weights were **not** adjusted after seeing results.

### Control FIRST (arm-independent distance gate)

| Fixture | feature_distance | feature_match_score |
|---------|-----------------:|--------------------:|
| MAX-IN | 0.08 | 92.0 |
| MAX-OFF | 0.92 | 8.0 |

sep (off − in distance) = **0.84**  
Gate MAX-IN < MAX-OFF: **True**

### N=6 — per-pair feature-distance

| Pair | IN dist | OFF dist | sep (off−in) | OFF farther? |
|------|--------:|---------:|-------------:|:------------:|
| pair_1_merge_headers | 0.08 | 0.7724 | 0.6924 | yes |
| pair_2_build_url | 0.08 | 0.7264 | 0.6464 | yes |
| pair_3_parse_status | 0.08 | 0.7264 | 0.6464 | yes |

Avg IN dist **0.08**, avg OFF dist **0.7417**, sep **0.6617** (3/3 pairs OFF farther).

Shared scale itself separates IN/OFF cleanly and identically for both arms (code-only). Arm comparison is framing-(a) tracking below — not findings-derived `style_score`.

### Framing (a) — review tracking of material deviations

Pooled recall of material feature deviations in Style Analyst findings (stored evidence; same mention rules both arms; personalized = post–Defect B filtered):

| Arm | OFF pooled recall | IN false-alarm rate (dims/case) |
|-----|------------------:|--------------------------------:|
| personalized | 0.6667 | 0.0 |
| generic | 0.1667 | 0.6667 |

**Reason:** personalized OFF material-recall 0.6667 > generic 0.1667; IN false-alarm rate 0.00 <= generic 0.67

Note: without applying the production direction filter to stored personalized raw findings, pair1 IN still carried inverted docstring/naming nits → IN FP-rate 1.0 and a mixed/inconclusive read. That pre-filter artifact is **not** the post-fix system; weights were not changed to obtain the yes.

### One-line verdict

**On a fair scale, does personalization separate in/off better than generic: yes.**

Caveat: N=6 is small / directional. Shared feature-distance validates the fixtures; the arm win is on **tracking recall of true OFF deviations**, not on the circular findings-score (personalized −46 vs generic 0). A fair null would have been accepted.

Artifacts: `evals/results/shared_scale_metric.json`, `evals/shared_scale_framing.md`, `evals/shared_scale_metric.py`.
