class LineItem {
    description string?
    quantity string?
    unit_price string?
    total string?
}

class InvoiceExtraction {
    invoice_number string?
    date string?
    vendor_name string?
    subtotal string?
    tax string?
    total_amount string?
    line_items LineItem[]?
}

function ExtractInvoice(image: image) -> InvoiceExtraction {
    client GeminiFlash
    prompt #"
        You are extracting fields from an invoice.

        Return a JSON object matching the InvoiceExtraction schema. Preserve
        the currency markers exactly as they appear on the invoice — do NOT
        strip "Rs.", "/-", lakh-style commas ("1,50,000"), or currency prefixes.
        Use null (not empty string) for any field that is not present.

        Format date as YYYY-MM-DD when the date is unambiguous; otherwise
        pass through the original string.

        Capture every line item visible on the invoice with its description,
        quantity, unit_price, and total. Preserve currency markers in line
        item amounts as well.

        {{ ctx.output_format }}

        {{ _.role("user") }}
        {{ image }}
    "#
}

function ReconcileInvoice(image: image, error_context: string) -> InvoiceExtraction {
    client GeminiFlash
    prompt #"
        You are performing a TARGETED RE-SCAN of a financial document.

        A prior extraction failed strict-Decimal math reconciliation with the
        following diagnostic from our auditor:

        {{ error_context }}

        Re-extract the entire invoice, but pay EXTRA attention to the field(s)
        named in the diagnostic above. In particular, watch for:

          - Decimal-point placement: misreads like "12.50" → "1250" or
            "125.0" are the single most common failure mode.
          - Currency prefixes and suffixes: "Rs.", "PKR", "INR", "USD", "$",
            "/-", "/=" — preserve EXACTLY as printed.
          - Lakh-style grouping: "1,50,000" is one-hundred-fifty-thousand
            (one-and-a-half lakh), NOT 150,000 written in Western grouping.
          - OCR digit confusions: 0↔O, 1↔I↔l, 8↔B, 5↔S, 6↔G.
          - Sign / placement of the tax row — sometimes "Tax" includes an
            embedded "-" or is placed under the subtotal in a visually
            ambiguous way.

        Your output must satisfy the invariant:
            subtotal + tax == total_amount     (within 0.01 rounding)

        Capture every line item visible with its description, quantity,
        unit_price, and total. Preserve currency markers in line-item
        amounts. Use null (not empty string) for fields that are genuinely
        not present on the document.

        {{ ctx.output_format }}

        {{ _.role("user") }}
        {{ image }}
    "#
}

test pakistani_invoice {
    functions [ExtractInvoice]
    args {
        image { url "https://example.com/invoice_pk.png" }
    }
}
