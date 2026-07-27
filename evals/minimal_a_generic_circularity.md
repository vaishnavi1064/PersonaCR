# Diagnosis — Is the post-A/B style_score circular for the generic arm?

**Date:** 2026-07-27  
**Mode:** diagnosis only — scorer / arms / retrieval / guards untouched  
**Groq cost this pass:** **0** (stored evidence + control raw from prior force re-run)

---

## Step 1 — Can the penalty fire on the generic arm?

### How the scorer works (code fact)

`compute_style_score_from_findings` subtracts severity penalties for **every** finding with `category != "error"`. It does **not** check for a fingerprint tag. Empty-fingerprint direction filter is a no-op.

Mapping: start **100**; high **−25**, medium **−12**, low **−5**.

So arithmetically, generic *can* be penalized **if** Style Analyst emits findings.

### pair1 generic — real findings + arithmetic (stored evidence)

**IN** (`pair_1_merge_headers/in_style/generic`) → checkpoint **78.0**

| finding | severity | penalty |
|---------|----------|--------:|
| style: explicit loops “not most Pythonic”; fp=`No similar functions found…` | medium | −12 |
| complexity: may not handle edge cases | low | −5 |
| naming: name could be more descriptive | low | −5 |
| **Total** | | **100 − 22 = 78** |

**OFF** (`…/off_style/generic`) → checkpoint **78.0**

| finding | severity | penalty |
|---------|----------|--------:|
| style: unnecessary dict comprehensions | medium | −12 |
| style: clear docstring but fingerprint empty | low | −5 |
| naming: camelCase but fingerprint empty | low | −5 |
| **Total** | | **100 − 22 = 78** |

Findings exist and **do** incur penalties. But IN and OFF land on the **same** score: soft generic/best-practice nits, not a fingerprint-relative style gap. `fingerprint_value` repeatedly says “Not applicable (no similar functions found)” / empty fingerprint.

### pair2 / pair3 generic — live re-run under new scorer

| key | n_raw_findings | style_score | arithmetic |
|-----|---------------:|------------:|------------|
| pair_2 …/in_style/generic | **0** | **100** | 100 − 0 = 100 |
| pair_2 …/off_style/generic | **0** | **100** | 100 − 0 = 100 |
| pair_3 …/in_style/generic | **0** | **100** | 100 − 0 = 100 |
| pair_3 …/off_style/generic | **0** | **100** | 100 − 0 = 100 |

On 4/6 generic arms in the N=6 set, **zero findings → score stuck at 100 by construction of “score = f(findings)” with an empty finding set.**

N=6 generic means: (78+100+100)/3 = **92.667** for both IN and OFF → sep **0.0**.

### Prompt coupling (why findings vanish)

`build_fingerprint_direction_guide({})` returns:

> `(no fingerprint — do not invent personal-pattern deviations)`

Together with “only report DEVIATIONS from personal patterns,” the empty-FP generic arm is **instructed not to emit** the very findings the deterministic score needs in order to move.

---

## Step 2 — Generic on the control (decisive stored result)

From `evals/results/minimal_a_control_raw.json` (post-fix `--force` re-run; **no new Groq**):

| | MAX-IN | MAX-OFF | sep (off−in) |
|--|-------:|--------:|-------------:|
| **Generic (new scorer)** | **100.0** | **51.0** | **−49.0** |
| Personalized (new) | 95.0 | 63.0 | −32.0 |
| Generic (**pre-fix**, prior control) | 100.0 | 0.0 | −100.0 |

Generic MAX-OFF pipeline style issues (official score **51** = 100−25−12−12):

- [error_handling/**high**] −25 — nested try/except “unusual without a fingerprint…”
- [naming/**medium**] −12 — PascalCase “unusual without a fingerprint…”
- [complexity/**medium**] −12 — list comprehension “unusual without a fingerprint…”

**Step 2 reading:** generic MAX-OFF is **not** stuck near ~90 — it **did** score low (51). Penalties can fire when the LLM still emits findings on a blatant fixture. This is **not** pure “generic cannot leave ~100.”

It is also **weaker** than pre-fix free LLM scalar (0), and the findings are hedged as “unusual without a fingerprint” rather than true personal-pattern deviations.

---

## Step 3 — Common-scale analysis

Experiment logic: personalized must beat **generic** on the **same** primary metric.

| | Personalized | Generic |
|--|--------------|---------|
| Fingerprint in Style Analyst | requests FP + direction guide | `{}` + “do not invent personal-pattern deviations” |
| Retrieval | live Chroma | none |
| Score | 100 − Σ severity(findings) | same formula |

The deterministic score is **only meaningfully movable when Style Analyst emits findings.** Emitting personal-pattern deviations is what the personalized arm is set up to do; the generic arm is set up (empty FP + prompt) **not** to. So:

- Yes: the new score is **primarily meaningful for fingerprint-conditioned reviews**.
- The two arms are **not** on a fair common scale for “does personalization separate IN vs OFF better?” — personalized can generate penalizable deviations; generic often cannot (or emits non-separating BP nits, as in pair1 78=78).

Control shows generic *can* still move on an extreme; N=6 shows on realistic pairs it often **doesn't**, collapsing sep to 0 while personalized moves freely (−46). That gap is **partly baked into arm×metric coupling**, not a clean measurement of personalization.

---

## Step 4 — Verdict

### **Mixed — comparatively circular for the N=6 claim; not arithmetically locked**

**Not pure circular** by the strict Step-2 test: generic **can** incur penalties and **did** score control MAX-OFF at **51** (not ~90). The scorer code does not special-case “personal-pattern only.”

**Comparatively circular / invalid as thesis support** for personalized −46.3 vs generic **0.0**:

1. On 4/6 N=6 generic arms, **0 findings → score ≡ 100** for both IN and OFF.
2. On pair1, findings existed but **identical penalty totals** (78 vs 78) from empty-FP / BP nits.
3. Generic sep **0.0** is therefore largely an artifact of “score = f(findings)” + an arm that is prompted not to produce those findings — not evidence that generic cannot tell in-style from off-style in principle (pre-fix free score did: sep −50; control still does: sep −49).

**The −46.3 vs 0.0 result must not be treated as thesis support.** A metric that flatters personalized by neutering the baseline is worse than the honest prior negative.

### Implied fix (NOT executed)

Restore a **common movable scale**, e.g. one of:

1. **Deterministic feature-vs-fingerprint score** applied to the submitted code for **both** arms (same requests FP at scoring time); keep arm difference in retrieval / finding generation only; or  
2. **Dual path:** findings-derived score when FP present; a separate generic-capable style score when FP is empty (e.g. free LLM scalar or fixed style prior) — only if both are calibrated onto one comparable axis; or  
3. **Same Style Analyst conditioning for scoring** (both arms see the fingerprint for score inputs) while still ablating retrieval / personalization elsewhere.

Do **not** keep using findings-derived `overall_style_score` as the sole personalized-vs-generic separator while the generic arm is instructed to emit no personal-pattern findings.

---

## Artifacts

- Script: `evals/diagnose_generic_circularity.py` (read-only diagnosis)
- Evidence: `evals/results/minimal_a_pair_*_evidence.json`, control `evals/results/minimal_a_control_raw.json`
- pair1 bug record unchanged: `evals/minimal_a_pair1_diagnosis.md`
