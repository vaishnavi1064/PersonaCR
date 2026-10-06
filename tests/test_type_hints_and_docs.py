"""
Type hints are measured only where annotations are optional (Python, TypeScript).
Statically typed languages and plain JavaScript are not counted as "typed" —
type_hint_usage is None when nothing was measurable. Doc comments for
non-Python code are found directly above the function in the file.
"""
from __future__ import annotations

import pytest

from backend.src.agents.style_analyst import build_fingerprint_direction_guide
from backend.src.core.github_ingestor import _extract_generic_functions, _has_leading_doc_comment
from backend.src.core.pattern_extractor import _ts_has_type_annotations, extract_fingerprint
from tests.conftest import make_chunk


def java(name: str, doc: bool = False):
    c = make_chunk(name, f"public int {name}(int x) {{\n    return x;\n}}", language="java", file_path="A.java")
    c.metadata["doc_comment"] = doc
    return c


def ts(name: str, sig: str):
    return make_chunk(name, f"{sig} {{\n  return 1\n}}", language="typescript", file_path="a.ts")


# ── Type hints ────────────────────────────────────────────────────────────────

def test_pure_java_repo_has_no_type_hint_measurement():
    fp = extract_fingerprint([java("a"), java("b"), java("c")])
    assert fp["type_hint_usage"] is None  # was 1.0: every Java function counted as typed
    assert fp["type_hint_functions"] == 0


def test_plain_javascript_is_not_measured():
    js = make_chunk("f", "function f(a, b) {\n  return a + b\n}", language="javascript", file_path="a.js")
    fp = extract_fingerprint([js])
    assert fp["type_hint_usage"] is None
    assert fp["type_hint_functions"] == 0


def test_python_known_corpus_unchanged(known_fingerprint_chunks):
    fp = extract_fingerprint(known_fingerprint_chunks)
    assert fp["type_hint_usage"] == 0.5  # 5 of 10 annotated
    assert fp["type_hint_functions"] == 10


def test_typescript_annotations_measured():
    chunks = [
        ts("a", "function a(x: number)"),             # param annotation
        ts("b", "function b(x): string"),             # return type
        ts("c", "function c(opts?: Options)"),        # optional param
        ts("d", "function d({ id, name }: User)"),    # destructured + annotated
        ts("e", "function e(x, y)"),                  # none
    ]
    fp = extract_fingerprint(chunks)
    assert fp["type_hint_functions"] == 5
    assert fp["type_hint_usage"] == 0.8


def test_mixed_repo_counts_only_measurable_functions():
    py_typed = make_chunk("p1", "def p1(x: int) -> int:\n    return x")
    py_plain = make_chunk("p2", "def p2(x):\n    return x")
    fp = extract_fingerprint([py_typed, py_plain, java("j1"), java("j2"), java("j3")])
    assert fp["type_hint_functions"] == 2
    assert fp["type_hint_usage"] == 0.5  # 1 of 2 Python functions — Java ignored
    assert fp["total_functions"] == 5


@pytest.mark.parametrize("sig,expected", [
    ("async fetchUser(id: string): Promise<User>", True),
    ("render()", False),
    ("constructor(private readonly svc: Service)", True),
    ("handle(event)", False),
])
def test_ts_signature_detection(sig, expected):
    assert _ts_has_type_annotations(f"{sig} {{\n  return\n}}") is expected


# ── Doc comments (non-Python) ─────────────────────────────────────────────────

JAVA_SRC = """\
package a;

public class Svc {
    /**
     * Loads a user.
     */
    @Override
    public User load(String id) {
        return repo.find(id);
    }

    public void save(User u) {
        repo.put(u);
    }

    // plain comment, not documentation
    public void drop(User u) {
        repo.remove(u);
    }
}
"""


def test_javadoc_above_method_is_detected_through_annotations():
    chunks = {c.function_name: c for c in _extract_generic_functions(JAVA_SRC, "Svc.java", "java")}
    assert chunks["load"].metadata["doc_comment"] is True
    assert chunks["save"].metadata["doc_comment"] is False
    assert chunks["drop"].metadata["doc_comment"] is False  # // isn't a Java doc comment


def test_go_uses_line_comments_rust_uses_triple_slash():
    go = "// Sum adds two ints.\nfunc Sum(a int, b int) int {\n  return a + b\n}\n".splitlines()
    assert _has_leading_doc_comment(go, 1, "go") is True
    rust = ["#[inline]", "/// Adds.", "#[must_use]", "fn add(a: i32) -> i32 {"]
    assert _has_leading_doc_comment(rust, 3, "rust") is True
    c_block = ["/* not a doc */", "int f(int x) {"]
    assert _has_leading_doc_comment(c_block, 1, "c") is False


def test_docstring_coverage_uses_detected_doc_comments():
    fp = extract_fingerprint([java("a", doc=True), java("b"), java("c"), java("d", doc=True)])
    assert fp["docstring_coverage"] == 0.5


def test_doc_comment_inside_the_60_line_window_no_longer_counts():
    # Old heuristic: any /** in the chunk text (often a LATER function's Javadoc)
    src = "public void a() {\n  x();\n}\n/** Docs for b. */\npublic void b() {\n}"
    c = make_chunk("a", src, language="java", file_path="A.java")
    c.metadata["doc_comment"] = False
    assert extract_fingerprint([c])["docstring_coverage"] == 0.0


# ── Ruby comments ─────────────────────────────────────────────────────────────

def test_ruby_hash_comments_are_counted():
    rb = make_chunk("f", "def f(x) {\n  # explain\n  x # inline\n}", language="ruby", file_path="a.rb")
    fp = extract_fingerprint([rb])
    assert fp["comment_density"] > 0


# ── Review-time guidance ──────────────────────────────────────────────────────

def test_style_guide_says_not_measured_instead_of_dropping_silently():
    guide = build_fingerprint_direction_guide({"type_hint_usage": None, "docstring_coverage": 0.2})
    assert "type_hint_usage=not measured" in guide
    assert "do NOT flag" in guide
    assert "docstring_coverage=0.200 (RARE)" in guide
