from src.backend.analytics.widget_catalog import (
    APPROVED_WIDGETS,
    catalog_for_role,
    default_layout_for_role,
    validate_layout,
)


class TestCatalogForRole:
    def test_enterprise_user_does_not_see_reviewer_only_widgets(self):
        keys = {w["key"] for w in catalog_for_role("enterprise_user")}
        assert "iframe_powerbi" not in keys
        assert "grid_vendor_risk" not in keys
        assert "table_flagged" not in keys

    def test_reviewer_sees_reviewer_widgets(self):
        keys = {w["key"] for w in catalog_for_role("reviewer")}
        assert "iframe_powerbi" in keys
        assert "grid_vendor_risk" in keys

    def test_unknown_role_returns_empty(self):
        assert catalog_for_role("guest") == []


class TestValidateLayout:
    def test_strips_unknown_keys(self):
        layout = validate_layout(
            enabled=["kpi_total_spend", "not_a_real_widget"],
            order=["kpi_total_spend", "not_a_real_widget"],
            role="admin",
        )
        assert "not_a_real_widget" not in layout["enabled"]
        assert "not_a_real_widget" not in layout["order"]
        assert "kpi_total_spend" in layout["enabled"]

    def test_strips_widgets_not_allowed_for_role(self):
        # iframe_powerbi is reviewer/admin only
        layout = validate_layout(
            enabled=["iframe_powerbi", "kpi_total_spend"],
            order=["iframe_powerbi", "kpi_total_spend"],
            role="enterprise_user",
        )
        assert "iframe_powerbi" not in layout["enabled"]
        assert "iframe_powerbi" not in layout["order"]
        assert "kpi_total_spend" in layout["enabled"]

    def test_enabled_keys_are_appended_to_order_when_missing(self):
        layout = validate_layout(
            enabled=["kpi_total_spend"],
            order=[],  # empty order
            role="admin",
        )
        # every enabled key must appear in order
        for key in layout["enabled"]:
            assert key in layout["order"]

    def test_none_inputs_are_handled(self):
        layout = validate_layout(enabled=None, order=None, role="admin")
        assert layout == {"enabled": [], "order": []}


class TestDefaultLayoutForRole:
    def test_default_includes_only_default_true_widgets(self):
        layout = default_layout_for_role("admin")
        default_keys = {w["key"] for w in APPROVED_WIDGETS if w["default"] and "admin" in w["roles"]}
        assert set(layout["enabled"]) == default_keys

    def test_order_matches_catalog_order(self):
        layout = default_layout_for_role("admin")
        catalog_keys = [w["key"] for w in APPROVED_WIDGETS if "admin" in w["roles"]]
        assert layout["order"] == catalog_keys
