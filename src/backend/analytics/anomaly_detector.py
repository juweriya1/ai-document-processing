import numpy as np
from sqlalchemy.orm import Session

from src.backend.db.crud import get_documents_with_confidence_stats


MIN_DOCS_FOR_ISOLATION_FOREST = 10


def detect_anomalies(db: Session) -> list[dict]:
    doc_stats = get_documents_with_confidence_stats(db)

    if not doc_stats:
        return []

    entries = []
    for d in doc_stats:
        amount = d["total_amount"] if d["total_amount"] is not None else 0.0
        confidence = d["avg_confidence"] if d["avg_confidence"] is not None else 0.0
        entries.append({
            "document_id": d["document_id"],
            "filename": d["filename"],
            "total_amount": amount,
            "avg_confidence": confidence,
            "correction_count": d["correction_count"],
        })

    if len(entries) >= MIN_DOCS_FOR_ISOLATION_FOREST:
        return _isolation_forest_detect(entries)
    else:
        return _zscore_detect(entries)


def _isolation_forest_detect(entries: list[dict]) -> list[dict]:
    from sklearn.ensemble import IsolationForest

    features = np.array([
        [e["total_amount"], e["avg_confidence"], e["correction_count"]]
        for e in entries
    ])

    clf = IsolationForest(contamination=0.1, random_state=42)
    predictions = clf.fit_predict(features)
    scores = clf.decision_function(features)

    anomalies = []
    for i, (pred, score) in enumerate(zip(predictions, scores)):
        if pred == -1:
            reasons = _build_reasons(entries[i], entries)
            anomalies.append({
                "document_id": entries[i]["document_id"],
                "filename": entries[i]["filename"],
                "anomaly_score": round(float(-score), 4),
                "reasons": reasons,
                "method": "isolation_forest",
            })

    return anomalies


def _zscore_detect(entries: list[dict]) -> list[dict]:
    if len(entries) < 2:
        return []

    amounts = [e["total_amount"] for e in entries]
    confidences = [e["avg_confidence"] for e in entries]

    mean_amount = np.mean(amounts)
    std_amount = np.std(amounts) if len(amounts) > 1 else 0.0
    mean_conf = np.mean(confidences)
    std_conf = np.std(confidences) if len(confidences) > 1 else 0.0

    anomalies = []
    for entry in entries:
        reasons = []
        is_anomaly = False

        if std_amount > 0:
            z_amount = abs(entry["total_amount"] - mean_amount) / std_amount
            if z_amount > 2:
                reasons.append(f"Unusual amount: ${entry['total_amount']:.2f} (z-score: {z_amount:.2f})")
                is_anomaly = True

        if std_conf > 0:
            z_conf = abs(entry["avg_confidence"] - mean_conf) / std_conf
            if z_conf > 2:
                reasons.append(f"Unusual confidence: {entry['avg_confidence']:.4f} (z-score: {z_conf:.2f})")
                is_anomaly = True

        if entry["correction_count"] > 3:
            reasons.append(f"High correction count: {entry['correction_count']}")
            is_anomaly = True

        if is_anomaly:
            anomalies.append({
                "document_id": entry["document_id"],
                "filename": entry["filename"],
                "anomaly_score": round(len(reasons) / 3.0, 4),
                "reasons": reasons,
                "method": "zscore",
            })

    return anomalies


def _build_reasons(entry: dict, all_entries: list[dict]) -> list[str]:
    reasons = []
    amounts = [e["total_amount"] for e in all_entries]
    confidences = [e["avg_confidence"] for e in all_entries]

    mean_amount = np.mean(amounts)
    std_amount = np.std(amounts)
    if std_amount > 0:
        z = abs(entry["total_amount"] - mean_amount) / std_amount
        if z > 1.5:
            reasons.append(f"Unusual amount: ${entry['total_amount']:.2f}")

    mean_conf = np.mean(confidences)
    std_conf = np.std(confidences)
    if std_conf > 0:
        z = abs(entry["avg_confidence"] - mean_conf) / std_conf
        if z > 1.5:
            reasons.append(f"Unusual confidence: {entry['avg_confidence']:.4f}")

    if entry["correction_count"] > 2:
        reasons.append(f"High corrections: {entry['correction_count']}")

    if not reasons:
        reasons.append("Statistical outlier detected by model")

    return reasons
