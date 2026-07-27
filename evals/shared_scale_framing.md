# Shared-scale metric — framing decision (frozen before re-measure)

**Date:** 2026-07-27  
**Agent:** AGENT 1 (evals only)  
**Status:** Framing + weights locked **before** control / N=6 re-measure. No post-hoc weight tuning.

---

## Choice: **(a)**

**Question:** Does the personalized *review* track objective feature-distance (code vs fingerprint) better than the generic review?

### Why (a) over (b)

| | (a) review tracks feature-distance | (b) report distance + mention check |
|--|-------------------------------------|-------------------------------------|
| Tests | Real thesis: personalization of the **review** | Mostly the fingerprint extractor |
| Harder? | Yes — LLM must surface true deviations | No — distance is arm-independent |
| Fair scale | Distance is identical for both arms; arm gap is tracking quality | Distance alone cannot prefer either arm |

**(b)** is a useful diagnostic of the extractor (control still needs it) but does not answer whether personalization helps the review. After the circular findings-score collapse (generic sep 0.0 because empty-FP arms emit no personal-pattern findings), we need a scale **neither arm can game** — then ask whether personalized findings/scores **align** with that scale better than generic.

**Trade-off accepted:** (a) can still return a fair null (personalized no better than generic on tracking). That beats a rigged win from findings-derived `style_score`. Findings-based `style_score` remains **diagnostic only**.

### How arm comparison works under (a)

1. **Shared objective:** `feature_distance(code, fingerprint)` — same formula, same FP, both arms.  
2. **Control:** MAX-IN ≪ MAX-OFF on distance (validates the scale itself).  
3. **N=6:** per-case distances; IN should be nearer FP than OFF.  
4. **Tracking:** for dimensions where code materially deviates from FP, does each arm’s Style Analyst findings **mention** that dimension as a deviation (praise/consistency notes excluded)? Personalized findings from stored evidence are passed through production `filter_findings_by_fingerprint_direction` (Defect B) so tracking measures the **fixed** system without new Groq calls. Personalized “separates better” iff it recalls true OFF deviations more than generic **and** does not invent more false IN deviations than generic (net tracking advantage).

Honesty guards and Defect A/B findings-score path are untouched.

---

## Frozen weights (set on principle — not tuned to a target)

Five Python style axes that define the PersonaCR personalization claim for this requests fixture set. **Equal weight** — no axis privileged after seeing results.

| Feature key | Weight | Distance definition (all ∈ [0, 1]) |
|-------------|-------:|-----------------------------------|
| `type_hint_usage` | **0.20** | \|code_rate − fp_rate\| |
| `naming_convention` | **0.20** | 0 if code name matches FP convention, else 1 |
| `docstring_coverage` | **0.20** | \|code_rate − fp_rate\| |
| `error_handling_rate` | **0.20** | \|code_rate − fp_rate\| |
| `comprehension_ratio` | **0.20** | \|code_rate − fp_rate\| |

- **Total weight** = 1.0  
- **feature_distance** = Σ wᵢ · dᵢ ∈ [0, 1]  
- **feature_match_score** = 100 · (1 − feature_distance) ∈ [0, 100] (higher = closer to FP)  
- **Separation** = OFF_distance − IN_distance (more positive ⇒ OFF farther from FP) — for the shared scale itself  
- **Material deviation** (for mention tracking): dᵢ ≥ **0.35** (same rarity band used elsewhere as “not mid”; frozen here as “large enough absolute gap to count as a true deviation dimension”)
- **Mention = deviation flag only:** findings whose text is praise/consistency (“consistent with…”, “follows the…”) do **not** count as mentioning a deviation dimension. Tracking measures whether the review *flags* true gaps, not whether it narrates matching features.

Code features come from `backend.src.core.pattern_extractor.extract_fingerprint` on a single `CodeChunk` wrapping the submitted snippet — **import only; no backend edits**.

---

## What we will not do

- Tune weights after control or N=6  
- Use findings-derived `style_score` as the shared primary separator for personalized vs generic  
- Overwrite `minimal_a_pair1_diagnosis.md`, `minimal_a_generic_circularity.md`, or prior result sections  
