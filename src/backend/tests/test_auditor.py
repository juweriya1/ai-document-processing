from decimal import Decimal

from src.backend.validation.auditor import FinancialAuditor


def test_math_passes_exact():
    auditor = FinancialAuditor()
    report = auditor.audit({"subtotal": "100.00", "tax": "15.00", "total_amount": "115.00"})
    assert report.ok
    assert report.delta == Decimal("0.00")


def test_math_passes_within_tolerance():
    auditor = FinancialAuditor()
    report = auditor.audit({"subtotal": "100.00", "tax": "15.005", "total_amount": "115.00"})
    assert report.ok


def test_math_fails_outside_tolerance():
    auditor = FinancialAuditor()
    report = auditor.audit({"subtotal": "100.00", "tax": "15.00", "total_amount": "120.00"})
    assert not report.ok
    assert report.reason == "math_mismatch"
    assert report.delta == Decimal("-5.00")


def test_pakistani_currency_math_pass():
    auditor = FinancialAuditor()
    report = auditor.audit({
        "subtotal": "Rs. 1,50,000/-",
        "tax": "Rs. 25,500/-",
        "total_amount": "Rs. 1,75,500/-",
    })
    assert report.ok
    assert report.total == Decimal("175500")


def test_partial_data_returns_ok_with_reason():
    auditor = FinancialAuditor()
    report = auditor.audit({"total_amount": "500", "subtotal": None, "tax": None})
    assert report.ok
    assert report.reason == "partial_data"


def test_unreadable_total():
    auditor = FinancialAuditor()
    report = auditor.audit({"total_amount": "banana", "subtotal": "10", "tax": "2"})
    assert not report.ok
    assert report.reason == "unreadable_total"


def test_missing_total():
    auditor = FinancialAuditor()
    report = auditor.audit({"subtotal": "10", "tax": "2"})
    assert not report.ok
    assert report.reason == "missing_total"
