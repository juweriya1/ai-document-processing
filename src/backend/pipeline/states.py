from __future__ import annotations

from enum import Enum


class DocState(str, Enum):
    RECEIVED = "received"
    PREPROCESSED = "preprocessed"
    LOCALLY_PARSED = "locally_parsed"
    VLM_RECONCILED = "vlm_reconciled"
    VERIFIED = "verified"
    FLAGGED = "flagged"
    FAILED = "failed"


_VALID_TRANSITIONS: dict[DocState, set[DocState]] = {
    DocState.RECEIVED: {DocState.PREPROCESSED, DocState.FAILED},
    DocState.PREPROCESSED: {DocState.LOCALLY_PARSED, DocState.VLM_RECONCILED, DocState.FAILED},
    DocState.LOCALLY_PARSED: {DocState.VERIFIED, DocState.VLM_RECONCILED, DocState.FLAGGED, DocState.FAILED},
    DocState.VLM_RECONCILED: {DocState.VERIFIED, DocState.FLAGGED, DocState.FAILED},
    DocState.VERIFIED: set(),
    DocState.FLAGGED: set(),
    DocState.FAILED: set(),
}

_DB_STATUS: dict[DocState, str] = {
    DocState.RECEIVED: "uploaded",
    DocState.PREPROCESSED: "preprocessing",
    DocState.LOCALLY_PARSED: "locally_parsed",
    DocState.VLM_RECONCILED: "vlm_reconciled",
    DocState.VERIFIED: "verified",
    DocState.FLAGGED: "review_pending",
    DocState.FAILED: "failed",
}


def db_status_for(state: DocState) -> str:
    return _DB_STATUS[state]


def assert_transition(from_state: DocState, to_state: DocState) -> None:
    if to_state not in _VALID_TRANSITIONS[from_state]:
        raise ValueError(f"Invalid transition: {from_state.value} -> {to_state.value}")
