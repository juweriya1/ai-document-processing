import pytest

from src.backend.pipeline.states import DocState, assert_transition, db_status_for


def test_db_status_mapping():
    assert db_status_for(DocState.RECEIVED) == "uploaded"
    assert db_status_for(DocState.VERIFIED) == "verified"
    assert db_status_for(DocState.FLAGGED) == "review_pending"


def test_valid_transitions():
    assert_transition(DocState.RECEIVED, DocState.PREPROCESSED)
    assert_transition(DocState.LOCALLY_PARSED, DocState.VERIFIED)
    assert_transition(DocState.LOCALLY_PARSED, DocState.VLM_RECONCILED)


def test_invalid_transition_raises():
    with pytest.raises(ValueError):
        assert_transition(DocState.VERIFIED, DocState.RECEIVED)
    with pytest.raises(ValueError):
        assert_transition(DocState.RECEIVED, DocState.VERIFIED)
