from sqlalchemy.orm import Session

from src.backend.analytics.anomaly_detector import detect_anomalies
from src.backend.analytics.risk_scorer import score_suppliers
from src.backend.analytics.trend_forecaster import forecast_spend


def generate_predictions(db: Session) -> dict:
    risk_scores = score_suppliers(db)
    forecast = forecast_spend(db, forecast_months=3)
    anomalies = detect_anomalies(db)
    insights = _generate_text_insights(risk_scores, forecast, anomalies)

    return {
        "risk_scores": risk_scores,
        "spend_forecast": forecast,
        "anomalies": anomalies,
        "insights": insights,
    }


def _generate_text_insights(
    risk_scores: list[dict],
    forecast: dict,
    anomalies: list[dict],
) -> list[str]:
    insights = []

    high_risk = [s for s in risk_scores if s.get("risk_score", 0) >= 60]
    if high_risk:
        names = ", ".join(s["supplier_name"] for s in high_risk)
        insights.append(f"High-risk suppliers detected: {names}. Consider additional review.")

    if forecast.get("forecast"):
        last_historical = forecast["historical"][-1]["total_spend"] if forecast["historical"] else 0
        last_forecast = forecast["forecast"][-1]["predicted_spend"]
        if last_forecast > last_historical * 1.2:
            insights.append("Spend is projected to increase significantly. Review budget allocations.")
        elif last_forecast < last_historical * 0.8:
            insights.append("Spend is projected to decrease. Verify supplier activity.")

    if anomalies:
        insights.append(
            f"{len(anomalies)} anomalous document(s) detected. Review flagged documents for potential issues."
        )

    if not insights:
        insights.append("No significant concerns detected. All metrics within normal range.")

    return insights
