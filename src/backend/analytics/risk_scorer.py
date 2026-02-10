import numpy as np
from sqlalchemy.orm import Session

from src.backend.db.crud import get_all_supplier_metrics, upsert_supplier_metric


MIN_SUPPLIERS_FOR_ML = 5


def score_suppliers(db: Session) -> list[dict]:
    metrics = get_all_supplier_metrics(db)
    if not metrics:
        return []

    supplier_data = []
    for m in metrics:
        supplier_data.append({
            "supplier_name": m.supplier_name,
            "total_documents": m.total_documents,
            "avg_confidence": m.avg_confidence if m.avg_confidence is not None else 0.0,
        })

    if len(supplier_data) >= MIN_SUPPLIERS_FOR_ML:
        scored = _ml_risk_scores(supplier_data)
    else:
        scored = _heuristic_risk_scores(supplier_data)

    for item in scored:
        upsert_supplier_metric(
            db,
            supplier_name=item["supplier_name"],
            total_documents=item["total_documents"],
            avg_confidence=item["avg_confidence"],
            risk_score=item["risk_score"],
        )

    return scored


def _ml_risk_scores(supplier_data: list[dict]) -> list[dict]:
    from sklearn.ensemble import RandomForestClassifier

    features = []
    for s in supplier_data:
        features.append([s["avg_confidence"], s["total_documents"]])
    X = np.array(features)

    # Generate synthetic training labels based on heuristic for training
    y = []
    for s in supplier_data:
        heuristic = _compute_heuristic_score(s["avg_confidence"], s["total_documents"])
        y.append(1 if heuristic >= 50 else 0)

    # If all labels are the same, fall back to heuristic
    if len(set(y)) < 2:
        return _heuristic_risk_scores(supplier_data)

    clf = RandomForestClassifier(n_estimators=50, random_state=42)
    clf.fit(X, y)

    probabilities = clf.predict_proba(X)
    risk_col_idx = list(clf.classes_).index(1) if 1 in clf.classes_ else 0

    results = []
    for i, s in enumerate(supplier_data):
        risk_prob = probabilities[i][risk_col_idx]
        risk_score = round(risk_prob * 100, 2)
        results.append({
            "supplier_name": s["supplier_name"],
            "total_documents": s["total_documents"],
            "avg_confidence": s["avg_confidence"],
            "risk_score": risk_score,
            "method": "random_forest",
        })

    return results


def _heuristic_risk_scores(supplier_data: list[dict]) -> list[dict]:
    results = []
    for s in supplier_data:
        risk_score = _compute_heuristic_score(s["avg_confidence"], s["total_documents"])
        results.append({
            "supplier_name": s["supplier_name"],
            "total_documents": s["total_documents"],
            "avg_confidence": s["avg_confidence"],
            "risk_score": round(risk_score, 2),
            "method": "heuristic",
        })
    return results


def _compute_heuristic_score(avg_confidence: float, total_documents: int) -> float:
    confidence_risk = (1.0 - avg_confidence) * 60
    experience_factor = min(total_documents / 10, 1.0)
    inexperience_risk = (1.0 - experience_factor) * 40
    return max(0, min(100, confidence_risk + inexperience_risk))
