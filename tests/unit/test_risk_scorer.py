import pytest

from src.backend.db.crud import upsert_supplier_metric, get_all_supplier_metrics
from src.backend.analytics.risk_scorer import (
    score_suppliers,
    _heuristic_risk_scores,
    _compute_heuristic_score,
    _ml_risk_scores,
    MIN_SUPPLIERS_FOR_ML,
)


class TestComputeHeuristicScore:
    def test_high_confidence_low_risk(self):
        score = _compute_heuristic_score(0.95, 10)
        assert score < 30

    def test_low_confidence_high_risk(self):
        score = _compute_heuristic_score(0.50, 1)
        assert score > 40

    def test_score_bounded_0_100(self):
        score = _compute_heuristic_score(1.0, 100)
        assert 0 <= score <= 100
        score2 = _compute_heuristic_score(0.0, 0)
        assert 0 <= score2 <= 100


class TestHeuristicRiskScores:
    def test_returns_scores_for_all_suppliers(self):
        data = [
            {"supplier_name": "A", "total_documents": 5, "avg_confidence": 0.9},
            {"supplier_name": "B", "total_documents": 1, "avg_confidence": 0.5},
        ]
        result = _heuristic_risk_scores(data)
        assert len(result) == 2
        assert all(r["method"] == "heuristic" for r in result)
        assert result[0]["risk_score"] < result[1]["risk_score"]


class TestMlRiskScores:
    def test_with_varied_data(self):
        data = [
            {"supplier_name": f"S{i}", "total_documents": i + 1, "avg_confidence": 0.5 + i * 0.08}
            for i in range(6)
        ]
        result = _ml_risk_scores(data)
        assert len(result) == 6
        assert all("risk_score" in r for r in result)

    def test_uniform_data_falls_back_to_heuristic(self):
        data = [
            {"supplier_name": f"S{i}", "total_documents": 5, "avg_confidence": 0.9}
            for i in range(6)
        ]
        result = _ml_risk_scores(data)
        assert len(result) == 6
        assert all(r["method"] == "heuristic" for r in result)


class TestScoreSuppliers:
    def test_empty_database(self, db_session):
        result = score_suppliers(db_session)
        assert result == []

    def test_heuristic_fallback_few_suppliers(self, db_session):
        upsert_supplier_metric(db_session, "Vendor A", 3, 0.85)
        upsert_supplier_metric(db_session, "Vendor B", 1, 0.60)
        result = score_suppliers(db_session)
        assert len(result) == 2
        assert all(r["method"] == "heuristic" for r in result)

    def test_persists_risk_scores(self, db_session):
        upsert_supplier_metric(db_session, "Vendor A", 5, 0.90)
        score_suppliers(db_session)
        metrics = get_all_supplier_metrics(db_session)
        assert metrics[0].risk_score is not None
