REQUIRED_FIELDS = [
    "merchant_name",
    "invoice_number",
    "date",
    "total_amount",
]

OPTIONAL_FIELDS = [
    "currency",
    "tax_amount",
    "subtotal",
    "discount",
    "cash_tendered",
    "change",
]

# core extraction output format
SCHEMA = {
    "merchant_name": None,     # top-of-receipt identity, messy allowed
    "invoice_number": None,    # order id / bill id / invoice / doc no
    "date": None,              # raw string, no forced format yet
    "total_amount": None,      # final payable amount (NOT subtotal)
    
    "currency": None,         # "PKR", "RM", etc if visible
    
    "tax_amount": None,       # total tax or VAT/SST if clearly present
    "subtotal": None,         # pre-tax total if explicitly labeled
    "discount": None,         # total discount if shown
    
    "cash_tendered": None,    # cash given (only if present)
    "change": None,           # change returned (only if present)
}