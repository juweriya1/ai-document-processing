from decimal import Decimal

import pytest

from src.backend.utils.currency import (
    InvalidCurrencyError,
    normalize_amount,
    parse,
)


class TestParse:
    def test_pakistani_with_slash_dash(self):
        assert parse("Rs. 5,000/-") == Decimal("5000")

    def test_indian_lakh(self):
        assert parse("1,50,000.00") == Decimal("150000.00")

    def test_indian_crore(self):
        assert parse("1,00,00,000") == Decimal("10000000")

    def test_us_grouping(self):
        assert parse("$1,500,000.00") == Decimal("1500000.00")

    def test_plain_numeric(self):
        assert parse("1000.00") == Decimal("1000.00")

    def test_suffix_only(self):
        assert parse("500/-") == Decimal("500")

    def test_pkr_prefix(self):
        assert parse("PKR 2,500.50") == Decimal("2500.50")

    def test_whitespace_tolerant(self):
        assert parse("  Rs.  1,00,000  /-  ") == Decimal("100000")

    def test_numeric_passthrough(self):
        assert parse(1234.5) == Decimal("1234.5")

    def test_decimal_passthrough(self):
        assert parse(Decimal("42.00")) == Decimal("42.00")

    def test_none_raises(self):
        with pytest.raises(InvalidCurrencyError):
            parse(None)

    def test_empty_string_raises(self):
        with pytest.raises(InvalidCurrencyError):
            parse("")

    def test_garbage_raises(self):
        with pytest.raises(InvalidCurrencyError):
            parse("not-a-number")

    def test_trailing_group_must_be_three(self):
        with pytest.raises(InvalidCurrencyError):
            parse("1,50,00")


class TestNormalize:
    def test_returns_none_for_none(self):
        assert normalize_amount(None) is None

    def test_returns_none_for_blank(self):
        assert normalize_amount("   ") is None

    def test_returns_none_for_garbage(self):
        assert normalize_amount("xyz") is None

    def test_parses_valid(self):
        assert normalize_amount("Rs. 100") == Decimal("100")
