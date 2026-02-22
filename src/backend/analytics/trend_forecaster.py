import numpy as np
from sqlalchemy.orm import Session

from src.backend.db.crud import get_spend_by_month


MIN_MONTHS_FOR_ARIMA = 6


def forecast_spend(db: Session, forecast_months: int = 3) -> dict:
    monthly_data = get_spend_by_month(db)

    if not monthly_data:
        return {
            "historical": [],
            "forecast": [],
            "method": "none",
            "message": "No historical data available",
        }

    values = [m["total_spend"] for m in monthly_data]

    if len(values) >= MIN_MONTHS_FOR_ARIMA:
        forecast_values, method = _arima_forecast(values, forecast_months)
    else:
        forecast_values, method = _linear_forecast(values, forecast_months)

    last_month = monthly_data[-1]["month"]
    forecast_months_list = _generate_future_months(last_month, forecast_months)

    return {
        "historical": monthly_data,
        "forecast": [
            {"month": m, "predicted_spend": round(v, 2)}
            for m, v in zip(forecast_months_list, forecast_values)
        ],
        "method": method,
    }


def _arima_forecast(values: list[float], steps: int) -> tuple[list[float], str]:
    try:
        import warnings
        from statsmodels.tsa.arima.model import ARIMA

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            model = ARIMA(values, order=(1, 1, 0))
            fitted = model.fit()
            prediction = fitted.forecast(steps=steps)
        return [max(0, float(v)) for v in prediction], "arima"
    except Exception:
        return _linear_forecast(values, steps)


def _linear_forecast(values: list[float], steps: int) -> tuple[list[float], str]:
    if len(values) < 2:
        last_val = values[-1] if values else 0.0
        return [last_val] * steps, "linear"
    x = np.arange(len(values), dtype=float)
    y = np.array(values, dtype=float)
    coeffs = np.polyfit(x, y, 1)
    forecast = []
    for i in range(steps):
        predicted = coeffs[0] * (len(values) + i) + coeffs[1]
        forecast.append(max(0, float(predicted)))
    return forecast, "linear"


def _generate_future_months(last_month: str, count: int) -> list[str]:
    year, month = map(int, last_month.split("-"))
    result = []
    for _ in range(count):
        month += 1
        if month > 12:
            month = 1
            year += 1
        result.append(f"{year:04d}-{month:02d}")
    return result
