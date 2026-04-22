import re


def extract_merchant_name(text: str):
    lines = [l.strip() for l in text.split("\n") if l.strip()]

    skip_words = {
        "invoice", "receipt", "tax", "bill", "order", "cash", "total",
        "date", "tel", "phone", "www", "http"
    }

    for line in lines[:8]:
        if len(line) < 3:
            continue
        if any(char.isdigit() for char in line) and len(line) < 6:
            continue

        low = line.lower()
        if any(w in low for w in skip_words):
            continue

        return line

    return None


def extract_invoice_number(text: str):
    patterns = [
        r"Invoice\s*#\s*([A-Za-z0-9\-_/]+)",
        r"Invoice\s*No\.?\s*[:\-]?\s*([A-Za-z0-9\-_/]+)",
        r"INVOICE\s*NO\.?\s*[:\-]?\s*([A-Za-z0-9\-_/]+)",
        r"Document\s*(?:No|Number)\s*[:\-]?\s*([A-Za-z0-9\-_/]+)",
        r"INV\s*#?\s*([A-Za-z0-9\-_/]+)",
    ]

    for p in patterns:
        match = re.search(p, text, re.IGNORECASE)
        if match:
            val = match.group(1).strip()
            val = re.split(r"\s|\n|\|", val)[0]
            return val

    return None


def extract_date(text: str):
    labeled_patterns = [
        r"Date\s*[:\-]?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
        r"Invoice\s*Date\s*[:\-]?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
        r"Date\s*[:\-]?\s*([A-Za-z]{3,9}\s*\d{1,2},?\s*\d{4})",
        r"Invoice\s*Date\s*[:\-]?\s*([A-Za-z]{3,9}\s*\d{1,2},?\s*\d{4})",
    ]

    generic_patterns = [
        r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b",
        r"\b\d{1,2}-[A-Za-z]{3}-\d{2,4}\b",
    ]

    for p in labeled_patterns:
        match = re.search(p, text, re.IGNORECASE)
        if match:
            return match.group(1)

    for p in generic_patterns:
        match = re.search(p, text)
        if match:
            return match.group(0)

    return None


def extract_total_amount(text: str):
    patterns = [
        r"Grand\s*Total\s*[:\-]?\s*([\d,]+\.\d{2})",
        r"Payable\s*[:\-]?\s*([\d,]+\.\d{2})",
        r"Total\s*Amount\s*[:\-]?\s*([\d,]+\.\d{2})",
        r"TOTAL\s*RM\s*([\d,]+\.\d{2})",
        r"Total\s*[:\-]?\s*([\d,]+\.\d{2})",
    ]

    candidates = []

    for p in patterns:
        for m in re.finditer(p, text, re.IGNORECASE):
            val = m.group(1).replace(",", "")
            try:
                candidates.append(float(val))
            except:
                pass

    if not candidates:
        return None

    return f"{max(candidates):.2f}"


# OPTIONAL FIELDS (light extraction only)

def extract_tax_amount(text: str):
    patterns = [
        r"Tax\s*@\s*\d+%[:\-]?\s*([\d,]+\.\d{2})",
        r"GST[:\-]?\s*([\d,]+\.\d{2})",
        r"SST[:\-]?\s*([\d,]+\.\d{2})",
        r"Sales\s*Tax[:\-]?\s*([\d,]+\.\d{2})",
    ]

    for p in patterns:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            return m.group(1)

    return None


def extract_subtotal(text: str):
    patterns = [
        r"Sub\s*Total[:\-]?\s*([\d,]+\.\d{2})",
        r"Subtotal[:\-]?\s*([\d,]+\.\d{2})",
    ]

    for p in patterns:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            return m.group(1)

    return None


def extract_discount(text: str):
    patterns = [
        r"Discount[:\-]?\s*([\d,]+\.\d{2})",
    ]

    for p in patterns:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            return m.group(1)

    return None


def extract_cash_tendered(text: str):
    patterns = [
        r"Cash\s*Tendered[:\-]?\s*([\d,]+\.\d{2})",
        r"CASH[:\-]?\s*([\d,]+\.\d{2})",
    ]

    for p in patterns:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            return m.group(1)

    return None


def extract_change(text: str):
    patterns = [
        r"Change[:\-]?\s*([\d,]+\.\d{2})",
    ]

    for p in patterns:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            return m.group(1)

    return None


def extract_fields(text: str) -> dict:
    return {
        "merchant_name": extract_merchant_name(text),
        "invoice_number": extract_invoice_number(text),
        "date": extract_date(text),
        "total_amount": extract_total_amount(text),

        # optional fields
        "currency": None,
        "tax_amount": extract_tax_amount(text),
        "subtotal": extract_subtotal(text),
        "discount": extract_discount(text),
        "cash_tendered": extract_cash_tendered(text),
        "change": extract_change(text),
    }