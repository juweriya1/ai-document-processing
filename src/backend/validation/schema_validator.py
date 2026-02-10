import re
from datetime import datetime

from sqlalchemy.orm import Session

from src.backend.db.crud import (
    get_extracted_fields,
    get_line_items,
    update_field_validation_status,
)

INVOICE_NUMBER_PATTERN = re.compile(r"^INV-\d{4}-\d{4}$")
DATE_FORMAT = "%Y-%m-%d"

VALIDATION_RULES = {
    "invoice_number": {
        "required": True,
        "pattern": INVOICE_NUMBER_PATTERN,
        "error": "Invoice number must match format INV-YYYY-NNNN",
    },
    "date": {
        "required": True,
        "date_format": DATE_FORMAT,
        "error": "Date must be in YYYY-MM-DD format",
    },
    "vendor_name": {
        "required": True,
        "error": "Vendor name is required",
    },
    "total_amount": {
        "required": True,
        "numeric": True,
        "error": "Total amount must be a valid number",
    },
}


def validate_field(field_name: str, field_value: str | None) -> tuple[str, str | None]:
    rule = VALIDATION_RULES.get(field_name)
    if rule is None:
        return "valid", None

    if rule.get("required") and (field_value is None or field_value.strip() == ""):
        return "invalid", f"{field_name} is required"

    if field_value is None or field_value.strip() == "":
        return "valid", None

    value = field_value.strip()

    if "pattern" in rule:
        if not rule["pattern"].match(value):
            return "invalid", rule["error"]

    if "date_format" in rule:
        try:
            datetime.strptime(value, rule["date_format"])
        except ValueError:
            return "invalid", rule["error"]

    if rule.get("numeric"):
        try:
            float(value)
        except ValueError:
            return "invalid", rule["error"]

    return "valid", None


def validate_line_item_reconciliation(
    total_amount_str: str | None, line_items: list,
) -> tuple[str, str | None]:
    if total_amount_str is None or not line_items:
        return "valid", None

    try:
        total = float(total_amount_str.strip())
    except (ValueError, AttributeError):
        return "valid", None

    items_sum = sum(item.total or 0.0 for item in line_items)

    if abs(items_sum - total) >= 0.01:
        return (
            "invalid",
            f"Line items sum ({items_sum:.2f}) does not match total ({total:.2f})",
        )
    return "valid", None


def validate_document_fields(db: Session, document_id: str) -> list[dict]:
    fields = get_extracted_fields(db, document_id)
    line_items = get_line_items(db, document_id)
    results = []

    total_amount_value = None

    for field in fields:
        status, error = validate_field(field.field_name, field.field_value)
        update_field_validation_status(db, field.id, status, error)
        results.append({
            "field_id": field.id,
            "field_name": field.field_name,
            "status": status,
            "error_message": error,
        })
        if field.field_name == "total_amount":
            total_amount_value = field.field_value

    if total_amount_value and line_items:
        recon_status, recon_error = validate_line_item_reconciliation(
            total_amount_value, line_items,
        )
        if recon_status == "invalid":
            for field in fields:
                if field.field_name == "total_amount":
                    update_field_validation_status(db, field.id, "invalid", recon_error)
                    for r in results:
                        if r["field_id"] == field.id:
                            r["status"] = "invalid"
                            r["error_message"] = recon_error
                    break

    return results
