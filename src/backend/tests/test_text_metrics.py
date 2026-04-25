"""Tests for CER / WER utilities.

The article-canonical examples are encoded as test cases so future
refactors of the DP can't silently break them. See:
  - mitten / fitting → Levenshtein 3
  - 809475127 / 80g475Z7 → CER ≈ 33.33%
  - my name is kenneth / myy nime iz kenneth → WER 75%
"""

from __future__ import annotations

import math

import pytest

from src.backend.utils.text_metrics import (
    EditOps,
    aggregate_cer,
    aggregate_wer,
    cer,
    cer_with_breakdown,
    normalized_cer,
    wer,
)


# ─── Levenshtein-grounded sanity ──────────────────────────────────────────

def test_identical_strings_zero_cer():
    assert cer("abc", "abc") == 0.0
    assert wer("hello world", "hello world") == 0.0


def test_mitten_fitting_distance_three():
    """Article example: m→f, e→i, +g = 3 edits over reference length 6."""
    val, ops = cer_with_breakdown("mitten", "fitting")
    assert ops.total_edits == 3
    assert math.isclose(val, 3 / 6, abs_tol=1e-6)


def test_id_string_cer_matches_article():
    """Article example: 809475127 vs 80g475Z7 → CER 33.33%."""
    val, ops = cer_with_breakdown("809475127", "80g475Z7")
    # Article counts: 2 substitutions + 1 deletion + 0 insertions = 3 edits, ref=9
    assert ops.total_edits == 3
    assert math.isclose(val, 3 / 9, abs_tol=1e-4)


def test_wer_article_example():
    """Article: 'my name is kenneth' vs 'myy nime iz kenneth' → WER 75%."""
    # 4 reference words, 3 substitutions
    val = wer("my name is kenneth", "myy nime iz kenneth")
    assert math.isclose(val, 0.75, abs_tol=1e-6)


# ─── Edge cases ───────────────────────────────────────────────────────────

def test_empty_reference_with_hypothesis_treats_all_as_insertions():
    """No reference but a non-empty hypothesis = pure insertion error.
    Plain CER is unbounded (uses len(hyp) as denominator); normalized
    is bounded."""
    val, ops = cer_with_breakdown("", "abc")
    assert ops.insertions == 3
    assert val == 1.0
    assert normalized_cer("", "abc") == 1.0


def test_empty_hypothesis_with_reference_is_all_deletions():
    val, ops = cer_with_breakdown("abc", "")
    assert ops.deletions == 3
    assert val == 1.0


def test_both_empty_zero():
    assert cer("", "") == 0.0
    assert normalized_cer("", "") == 0.0


def test_none_inputs_treated_as_empty():
    assert cer(None, None) == 0.0
    assert cer(None, "") == 0.0
    assert wer(None, None) == 0.0


def test_normalized_cer_bounded_by_one():
    """Plain CER can exceed 1.0 (article: ABC vs ABC12345 = 166.67%);
    normalized CER never does."""
    plain = cer("ABC", "ABC12345")
    assert plain > 1.0
    norm = normalized_cer("ABC", "ABC12345")
    assert 0.0 <= norm <= 1.0
    # 5 insertions, 3 matches, 0 sub/del → 5/(5+3) = 0.625
    assert math.isclose(norm, 5 / 8, abs_tol=1e-6)


def test_breakdown_separates_sub_del_ins():
    _, ops = cer_with_breakdown("abc", "abXcd")
    # ref a-b-c, hyp a-b-X-c-d → 1 insert (X) + 1 insert (d) = 2 insertions, 3 matches
    assert ops.matches == 3
    assert ops.insertions == 2
    assert ops.substitutions == 0
    assert ops.deletions == 0


# ─── Field-extraction-flavored cases (the actual production use) ──────────

def test_vendor_name_close_match():
    """ACMC Corp vs ACME Corp — one substitution out of 9 chars."""
    val = cer("ACME Corp", "ACMC Corp")
    assert math.isclose(val, 1 / 9, abs_tol=1e-6)


def test_decimal_slip_amount_low_cer():
    """1000 read as 10.00 — only one structural edit (insert '.') even
    though semantically the value is off by 100×. This is exactly why
    CER alone can't catch decimal slips; it's a low-CER, high-impact
    error. The MagnitudeGuard in validation/auditor.py handles this
    semantic case separately."""
    val, ops = cer_with_breakdown("1000", "10.00")
    # ref=1000 (4 chars), hyp=10.00 (5 chars), single insertion of '.'
    assert ops.insertions == 1
    assert ops.matches == 4
    assert ops.total_edits == 1
    assert math.isclose(val, 1 / 4, abs_tol=1e-6)


# ─── Aggregation ──────────────────────────────────────────────────────────

def test_aggregate_cer_micro_averages_over_corpus():
    """Corpus CER weights long references more than short ones."""
    pairs = [
        ("aaaaaaaaaa", "aaaaaaaaab"),  # 1 edit / 10 = 0.1
        ("xy", "xz"),                   # 1 edit / 2 = 0.5
    ]
    # Micro: total edits 2, total ref chars 12 → 2/12 ≈ 0.167
    assert math.isclose(aggregate_cer(pairs), 2 / 12, abs_tol=1e-6)


def test_aggregate_wer_works_with_empty_pairs():
    assert aggregate_wer([]) == 0.0


def test_aggregate_wer_skips_unsupervised_pairs_correctly():
    pairs = [
        ("hello world foo", "hello world bar"),   # 1 wer-edit / 3 ref words
        ("a b c d", "a b c d"),                    # 0 / 4
    ]
    # Total edits 1, total ref words 7 → 1/7
    assert math.isclose(aggregate_wer(pairs), 1 / 7, abs_tol=1e-6)
