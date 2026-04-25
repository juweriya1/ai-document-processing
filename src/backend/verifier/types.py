from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class VerifierReport:
    """Output of `PlausibilityVerifier.evaluate`.

    `score` is the *calibrated* probability (post isotonic regression) that
    the extraction is plausible — so e.g. score=0.9 means the verifier
    estimates a 90% empirical probability of correctness, not a raw model
    output. `threshold` is the F1-optimal cutoff chosen at training time;
    `ok` reflects `score >= threshold`.

    `skipped=True` indicates the verifier was unavailable (no model artifact
    on disk yet, or feature extraction raised). The pipeline treats a
    skipped report as non-blocking — math-only gating still applies.
    """

    ok: bool
    score: float | None
    threshold: float | None
    reason: str | None
    top_features: list[tuple[str, float]] = field(default_factory=list)
    skipped: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "score": self.score,
            "threshold": self.threshold,
            "reason": self.reason,
            "top_features": [
                {"name": name, "contribution": contrib}
                for name, contrib in self.top_features
            ],
            "skipped": self.skipped,
        }

    @classmethod
    def skipped_report(cls, reason: str) -> "VerifierReport":
        """Construct a non-blocking 'verifier unavailable' report."""
        return cls(
            ok=True,
            score=None,
            threshold=None,
            reason=reason,
            top_features=[],
            skipped=True,
        )
