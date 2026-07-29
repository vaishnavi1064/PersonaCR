# Minimal-A Result (real checkpoint only)

**Generated:** 2026-07-29T00:42:15.944815+00:00
**Target N (paired-clean):** 14
**Achieved N:** 14
**Incomplete / unpaired cases in checkpoint:** 0
**Status:** TARGET MET — reportable
**Primary metric:** `style_score` (Style Analyst `overall_style_score`, 0–100). Separation = off − in (more negative ⇒ off more deviant).

## Step 0 budget (context)

Groq `llama-3.3-70b-versatile` docs base limits: **30 RPM**, **1K RPD**, **12K TPM**, **100K TPD**. Each arm ≈ 3–4 LLM calls; TPM is binding. Harness paces **25s** between arms, **1** in-flight.

## Primary metric — style_score separation

Source: `review_output.style_score` ← Style Analyst `overall_style_score` (deterministic from findings: start 100, subtract severity penalties high=25 / medium=12 / low=5; direction-filtered against fingerprint rates). LLM JSON score field is ignored.

| Arm | Avg score IN-STYLE | Avg score OFF-STYLE | Separation (off − in) | n_in | n_off |
|-----|-------------------:|--------------------:|----------------------:|-----:|------:|
| Personalized | 89.143 | 60.286 | **-28.857** | 7 | 7 |
| Generic | 96.857 | 91.714 | **-5.143** | 7 | 7 |

## Diagnostic — finding-count separation (demoted; do not judge on this)

Count of Style Analyst findings with `category != "error"`. Kept for visibility only.

| Arm | Avg findings IN | Avg findings OFF | Separation_findings (off − in) |
|-----|----------------:|-----------------:|-------------------------------:|
| Personalized | 1.286 | 1.143 | -0.143 |
| Generic | 0.286 | 0.429 | 0.143 |

## Per-feature deviation (personalized style issue categories, when checkpointed)

_No per-feature issue texts in main checkpoint (control runner stores issues; main harness arm records may not)._

## CRScore-style metrics (Layer 3 scores captured per clean arm)

### comprehensiveness

- Personalized: in=0.488, off=0.827 (n_in=7, n_off=7)
- Generic: in=0.589, off=0.628 (n_in=7, n_off=7)
- Separation (personalized − generic), mean over cases with scores: **0.0491**

### conciseness

- Personalized: in=0.845, off=0.882 (n_in=7, n_off=7)
- Generic: in=0.857, off=0.852 (n_in=7, n_off=7)
- Separation (personalized − generic), mean over cases with scores: **0.0086**

### relevance

- Personalized: in=0.584, off=0.845 (n_in=7, n_off=7)
- Generic: in=0.689, off=0.72 (n_in=7, n_off=7)
- Separation (personalized − generic), mean over cases with scores: **0.0096**

## Per-case raw deltas

| Case | Δ style_score (p−g) | Δ findings (diag) | Δ comp | Δ conc | Δ rel |
|------|--------------------:|------------------:|-------:|-------:|------:|
| `pair_1_merge_headers/in_style` | 10.0 | 1 | 0.111 | -0.25 | -0.008 |
| `pair_1_merge_headers/off_style` | -20.0 | 1 | 0.345 | 0.333 | 0.348 |
| `pair_2_build_url/in_style` | -5.0 | 1 | -0.17 | 0.0 | -0.144 |
| `pair_2_build_url/off_style` | -62.0 | 0 | 0.454 | 0.25 | 0.386 |
| `pair_3_parse_status/in_style` | -10.0 | 1 | 0.111 | 1.0 | 0.2 |
| `pair_3_parse_status/off_style` | -62.0 | 1 | 0.157 | 0.0 | 0.099 |
| `pair_4_extract_cookies/in_style` | -22.0 | 2 | -0.317 | -0.333 | -0.325 |
| `pair_4_extract_cookies/off_style` | -50.0 | 2 | 0.102 | -0.179 | -0.05 |
| `pair_5_redact_auth/in_style` | -5.0 | 0 | -0.25 | -0.5 | -0.334 |
| `pair_5_redact_auth/off_style` | -25.0 | 1 | 0.144 | 0.2 | 0.167 |
| `pair_6_join_query/in_style` | -17.0 | 2 | 0.142 | 0.0 | 0.097 |
| `pair_6_join_query/off_style` | -12.0 | 1 | 0.091 | -0.2 | -0.016 |
| `pair_7_ensure_scheme/in_style` | -5.0 | 0 | -0.333 | 0.0 | -0.227 |
| `pair_7_ensure_scheme/off_style` | 11.0 | -1 | 0.1 | -0.2 | -0.058 |

## Statistical power

