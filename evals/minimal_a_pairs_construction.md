# Construction notes — expanded minimal-A pairs (psf/requests)

**Fingerprint:** `evals/results/minimal_a_fingerprint.json`  
**Repo:** psf/requests @ `4ed3d1b` (`user_id=eval-requests-user`)  
**High-signal FP facts (unchanged):** type_hint_usage≈0.993, naming=snake_case, docstring_coverage≈0.246 (LOW), error_handling_rate≈0.131 (LOW), comprehension_ratio≈0.016 (RARE).

## Construction rules (same as original pairs 1–5 — no cherry-picking)

For every pair:
- **Same task** for IN and OFF (behaviorally equivalent intent).
- **IN-STYLE:** snake_case name; type hints on params/return; little or no docstring; no try/except; explicit loops (no comprehensions); length in a normal short-helper range.
- **OFF-STYLE:** violates naming (camelCase / PascalCase / mixedCase params); drops type hints; adds a verbose Args/Returns docstring; plus at least one of: broad try/except, or comprehension-heavy body — matching the original violation mix.
- Difficulty: ordinary HTTP/URL/header helpers similar to pairs 1–5 — not deliberately easier or harder, not chosen to favor personalized.

Pairs **4–5** were already authored under these rules but not yet run (target stopped at N=6). Pairs **6–7** are new under the same rules.

---

### pair_4_extract_cookies (pre-authored, newly run)

- **Task:** Parse Set-Cookie values from a headers dict into name→value.
- **IN obeys:** snake_case, types, no docstring, explicit for-loop, no try/except.
- **OFF violates:** mixedCase params (`responseHeaders`), no types, verbose docstring, comprehension + `dict()`.

### pair_5_redact_auth (pre-authored, newly run)

- **Task:** Redact password in `user:password@` URLs.
- **IN obeys:** snake_case, types, no docstring, no try/except, no comprehensions.
- **OFF violates:** camelCase name/params, no types, lengthy docstring, broad try/except fallback.

### pair_6_join_query (new)

- **Task:** Join a dict of query parameters into a `k=v&k=v` string (no encoding library; simple string join).
- **IN obeys:** `join_query` snake_case; `(params: dict) -> str` hints; no docstring; explicit for-loop building parts; no try/except; no comprehension.
- **OFF violates:** `joinQuery` camelCase; no types; verbose Args/Returns docstring; list comprehension for pairs; unnecessary broad try/except.

### pair_7_ensure_scheme (new)

- **Task:** If a URL has no scheme, prepend `https://`; otherwise return unchanged.
- **IN obeys:** `ensure_scheme` snake_case; typed; no docstring; early return; no try/except; no comprehension.
- **OFF violates:** `EnsureScheme` PascalCase; no types; verbose docstring with examples; wraps body in try/except; uses a comprehension-style generator unnecessarily for a trivial check.

---

**Target N:** 7 pairs × {in, off} = **14** paired-clean cases (within 12–15).  
**Not used:** additional repos — stay on the same requests fingerprint for comparability with N=6.
