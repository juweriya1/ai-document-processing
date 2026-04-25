"""Self-supervised plausibility verifier.

Trains a learned classifier on synthetic corruptions of clean extractions.
Runs alongside the deterministic FinancialAuditor as a parallel gate: both
must pass for an extraction to be declared verified.

Public surface:
- PlausibilityVerifier: inference-time entry point (loads latest model artifact)
- VerifierReport: structured result returned by .evaluate()

The trainer module and CLI scripts (`scripts/train_verifier.py`,
`scripts/eval_verifier.py`) are training-time only and do not need to be
imported in the request path.
"""

from src.backend.verifier.predictor import PlausibilityVerifier
from src.backend.verifier.types import VerifierReport

__all__ = ["PlausibilityVerifier", "VerifierReport"]
