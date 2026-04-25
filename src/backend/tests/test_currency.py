from decimal import Decimal

import pytest

from src.backend.utils.currency import (
    InvalidCurrencyError,
    normalize_amount,
    parse,
)


class TestParse:
    def test_dollar_us_grouping(self):
        assert parse("$1,500,000.00") == Decimal("1500000.00")

    def test_euro_prefix(self):
        assert parse("€1,234.56") == Decimal("1234.56")

    def test_gbp_prefix(self):
        assert parse("£500") == Decimal("500")

    def test_usd_suffix(self):
        assert parse("2500.50 USD") == Decimal("2500.50")

    def test_plain_numeric(self):
        assert parse("1000.00") == Decimal("1000.00")

    def test_whitespace_tolerant(self):
        assert parse("  $  1,500.00  ") == Decimal("1500.00")

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

    def test_lakh_grouping_not_supported(self):
        """Indian/Pakistani lakh-style grouping (1,50,000) is rejected
        because we no longer target that distribution. Standard 3-digit
        Western groups only."""
        with pytest.raises(InvalidCurrencyError):
            parse("1,50,000")

    def test_trailing_group_must_be_three(self):
        with pytest.raises(InvalidCurrencyError):
            parse("1,500,00")


class TestNormalize:
    def test_returns_none_for_none(self):
        assert normalize_amount(None) is None

    def test_returns_none_for_blank(self):
        assert normalize_amount("   ") is None

    def test_returns_none_for_garbage(self):
        assert normalize_amount("xyz") is None

    def test_parses_valid(self):
        assert normalize_amount("$100") == Decimal("100")
