"""Character Error Rate (CER) and Word Error Rate (WER) for OCR / VLM outputs.

Implements the standard error-rate metrics used in the OCR literature
(see Carrasco 2014; Leung 2021 walkthrough). All functions are pure and
operate on already-normalized strings — callers decide normalization
(lowercase, strip currency markers, etc.) so the same primitive works
for raw OCR text AND for already-extracted field values.

Definitions:
    Levenshtein distance L(ref, hyp) = min number of single-token edits
    (insert / delete / substitute) to turn ref into hyp.

    CER  = L(ref_chars, hyp_chars) / max(len(ref_chars), 1)
    WER  = L(ref_words, hyp_words) / max(len(ref_words), 1)

    Normalized CER  = L / (L + len(LCS))
                    = (S + D + I) / (S + D + I + C)
    Bounded in [0, 1] regardless of insertion length — useful when you
    want to chart error rates without occasional 200% spikes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence


@dataclass(frozen=True)
class EditOps:
    """Counts of substitutions / deletions / insertions / matches between
    a reference and a hypothesis. Computed via a standard DP table —
    O(len(ref) * len(hyp)) time, O(min) space."""

    substitutions: int
    deletions: int
    insertions: int
    matches: int

    @property
    def total_edits(self) -> int:
        return self.substitutions + self.deletions + self.insertions

    def to_dict(self) -> dict:
        return {
            "substitutions": self.substitutions,
            "deletions": self.deletions,
            "insertions": self.insertions,
            "matches": self.matches,
        }


def _edit_ops(ref: Sequence, hyp: Sequence) -> EditOps:
    """Levenshtein DP that also recovers the operation breakdown.

    We trace back from cell (m, n) to count how many of each op were
    chosen on the minimum path. The path isn't unique, but the
    AGGREGATE counts of S/D/I/C are invariant across equally-cheap
    paths, so this is well-defined.
    """
    m, n = len(ref), len(hyp)
    if m == 0 and n == 0:
        return EditOps(0, 0, 0, 0)
    # Build the DP cost table.
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(m + 1):
        dp[i][0] = i
    for j in range(n + 1):
        dp[0][j] = j
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if ref[i - 1] == hyp[j - 1]:
                dp[i][j] = dp[i - 1][j - 1]
            else:
                dp[i][j] = 1 + min(
                    dp[i - 1][j],      # deletion
                    dp[i][j - 1],      # insertion
                    dp[i - 1][j - 1],  # substitution
                )
    # Trace back.
    s = d = ins = c = 0
    i, j = m, n
    while i > 0 or j > 0:
        if i > 0 and j > 0 and ref[i - 1] == hyp[j - 1]:
            c += 1
            i -= 1
            j -= 1
        elif i > 0 and j > 0 and dp[i][j] == dp[i - 1][j - 1] + 1:
            s += 1
            i -= 1
            j -= 1
        elif i > 0 and dp[i][j] == dp[i - 1][j] + 1:
            d += 1
            i -= 1
        else:
            ins += 1
            j -= 1
    return EditOps(substitutions=s, deletions=d, insertions=ins, matches=c)


def _to_chars(s: str | None) -> list[str]:
    return list(s) if s else []


def _to_words(s: str | None) -> list[str]:
    return s.split() if s else []


def cer(reference: str | None, hypothesis: str | None) -> float:
    """Character Error Rate.

    Returns L(ref, hyp) / len(ref). If `reference` is empty, falls back
    to len(hyp) so an entirely hallucinated output isn't reported as 0.
    Can exceed 1.0 when the hypothesis is much longer than the reference
    — see `normalized_cer` for the bounded variant.
    """
    if reference is None:
        reference = ""
    if hypothesis is None:
        hypothesis = ""
    ref_chars = _to_chars(reference)
    hyp_chars = _to_chars(hypothesis)
    ops = _edit_ops(ref_chars, hyp_chars)
    denom = len(ref_chars) if ref_chars else max(len(hyp_chars), 1)
    return ops.total_edits / denom


def wer(reference: str | None, hypothesis: str | None) -> float:
    """Word Error Rate. Same as CER but tokenized on whitespace."""
    if reference is None:
        reference = ""
    if hypothesis is None:
        hypothesis = ""
    ref_words = _to_words(reference)
    hyp_words = _to_words(hypothesis)
    ops = _edit_ops(ref_words, hyp_words)
    denom = len(ref_words) if ref_words else max(len(hyp_words), 1)
    return ops.total_edits / denom


def normalized_cer(reference: str | None, hypothesis: str | None) -> float:
    """CER variant that's always in [0, 1].

    Defined as (S + D + I) / (S + D + I + C). Carrasco's normalization;
    avoids the >100% spikes that plain CER produces on heavy insertion.
    """
    if reference is None:
        reference = ""
    if hypothesis is None:
        hypothesis = ""
    ops = _edit_ops(_to_chars(reference), _to_chars(hypothesis))
    denom = ops.total_edits + ops.matches
    if denom == 0:
        return 0.0
    return ops.total_edits / denom


def cer_with_breakdown(
    reference: str | None, hypothesis: str | None
) -> tuple[float, EditOps]:
    """CER plus the (S, D, I, C) breakdown — useful for error analysis.

    The breakdown tells you WHY a field has a particular CER:
      - high S = OCR misreading characters
      - high D = OCR truncating
      - high I = OCR hallucinating extra characters
    """
    if reference is None:
        reference = ""
    if hypothesis is None:
        hypothesis = ""
    ref = _to_chars(reference)
    hyp = _to_chars(hypothesis)
    ops = _edit_ops(ref, hyp)
    denom = len(ref) if ref else max(len(hyp), 1)
    return ops.total_edits / denom, ops


def aggregate_cer(pairs: Iterable[tuple[str | None, str | None]]) -> float:
    """Corpus-level CER: micro-average over all pairs.

    Sums total edits across the corpus and divides by total reference
    length — gives a single number that weights long references more,
    which matches OCR-paper convention (rather than averaging per-doc
    CER, which over-weights tiny references).
    """
    total_edits = 0
    total_ref_len = 0
    total_hyp_len_when_ref_empty = 0
    for ref, hyp in pairs:
        ref = ref or ""
        hyp = hyp or ""
        ops = _edit_ops(_to_chars(ref), _to_chars(hyp))
        total_edits += ops.total_edits
        total_ref_len += len(ref)
        if not ref:
            total_hyp_len_when_ref_empty += len(hyp)
    denom = total_ref_len if total_ref_len else max(total_hyp_len_when_ref_empty, 1)
    return total_edits / denom


def aggregate_wer(pairs: Iterable[tuple[str | None, str | None]]) -> float:
    total_edits = 0
    total_ref_words = 0
    total_hyp_words_when_ref_empty = 0
    for ref, hyp in pairs:
        ref_w = _to_words(ref)
        hyp_w = _to_words(hyp)
        ops = _edit_ops(ref_w, hyp_w)
        total_edits += ops.total_edits
        total_ref_words += len(ref_w)
        if not ref_w:
            total_hyp_words_when_ref_empty += len(hyp_w)
    denom = total_ref_words if total_ref_words else max(total_hyp_words_when_ref_empty, 1)
    return total_edits / denom
