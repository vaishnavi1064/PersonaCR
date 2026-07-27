"""
Step 4b — ChatPage repo-selection consolidation.

Single source of truth:
  selectedRepoUrls / selectedRepoUrlsByChatId
  (index 0 = review target)

Deleted competing fields:
  lastAnalyzedRepo (legacy HEAD)
  primaryRepoUrlByChatId (WIP)

Correct contract for review: if the user has selected at least one analyzed
repo, review resolves to selected[0]. No separate primary/legacy gate.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CHATPAGE = ROOT / "frontend" / "src" / "pages" / "ChatPage.tsx"
STORE = ROOT / "frontend" / "src" / "store" / "useStore.ts"


def _resolve_review_target_correct(
    selected_urls: list[str],
    primary_url: str | None,
    last_analyzed_repo: str | None = None,
) -> str | None:
    """Documented correct resolution — used as the assertion oracle."""
    if not selected_urls:
        return None
    if primary_url and primary_url in selected_urls:
        return primary_url
    return selected_urls[0]


def _resolve_review_target_as_implemented(
    selected_urls: list[str],
    primary_url: str | None,
    last_analyzed_repo: str | None,
    chatpage_src: str,
) -> str | None:
    """
    Mirror the gate actually present in ChatPage.tsx source.
    Detects which field the review path uses.
    """
    uses_last = bool(re.search(r"reviewCode\(\s*lastAnalyzedRepo", chatpage_src))

    # Consolidated: reviewTarget derived from selectedRepoUrls (e.g. selected[0])
    review_target_assign = re.search(
        r"const reviewTarget\s*=\s*([^\n]+)",
        chatpage_src,
    )
    assign = review_target_assign.group(1) if review_target_assign else ""
    uses_selection = bool(
        re.search(r"selectedRepoUrls|selected_repos|selected\[0\]", assign)
    )

    uses_primary_only = (
        bool(re.search(r"primaryRepoUrlByChatId", chatpage_src))
        and bool(re.search(r"const reviewTarget", chatpage_src))
        and not uses_selection
    )

    if uses_last:
        return last_analyzed_repo
    if uses_selection:
        # Single-slice contract: selected[0] (primary encoded as index 0)
        if not selected_urls:
            return None
        if primary_url and primary_url in selected_urls:
            return primary_url
        return selected_urls[0]
    if uses_primary_only:
        # Legacy WIP bug: primary only, no selection fallback
        return primary_url
    # Unknown — treat as broken
    return None


class TestChatPageRepoSelection:
    def test_source_documents_competing_fields(self):
        """After consolidation: selected slice exists; deleted fields are gone."""
        store = STORE.read_text(encoding="utf-8")
        page = CHATPAGE.read_text(encoding="utf-8")

        has_legacy = "lastAnalyzedRepo" in store or "lastAnalyzedRepo" in page
        has_selected = "selectedRepoUrls" in page or "selectedRepoUrlsByChatId" in store
        has_primary = "primaryRepoUrlByChatId" in store or "primaryRepoUrlByChatId" in page

        assert has_selected, "selected-repos state must exist"
        assert not has_legacy, "lastAnalyzedRepo must be deleted from store/ChatPage"
        assert not has_primary, "primaryRepoUrlByChatId must be deleted from store/ChatPage"

    def test_review_resolves_from_selection_when_primary_missing(self):
        """
        Scenario: user has selected repos (Q&A would work) but primary/legacy
        review field is null → review must still proceed via selected[0].
        """
        page = CHATPAGE.read_text(encoding="utf-8")
        selected = ["https://github.com/acme/styled-lib"]
        primary = None
        last_analyzed = None

        expected = _resolve_review_target_correct(selected, primary, last_analyzed)
        actual = _resolve_review_target_as_implemented(
            selected, primary, last_analyzed, page
        )

        assert expected == "https://github.com/acme/styled-lib"
        assert actual == expected, (
            "Repo-selection bug: review gate ignores non-empty selected repos when "
            f"primary/legacy is null. actual={actual!r} expected={expected!r}. "
            "Review must resolve from selectedRepoUrls[0] (single slice)."
        )

    def test_review_code_call_does_not_hardcode_legacy_only(self):
        """
        Stricter source assertion on the review-target assignment itself.
        """
        page = CHATPAGE.read_text(encoding="utf-8")
        # Extract the reviewTarget / reviewCode wiring block
        m = re.search(
            r"(?:const reviewTarget\s*=\s*([^\n]+)|if\s*\(\s*!lastAnalyzedRepo\s*\))",
            page,
        )
        assert m, "could not locate review gate in ChatPage.tsx"

        if "lastAnalyzedRepo" in page and re.search(r"reviewCode\(\s*lastAnalyzedRepo", page):
            pytest.fail(
                "HEAD bug present: reviewCode(lastAnalyzedRepo) while RepoSelector "
                "writes selectedRepoUrls"
            )

        if "primaryRepoUrlByChatId" in page:
            pytest.fail(
                "WIP bug present: primaryRepoUrlByChatId still referenced in ChatPage; "
                "review must use selectedRepoUrls only"
            )

        assign = m.group(1) or ""
        if assign:
            # Must reference selection (selectedRepoUrls / selected[0]) — primary alone is insufficient
            uses_selection_fallback = bool(
                re.search(r"selectedRepoUrls|selected_repos|selected\[0\]", assign)
            )
            assert uses_selection_fallback, (
                "WIP still broken: review target assignment has no selected-repos fallback: "
                f"{assign.strip()!r}. Q&A uses selectedRepoUrls; review uses primary only."
            )
