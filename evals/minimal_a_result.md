# Minimal-A Result (real checkpoint only)

**Generated:** 2026-07-28T00:41:40.263728+00:00
**Target N (paired-clean):** 14
**Achieved N:** 10
**Incomplete / unpaired cases in checkpoint:** 1 (`pair_6_join_query/in_style`)
**Status:** INCOMPLETE — need more quota windows
**Primary metric:** `style_score` (Style Analyst `overall_style_score`, 0–100). Separation = off − in (more negative ⇒ off more deviant).

## Step 0 budget (context)

Groq `llama-3.3-70b-versatile` docs base limits: **30 RPM**, **1K RPD**, **12K TPM**, **100K TPD**. Each arm ≈ 3–4 LLM calls; TPM is binding. Harness paces **25s** between arms, **1** in-flight.

## Primary metric — style_score separation

Source: `review_output.style_score` ← Style Analyst `overall_style_score` (deterministic from findings: start 100, subtract severity penalties high=25 / medium=12 / low=5; direction-filtered against fingerprint rates). LLM JSON score field is ignored.

| Arm | Avg score IN-STYLE | Avg score OFF-STYLE | Separation (off − in) | n_in | n_off |
|-----|-------------------:|--------------------:|----------------------:|-----:|------:|
| Personalized | 89.2 | 51.8 | **-37.4** | 5 | 5 |
| Generic | 95.6 | 95.6 | **0.0** | 5 | 5 |

## Diagnostic — finding-count separation (demoted; do not judge on this)

Count of Style Analyst findings with `category != "error"`. Kept for visibility only.

| Arm | Avg findings IN | Avg findings OFF | Separation_findings (off − in) |
|-----|----------------:|-----------------:|-------------------------------:|
| Personalized | 1.4 | 1.2 | -0.2 |
| Generic | 0.4 | 0.2 | -0.2 |

## Per-feature deviation (personalized style issue categories, when checkpointed)

_No per-feature issue texts in main checkpoint (control runner stores issues; main harness arm records may not)._

## CRScore-style metrics (Layer 3 scores captured per clean arm)

### comprehensiveness

- Personalized: in=0.417, off=0.812 (n_in=5, n_off=5)
- Generic: in=0.52, off=0.572 (n_in=5, n_off=5)
- Separation (personalized − generic), mean over cases with scores: **0.0687**

### conciseness

- Personalized: in=0.783, off=0.914 (n_in=5, n_off=5)
- Generic: in=0.8, off=0.793 (n_in=5, n_off=5)
- Separation (personalized − generic), mean over cases with scores: **0.0521**

### relevance

- Personalized: in=0.499, off=0.852 (n_in=5, n_off=5)
- Generic: in=0.621, off=0.662 (n_in=5, n_off=5)
- Separation (personalized − generic), mean over cases with scores: **0.0339**

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

## Statistical power

N=10 paired-clean cases is below the predeclared target of 14. At this sample size the result is directional / preliminary — do not claim statistical significance.

## What this does and does not demonstrate

This report shows observed **style_score** separation (primary) and finding-count separation (diagnostic only) between the personalized arm (requests fingerprint + live Chroma retrieval) and the generic arm (empty fingerprint, no collection). Finding counts alone previously flattened a real signal (see positive control). It does **not** prove production readiness and generalizes only to these hand-authored pairs against psf/requests. Throttled and `category=error` arms were never counted.

## Quota / remaining work

Need **4** more paired-clean cases to hit target 14. At ~1–2 clean cases per careful quota window (TPM-limited), expect roughly **4–8** additional runs with `--max-cases 2` (or wait for daily reset if RPD exhausted).

Checkpoint file: `D:/agentic_project/evals/minimal_a_checkpoint.jsonl`
