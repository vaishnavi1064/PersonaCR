# Minimal-A Positive Control — Diagnosis

**Generated:** 2026-07-27T22:19:07.488921+00:00
**Fingerprint:** psf/requests (`evals/results/minimal_a_fingerprint.json`)
**Fixtures:** `evals/minimal_a_control_fixtures.json` (NOT in main case set)
**Primary metric (Bug 1 fix):** `style_score` (off − in). Finding counts are diagnostic only.
**Verdict: B**

## Verdict explanation

PRIMARY style_score shows clear personalized separation (sep=-32.0 ≤ −15). Bug 1 metric fix recovers the control signal. style_score personalized in=95.0 off=63.0 sep(off−in)=-32.0; generic in=100.0 off=51.0 sep=-49.0; [diag] findings sep_p=0 sep_g=3; raw_sep=-1; keyword_hits=['type', 'hint', 'snake']; retrieval_in_prompt=True; per_feature_in={'naming': 1}; per_feature_off={'naming': 1}. Bug2 residual: MAX-IN still has style categories {'naming': 1} (false/inverted findings can inflate IN deviance / depress IN score); Bug3 residual: type_safety present in raw OFF probe but absent from final pipeline style issues

## What A / B / C mean (under style_score primary)

- **A — Broken measurement:** raw findings show a signal; even style_score aggregation flattens it.
- **B — Metric recovers / effect detectable:** style_score shows clear MAX-OFF vs MAX-IN gap on personalized arm.
- **C — Mechanism genuinely flat:** even extremes show ~0 style_score separation and raw findings don't differ.

## Case: MAX-IN-STYLE (`control_max_in_style`)

Task: Normalize an HTTP header name to Title-Case hyphenated form

### Step 3 — Retrieval / prompt instrumentation (personalized path)

- Retrieved functions: **3** (similar_functions_found field=3)
- Similar snippets non-empty / would reach prompt: **True** (1397 chars)
- Retrieval neighbors:
  - rank 1: `unicode_is_ascii` in `src/requests/_internal_utils.py` distance=0.7993708252906799
  - rank 2: `to_native_string` in `src/requests/_internal_utils.py` distance=0.8505102396011353
  - rank 3: `_resolve_char_detection` in `src/requests/compat.py` distance=0.8980391025543213

- Raw Style Analyst findings (ex error): **3** (style_score=85.0)
  - [type_safety/low] The submitted code uses type hints, which is consistent with this developer's pattern.
    - fp=`0.993 (COMMON)` → submitted=`Type hints are present`
  - [naming/low] The submitted code uses snake_case naming convention, which is consistent with this developer's pattern.
    - fp=`snake_case` → submitted=`snake_case naming convention used`
  - [complexity/low] The submitted code has a low complexity, which is consistent with this developer's pattern of having an average complexity of 5.22.
    - fp=`5.22` → submitted=`Low complexity`

### Official arm metrics (primary = style_score)

| Arm | **style_score** | n_style (diag) | similar | comp | conc | rel | status |
|-----|----------------:|---------------:|--------:|-----:|-----:|----:|--------|
| personalized | **95.0** | 1 | 3 | 0.9 | 1.0 | 0.947 | passed |
| generic | **100.0** | 0 | 0 | 0.333 | 1.0 | 0.5 | low_confidence |

#### Final pipeline issues (personalized)

- [style/naming/low] The function name 'normalize_header_name' follows the snake_case convention, which is consistent with the developer's naming convention.
- [defect/smell/low] The function does not handle the case where the input is not a string. It would be better to add a type check at the beginning of the function.
- [defect/smell/low] The variable names 'p' and 'out' are not very descriptive. It would be better to use more descriptive names.

#### Final pipeline issues (generic)

- [defect/smell/low] Variable names could be more descriptive
- [defect/smell/low] Function could benefit from a docstring for better readability

## Case: MAX-OFF-STYLE (`control_max_off_style`)

Task: Normalize an HTTP header name to Title-Case hyphenated form

### Step 3 — Retrieval / prompt instrumentation (personalized path)

