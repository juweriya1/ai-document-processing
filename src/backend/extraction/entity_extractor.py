# =============================================================================
# DEPRECATED  —  legacy code retired on 2026-04-24.
#
# spaCy NER + regex entity extractor built on top of the legacy OCREngine
# result. Superseded by src/backend/extraction/heuristics.py (used by
# LocalExtractor) and the BAML ExtractInvoice / ReconcileInvoice functions
# for structured extraction.
#
# The implementation below is preserved as comments for reference and git
# history. Nothing in the active pipeline imports from this module; any
# accidental `from ... import X` will raise ImportError, which is intentional.
# =============================================================================

# import re
# from dataclasses import dataclass, field
#
# from src.backend.ocr.ocr_engine import DocumentOCRResult
#
#
# @dataclass
# class ExtractedData:
#     fields: list[dict] = field(default_factory=list)
#     line_items: list[dict] = field(default_factory=list)
#
#
# class EntityExtractor:
#     def __init__(self):
#         import spacy
#         self._nlp = spacy.load("en_core_web_sm")
#
#     def extract(self, ocr_result: DocumentOCRResult) -> ExtractedData:
#         text = ocr_result.full_text
#         fields = []
#
#         inv_value, inv_conf = self._extract_invoice_number(text)
#         if inv_value:
#             fields.append({"field_name": "invoice_number", "field_value": inv_value, "confidence": inv_conf})
#
#         date_value, date_conf = self._extract_date(text)
#         if date_value:
#             fields.append({"field_name": "date", "field_value": date_value, "confidence": date_conf})
#
#         vendor_value, vendor_conf = self._extract_vendor_name(text)
#         if vendor_value:
#             fields.append({"field_name": "vendor_name", "field_value": vendor_value, "confidence": vendor_conf})
#
#         amounts = self._extract_amounts(text)
#         if amounts.get("total_amount"):
#             fields.append({
#                 "field_name": "total_amount",
#                 "field_value": amounts["total_amount"],
#                 "confidence": amounts.get("confidence", 0.88),
#             })
#         if amounts.get("subtotal"):
#             fields.append({
#                 "field_name": "subtotal",
#                 "field_value": amounts["subtotal"],
#                 "confidence": amounts.get("confidence", 0.88),
#             })
#         if amounts.get("tax"):
#             fields.append({
#                 "field_name": "tax",
#                 "field_value": amounts["tax"],
#                 "confidence": amounts.get("confidence", 0.88),
#             })
#
#         line_items = self._extract_line_items(ocr_result.tables)
#
#         return ExtractedData(fields=fields, line_items=line_items)
#
#     @staticmethod
#     def _extract_invoice_number(text: str) -> tuple[str | None, float]:
#         pattern = r"(?:Invoice|INV)[#:\s\-]*([A-Z]{0,4}-?\d{4}-?\d{3,5}|\d{4,10})"
#         match = re.search(pattern, text, re.IGNORECASE)
#         if match:
#             return match.group(0).strip(), 0.92
#         return None, 0.0
#
#     @staticmethod
#     def _extract_date(text: str) -> tuple[str | None, float]:
#         # Try YYYY-MM-DD
#         iso_pattern = r"\d{4}-\d{2}-\d{2}"
#         # Try MM/DD/YYYY or DD/MM/YYYY
#         slash_pattern = r"\d{1,2}/\d{1,2}/\d{4}"
#         # Try Month DD, YYYY
#         written_pattern = r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2},?\s+\d{4}"
#
#         # Look near keywords first
#         keyword_pattern = r"(?:Date|Invoice\s*Date|Due\s*Date|Issued)[:\s]*"
#
#         for date_re in [iso_pattern, slash_pattern, written_pattern]:
#             contextual = keyword_pattern + r"(" + date_re + r")"
#             match = re.search(contextual, text, re.IGNORECASE)
#             if match:
#                 return _normalize_date(match.group(1)), 0.93
#
#         # Fall back to standalone date
#         for date_re in [iso_pattern, slash_pattern, written_pattern]:
#             match = re.search(date_re, text, re.IGNORECASE)
#             if match:
#                 return _normalize_date(match.group(0)), 0.90
#
#         return None, 0.0
#
#     def _extract_vendor_name(self, text: str) -> tuple[str | None, float]:
#         doc = self._nlp(text[:2000])  # limit to first 2000 chars for performance
#
#         org_entities = [ent.text.strip() for ent in doc.ents if ent.label_ == "ORG"]
#         if not org_entities:
#             return None, 0.0
#
#         # Prioritize orgs near vendor keywords
#         vendor_keywords = ["from", "vendor", "supplier", "bill from", "sold by", "company"]
#         text_lower = text.lower()
#         for keyword in vendor_keywords:
#             idx = text_lower.find(keyword)
#             if idx == -1:
#                 continue
#             context_window = text[idx:idx + 200]
#             context_doc = self._nlp(context_window)
#             for ent in context_doc.ents:
#                 if ent.label_ == "ORG":
#                     return ent.text.strip(), 0.88
#
#         # Return first ORG entity as fallback
#         return org_entities[0], 0.85
#
#     @staticmethod
#     def _extract_amounts(text: str) -> dict:
#         amount_pattern = r"\$?\s*([\d,]+\.\d{2})"
#         results = {}
#
#         # Total amount - search near keywords
#         total_keywords = [
#             r"(?:(?<!\w)Total\s*(?:Amount\s*)?(?:Due)?|Amount\s*Due|Balance\s*Due|Grand\s*Total)",
#             r"(?:Subtotal|Sub\s*Total)",
#             r"(?:(?<!\w)Tax|VAT|GST|Sales\s*Tax)",
#         ]
#         field_names = ["total_amount", "subtotal", "tax"]
#
#         for keywords, field_name in zip(total_keywords, field_names):
#             pattern = keywords + r"[:\s]*" + amount_pattern
#             match = re.search(pattern, text, re.IGNORECASE)
#             if match:
#                 value = match.group(1).replace(",", "")
#                 results[field_name] = value
#
#         # If no total found, try to find the largest amount
#         if "total_amount" not in results:
#             all_amounts = re.findall(amount_pattern, text)
#             if all_amounts:
#                 amounts_float = []
#                 for a in all_amounts:
#                     try:
#                         amounts_float.append(float(a.replace(",", "")))
#                     except ValueError:
#                         pass
#                 if amounts_float:
#                     results["total_amount"] = f"{max(amounts_float):.2f}"
#
#         results["confidence"] = 0.88
#         return results
#
#     @staticmethod
#     def _extract_line_items(tables: list[list[list[str]]]) -> list[dict]:
#         header_patterns = {
#             "description": ["description", "item", "product", "service", "name"],
#             "quantity": ["qty", "quantity", "units", "count"],
#             "unit_price": ["price", "unit price", "rate", "unit cost"],
#             "total": ["total", "amount", "line total", "ext"],
#         }
#
#         line_items = []
#
#         for table in tables:
#             if len(table) < 2:
#                 continue
#
#             header_row = table[0]
#             col_mapping = {}
#
#             for col_idx, header_cell in enumerate(header_row):
#                 header_lower = header_cell.strip().lower() if header_cell else ""
#                 for field_name, patterns in header_patterns.items():
#                     if field_name in col_mapping:
#                         continue
#                     for pattern in patterns:
#                         if pattern in header_lower:
#                             col_mapping[field_name] = col_idx
#                             break
#
#             if not col_mapping:
#                 continue
#
#             for row in table[1:]:
#                 item = {}
#                 for field_name, col_idx in col_mapping.items():
#                     if col_idx < len(row):
#                         cell_value = row[col_idx].strip() if row[col_idx] else ""
#                         if field_name in ("quantity", "unit_price", "total"):
#                             try:
#                                 item[field_name] = float(cell_value.replace(",", "").replace("$", ""))
#                             except (ValueError, AttributeError):
#                                 item[field_name] = 0.0
#                         else:
#                             item[field_name] = cell_value
#
#                 if item.get("description"):
#                     item.setdefault("quantity", 0.0)
#                     item.setdefault("unit_price", 0.0)
#                     item.setdefault("total", 0.0)
#                     line_items.append(item)
#
#         return line_items
#
#
# def _normalize_date(date_str: str) -> str:
#     import re as re_mod
#     date_str = date_str.strip()
#
#     # Already YYYY-MM-DD
#     if re_mod.match(r"\d{4}-\d{2}-\d{2}$", date_str):
#         return date_str
#
#     # MM/DD/YYYY
#     slash_match = re_mod.match(r"(\d{1,2})/(\d{1,2})/(\d{4})$", date_str)
#     if slash_match:
#         month, day, year = slash_match.groups()
#         return f"{year}-{int(month):02d}-{int(day):02d}"
#
#     # Written form: Month DD, YYYY
#     months = {
#         "jan": "01", "feb": "02", "mar": "03", "apr": "04",
#         "may": "05", "jun": "06", "jul": "07", "aug": "08",
#         "sep": "09", "oct": "10", "nov": "11", "dec": "12",
#     }
#     written_match = re_mod.match(r"([A-Za-z]+)\.?\s+(\d{1,2}),?\s+(\d{4})$", date_str)
#     if written_match:
#         month_str, day, year = written_match.groups()
#         month_num = months.get(month_str[:3].lower(), "01")
#         return f"{year}-{month_num}-{int(day):02d}"
#
#     return date_str
