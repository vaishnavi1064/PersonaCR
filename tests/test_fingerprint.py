"""Step 1 — Fingerprint correctness (deterministic, no network)."""
from __future__ import annotations

import ast

import pytest

from backend.src.core.pattern_extractor import (
    _has_docstring,
    _has_type_hints,
    extract_fingerprint,
)
from tests.conftest import make_chunk


class TestFingerprintHandCounts:
    def test_key_rates_match_hand_counts(
        self, known_fingerprint_chunks, known_fingerprint_expected
    ):
        fp = extract_fingerprint(known_fingerprint_chunks)
        assert fp, "fingerprint must be non-empty for 10 valid functions"

        for key, expected in known_fingerprint_expected.items():
            assert key in fp, f"missing fingerprint key: {key}"
            assert fp[key] == expected, (
                f"{key}: computed={fp[key]!r} hand-count={expected!r}"
            )

    def test_skips_file_level_chunks(self, known_fingerprint_chunks):
        file_chunk = make_chunk(
            "__file_summary__",
            "# file summary\nimport os\n",
            granularity="file",
        )
        fp = extract_fingerprint(known_fingerprint_chunks + [file_chunk])
        assert fp["total_functions"] == 10

    def test_empty_chunk_list_returns_empty_dict(self):
        assert extract_fingerprint([]) == {}

    def test_empty_source_functions_yield_empty_fingerprint(self):
        chunks = [make_chunk("empty_fn", "\n\n")]
        assert extract_fingerprint(chunks) == {}


class TestFingerprintEdgeCases:
    def test_syntax_error_source_does_not_crash(self):
        bad = make_chunk("broken", "def broken(\n    pass")
        fp = extract_fingerprint([bad])
        # Still countable as a function by line length; docstring/hints helpers catch SyntaxError
        assert fp.get("total_functions") == 1
        assert fp.get("docstring_coverage") == 0.0
        assert _has_docstring(bad.source) is False

    def test_docstring_uses_ast_constant_not_ast_str(self):
        """Regression guard for Python 3.8+ ast.Constant (ast.Str removed)."""
        src = 'def documented():\n    """hello"""\n    return 1'
        assert _has_docstring(src) is True

        tree = ast.parse(src)
        fn = tree.body[0]
        doc_expr = fn.body[0]
        assert isinstance(doc_expr.value, ast.Constant)
        assert not hasattr(ast, "Str") or not isinstance(doc_expr.value, getattr(ast, "Str", ()))

    def test_match_statement_function_still_fingerprinted(self):
        """Python 3.10+ match must not break extract_fingerprint."""
        src = (
            "def classify_item(x):\n"
            "    match x:\n"
            "        case 0:\n"
            "            return 'zero'\n"
            "        case _:\n"
            "            return 'other'\n"
        )
        fp = extract_fingerprint([make_chunk("classify_item", src)])
        assert fp["total_functions"] == 1
        assert fp["naming_convention"] == "snake_case"

    def test_type_hint_detection_on_annotated_def(self):
        assert _has_type_hints("def f(x: int) -> int:\n    return x") is True
        assert _has_type_hints("def f(x):\n    return x") is False