- Retrieved functions: **8** (similar_functions_found field=8)
- Similar snippets non-empty / would reach prompt: **True** (1959 chars)
- Retrieval neighbors:
  - rank 1: `_basic_auth_str` in `src/requests/auth.py` distance=0.6633821129798889
  - rank 2: `sha_utf8` in `src/requests/auth.py` distance=0.6932902336120605
  - rank 3: `sha256_utf8` in `src/requests/auth.py` distance=0.7103345990180969
  - rank 4: `sha512_utf8` in `src/requests/auth.py` distance=0.7106016278266907
  - rank 5: `handle_401` in `src/requests/auth.py` distance=0.7394239902496338

- Raw Style Analyst findings (ex error): **2** (style_score=63.0)
  - [naming/high] Function name does not follow snake_case convention
    - fp=`snake_case` → submitted=`CamelCase`
  - [type_safety/medium] Missing type hints for function parameters and return types
    - fp=`0.993` → submitted=`no type hints in function`

### Official arm metrics (primary = style_score)

| Arm | **style_score** | n_style (diag) | similar | comp | conc | rel | status |
|-----|----------------:|---------------:|--------:|-----:|-----:|----:|--------|
| personalized | **63.0** | 1 | 8 | 0.714 | 0.833 | 0.769 | passed |
| generic | **51.0** | 3 | 0 | 0.769 | 0.9 | 0.829 | passed |

#### Final pipeline issues (personalized)

- [style/naming/high] Non-snake_case naming convention
- [defect/bug/medium] The function does not handle the case where inputName is None. This could lead to a TypeError when trying to call split() on None.
- [defect/bug/low] The function does not handle the case where inputName is not a string. This could lead to a TypeError when trying to call split() on a non-string object.
- [defect/smell/medium] The function has a nested try-except block. This can make the code harder to read and understand. It would be better to handle the exceptions in a single try-except block.
- [defect/smell/low] The function raises a RuntimeError with a generic error message. It would be better to provide a more specific error message that indicates what went wrong.
- [defect/smell/low] The function returns an empty string if all else fails. This could lead to unexpected behavior downstream. It would be better to raise an exception in this case.

#### Final pipeline issues (generic)

- [style/error_handling/high] The submitted code has a complex error handling mechanism with nested try-except blocks, which may be unusual without a fingerprint to compare against.
- [style/naming/medium] The submitted code uses PascalCase for function names, which may be unusual without a fingerprint to compare against.
- [style/complexity/medium] The submitted code has a list comprehension with conditional statements, which may be unusual without a fingerprint to compare against.
- [defect/bug/medium] The function does not handle the case where inputName is None or not a string. This could lead to a TypeError or unexpected behavior.
- [defect/bug/low] The function catches all exceptions and raises a RuntimeError. This could mask other issues and make debugging more difficult.
- [defect/bug/low] The function has a nested try-except block. The inner try-except block does not add any value and can be removed.
- [defect/smell/medium] The function has a broad exception handling mechanism. It would be better to handle specific exceptions that could occur.
- [defect/smell/low] The function has a redundant try-except block. The outer try-except block is not necessary.
- [defect/smell/low] The variable name 'inputName' could be more descriptive. Consider renaming it to something like 'header_name'.
- [defect/security/low] The function does not validate or sanitize the input. This could potentially lead to security issues if the input is not trusted.

## Separation summary (Bug 1: style_score is primary)

| Signal | MAX-IN | MAX-OFF | Separation (off − in) |
|--------|-------:|--------:|----------------------:|
| **Personalized style_score (PRIMARY)** | 95.0 | 63.0 | **-32.0** |
| Generic style_score | 100.0 | 51.0 | -49.0 |
| Personalized n_style (diagnostic) | 1 | 1 | 0 |
| Generic n_style (diagnostic) | 0 | 3 | 3 |
| Personalized raw Style Analyst (ex error) | 3 | 2 | -1 |

### Per-feature style categories (final pipeline issues, personalized)

- MAX-IN categories: `{'naming': 1}`
- MAX-OFF categories: `{'naming': 1}`

## Constraint note

Honesty guards, arm definitions, and scoring were not modified. Only the aggregation/reporting primary metric switched from finding counts to `style_score`. Control fixtures are separate from `minimal_a_pairs.json`. No numbers were fabricated.
