import pytest

from src.backend.db.crud import (
    create_document,
    store_extracted_fields,
    update_document_status,
)
from src.backend.analytics.trend_forecaster import (
    forecast_spend,
    _linear_forecast,
    _generate_future_months,
    _arima_forecast,
)


class TestLinearForecast:
    def test_increasing_trend(self):
        values = [100, 200, 300, 400, 500]
        forecast, method = _linear_forecast(values, 3)
        assert method == "linear"
        assert len(forecast) == 3
        assert forecast[0] > values[-1] - 50

    def test_flat_trend(self):
        values = [100, 100, 100]
        forecast, method = _linear_forecast(values, 2)
        assert len(forecast) == 2
        for v in forecast:
            assert abs(v - 100) < 10

    def test_no_negative_values(self):
        values = [50, 30, 10]
        forecast, _ = _linear_forecast(values, 5)
        assert all(v >= 0 for v in forecast)


class TestGenerateFutureMonths:
    def test_basic_increment(self):
        result = _generate_future_months("2025-01", 3)
        assert result == ["2025-02", "2025-03", "2025-04"]

    def test_year_rollover(self):
        result = _generate_future_months("2025-11", 3)
        assert result == ["2025-12", "2026-01", "2026-02"]


class TestForecastSpend:
    def test_empty_database(self, db_session):
        result = forecast_spend(db_session)
        assert result["historical"] == []
        assert result["forecast"] == []
        assert result["method"] == "none"

    def test_with_data_uses_linear(self, db_session):
        for i in range(3):
            doc = create_document(db_session, f"d{i}.pdf", f"d{i}.pdf", "application/pdf", 100)
            store_extracted_fields(db_session, doc.id, [
                {"field_name": "total_amount", "field_value": f"{(i + 1) * 100}.00", "confidence": 0.9},
            ])
            update_document_status(db_session, doc.id, "approved")

        result = forecast_spend(db_session, forecast_months=2)
        assert len(result["historical"]) > 0
        assert result["method"] == "linear"


class TestArimaForecast:
    def test_with_enough_data(self):
        values = [100, 150, 200, 250, 300, 350, 400]
        forecast, method = _arima_forecast(values, 3)
        assert method == "arima"
        assert len(forecast) == 3
        assert all(v >= 0 for v in forecast)
