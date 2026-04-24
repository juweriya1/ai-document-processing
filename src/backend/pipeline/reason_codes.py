from __future__ import annotations

from enum import Enum


class ReasonCode(str, Enum):
    """Standardized machine-readable reasons for pipeline transitions.

    Persisted into Document.traceability_log so downstream dashboards and
    reviewers can filter on a stable vocabulary instead of free-form strings.
    """

    LOCAL_OK = "local_ok"
    LOCAL_IMPORT_ERROR = "local_import_error"
    LOCAL_RUNTIME_ERROR = "local_runtime_error"
    LOCAL_EMPTY_EXTRACTION = "local_empty_extraction"
    LOCAL_LOW_CONFIDENCE = "local_low_confidence"
    LOCAL_AUDIT_FAIL = "local_audit_fail"

    VLM_OK = "vlm_ok"
    VLM_UNAVAILABLE = "vlm_unavailable"
    VLM_RUNTIME_ERROR = "vlm_runtime_error"
    VLM_AUDIT_FAIL = "vlm_audit_fail"
    VLM_RETRIED = "vlm_retried"

    PREPROCESS_FAIL = "preprocess_fail"
    PERSIST_FAIL = "persist_fail"
    DOCUMENT_NOT_FOUND = "document_not_found"
    INVALID_STATE = "invalid_state"