N=14 paired-clean cases is at/above the predeclared target of 14. At this sample size the result is directional / preliminary — do not claim statistical significance.

## What this does and does not demonstrate

This report shows observed **style_score** separation (primary) and finding-count separation (diagnostic only) between the personalized arm (requests fingerprint + live Chroma retrieval) and the generic arm (empty fingerprint, no collection). Finding counts alone previously flattened a real signal (see positive control). It does **not** prove production readiness and generalizes only to these hand-authored pairs against psf/requests. Throttled and `category=error` arms were never counted.

## Quota / remaining work

Target 14 reached; further runs optional to grow N toward all 10 cases.

Checkpoint file: `D:/agentic_project/evals/minimal_a_checkpoint.jsonl`

---

## Shared-scale expand — N=14 paired-clean (APPEND)

**Generated:** 2026-07-29T00:42:27.146972+00:00  
**Metric:** frozen fair shared-scale (framing a) — weights/thresholds unchanged.  
**Paired-clean N:** 14 (7 pairs × in/off).  
**Throttled/errored arms excluded from averages:** 0 (honesty: never checkpointed).  
**Groq / runs:** free-tier (pace=60s); 4 new paired-clean this run, 0 throttled  
**Harness runs this expand:** 4.  
New-case construction: `evals/minimal_a_pairs_construction.md`.

### Per-pair feature-distance (arm-identical)

| Pair | IN dist | OFF dist | sep (off−in) | OFF farther? |
|------|--------:|---------:|-------------:|:------------:|
| pair_1_merge_headers | 0.08 | 0.7724 | 0.6924 | yes |
| pair_2_build_url | 0.08 | 0.7264 | 0.6464 | yes |
| pair_3_parse_status | 0.08 | 0.7264 | 0.6464 | yes |
| pair_4_extract_cookies | 0.08 | 0.7724 | 0.6924 | yes |
| pair_5_redact_auth | 0.08 | 0.7264 | 0.6464 | yes |
| pair_6_join_query | 0.08 | 0.92 | 0.84 | yes |
| pair_7_ensure_scheme | 0.08 | 0.7264 | 0.6464 | yes |

Mean IN dist **0.08**, mean OFF dist **0.7672**, mean sep **0.6872** (7/7 pairs OFF farther).

### Per-pair framing-(a) arm tracking

| Pair | p OFF recall | g OFF recall | p IN FP | g IN FP | case verdict |
|------|-------------:|-------------:|--------:|--------:|--------------|
| pair_1_merge_headers | 0.5 | 0.5 | 0 | 2 | mixed |
| pair_2_build_url | 0.75 | 0.0 | 0 | 0 | personalized_better |
| pair_3_parse_status | 0.75 | 0.0 | 0 | 0 | personalized_better |
| pair_4_extract_cookies | 0.5 | 0.0 | 3 | 0 | mixed |
| pair_5_redact_auth | 0.25 | 0.0 | 1 | 0 | mixed |
| pair_6_join_query | 0.2 | 0.0 | 2 | 0 | mixed |
| pair_7_ensure_scheme | 0.25 | 0.5 | 1 | 0 | generic_better |

### Pooled means (framing a)

| Arm | OFF pooled recall | IN FP-rate (dims/case) |
|-----|------------------:|-----------------------:|
| personalized | 0.4483 | 1.0 |
| generic | 0.1379 | 0.2857 |

**Reason:** mixed: OFF recall p=0.4483 g=0.1379; IN FP-rate p=1.00 g=0.29

### Robustness / consistency

- Personalized-better pairs: **2** `['pair_2_build_url', 'pair_3_parse_status']`
- Wrong-way (generic better): **1** `['pair_7_ensure_scheme']`

### Honest verdict (expand-N)

**Framing-(a) one-line:** personalization separates/tracks better than generic on this fair scale: **inconclusive**.

N≈12–15 remains modest — directional + consistency only; **not** strong statistical significance. Compare to the prior N=6 append above for held / strengthened / weakened.

Artifacts: `evals/results/shared_scale_metric.json`, `evals/minimal_a_pairs_construction.md`.

### Vs prior N=10 (same frozen metric)

At N=10: inconclusive; personalized_better **2**/5; wrong-way **0**.  
At N=14: inconclusive; personalized_better **2**/7; wrong-way **1** (pair_7_ensure_scheme).

Pooled OFF recall still favors personalized (0.45 vs 0.14), but IN FP-rate also favors generic (p=1.0 vs g=0.29) — same mixed pattern. Consistency **weakened** slightly (first wrong-way case). Overall vs N=10: signal **held as inconclusive** (did not strengthen).

**One-line (fair scale, N=14):** personalization separates in/off better than generic — **inconclusive**.
