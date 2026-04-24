# =============================================================================
# DEPRECATED  —  legacy code retired on 2026-04-24.
#
# Per-field-confidence router that escalated between EntityExtractor and
# VLMExtractor. Superseded by the auditor_node + reconciler_node loop in
# the LangGraph agent — see src/backend/agents/nodes.py.
#
# The implementation below is preserved as comments for reference and git
# history. Nothing in the active pipeline imports from this module; any
# accidental `from ... import X` will raise ImportError, which is intentional.
# =============================================================================

# """agentic_extractor.py — Confidence-routed extraction (Phase 7C).
#
# Routes each document through fast (EntityExtractor via RealExtractor) or VLM
# (Qwen2-VL-7B via VLMExtractor) extraction based on per-field confidence
# thresholds learned by ConfidenceCalibrator.
#
# Falls back gracefully to fast path if VLM fails.
# """
#
# from __future__ import annotations
#
# import logging
# from typing import TYPE_CHECKING
#
# from sqlalchemy.orm import Session
#
# from src.backend.pipeline.orchestrator import ExtractorInterface
#
# if TYPE_CHECKING:
#     from src.backend.pipeline.confidence_calibrator import ConfidenceCalibrator
#
# logger = logging.getLogger(__name__)
#
#
# class AgenticExtractor(ExtractorInterface):
#     """Confidence-routed extractor combining fast and VLM extractors.
#
#     Uses ConfidenceCalibrator-derived thresholds to decide, per document,
#     whether to escalate from EntityExtractor to VLMExtractor.
#
#     All dependencies are injectable for testing — no hard model imports at
#     construction time.
#     """
#
#     def __init__(
#         self,
#         db: Session,
#         extractor_fast: ExtractorInterface | None = None,
#         extractor_vlm: ExtractorInterface | None = None,
#         calibrator: "ConfidenceCalibrator | None" = None,
#     ) -> None:
#         """Initialise with injectable extractors and calibrator.
#
#         Args:
#             db: SQLAlchemy session (stored for potential future use)
#             extractor_fast: fast extractor; defaults to RealExtractor() on first use
#             extractor_vlm: VLM extractor; defaults to VLMExtractor() on first use
#             calibrator: fitted ConfidenceCalibrator; defaults to ConfidenceCalibrator()
#         """
#         self._db = db
#         self._extractor_fast = extractor_fast
#         self._extractor_vlm = extractor_vlm
#         self._calibrator = calibrator
#         self._stats: dict[str, int] = {"fast_path": 0, "vlm_path": 0}
#
#     # ------------------------------------------------------------------
#     # Lazy properties
#     # ------------------------------------------------------------------
#
#     @property
#     def extractor_fast(self) -> ExtractorInterface:
#         """Lazy-initialise fast extractor (RealExtractor) on first access."""
#         if self._extractor_fast is None:
#             from src.backend.pipeline.orchestrator import RealExtractor
#             self._extractor_fast = RealExtractor()
#         return self._extractor_fast
#
#     @property
#     def extractor_vlm(self) -> ExtractorInterface:
#         """Lazy-initialise VLM extractor (VLMExtractor) on first access."""
#         if self._extractor_vlm is None:
#             from src.backend.extraction.vlm_extractor import VLMExtractor
#             self._extractor_vlm = VLMExtractor()
#         return self._extractor_vlm
#
#     @property
#     def calibrator(self) -> "ConfidenceCalibrator":
#         """Lazy-initialise calibrator on first access."""
#         if self._calibrator is None:
#             from src.backend.pipeline.confidence_calibrator import ConfidenceCalibrator
#             self._calibrator = ConfidenceCalibrator()
#         return self._calibrator
#
#     # ------------------------------------------------------------------
#     # ExtractorInterface implementation
#     # ------------------------------------------------------------------
#
#     def extract(
#         self, document_id: str, filename: str
#     ) -> tuple[list[dict], list[dict]]:
#         """Route document through fast or VLM extraction based on confidence.
#
#         Algorithm:
#             1. Run fast extractor.
#             2. Identify low-confidence fields (confidence < calibrator threshold).
#             3. If none: return fast results (fast path).
#             4. Else: run VLM extractor; on failure return fast results.
#             5. Merge: replace low-conf fast fields with higher-confidence VLM
#                values; append VLM-only fields; prefer VLM line items.
#
#         Args:
#             document_id: document identifier passed through to extractors
#             filename: document filename relative to uploads/ directory
#
#         Returns:
#             (fields, line_items) matching ExtractorInterface contract
#         """
#         fast_fields, fast_line_items = self.extractor_fast.extract(document_id, filename)
#         low_conf = self._identify_low_confidence_fields(fast_fields)
#
#         if not low_conf:
#             self._stats["fast_path"] += 1
#             logger.info(
#                 "AgenticExtractor: doc=%s path=fast low_conf_fields=0", document_id
#             )
#             return fast_fields, fast_line_items
#
#         # Escalate to VLM
#         logger.info(
#             "AgenticExtractor: doc=%s path=vlm low_conf_fields=%d (%s)",
#             document_id, len(low_conf), ", ".join(sorted(low_conf)),
#         )
#         try:
#             vlm_fields, vlm_line_items = self.extractor_vlm.extract(document_id, filename)
#         except Exception as e:
#             logger.error(
#                 "AgenticExtractor: VLM extractor failed for doc=%s: %s — returning fast results",
#                 document_id, e,
#             )
#             return fast_fields, fast_line_items
#
#         merged_fields, merged_items = self._merge_results(
#             fast_fields, fast_line_items, vlm_fields, vlm_line_items, low_conf
#         )
#         self._stats["vlm_path"] += 1
#         return merged_fields, merged_items
#
#     # ------------------------------------------------------------------
#     # Helpers
#     # ------------------------------------------------------------------
#
#     def _identify_low_confidence_fields(self, fields: list[dict]) -> set[str]:
#         """Return field_names whose confidence is below the calibrator threshold.
#
#         Args:
#             fields: list of field dicts with field_name and confidence keys
#         Returns:
#             set of field_name strings (may be empty)
#         """
#         low: set[str] = set()
#         for f in fields:
#             field_name = f.get("field_name", "")
#             confidence = f.get("confidence", 1.0)
#             if confidence < self.calibrator.threshold(field_name):
#                 low.add(field_name)
#         return low
#
#     def _merge_results(
#         self,
#         fast_fields: list[dict],
#         fast_line_items: list[dict],
#         vlm_fields: list[dict],
#         vlm_line_items: list[dict],
#         low_conf_field_names: set[str],
#     ) -> tuple[list[dict], list[dict]]:
#         """Merge fast and VLM results, preferring VLM for low-confidence fields.
#
#         Scalar fields:
#           - Start with fast_fields as the base dict keyed by field_name.
#           - For each VLM field: if its field_name was low-confidence AND
#             vlm_field["confidence"] > fast_field["confidence"], replace.
#           - If a VLM field is entirely absent from fast results, append it.
#         Line items:
#           - Use vlm_line_items if non-empty; else fall back to fast_line_items.
#
#         Args:
#             fast_fields: fields from fast extractor
#             fast_line_items: line items from fast extractor
#             vlm_fields: fields from VLM extractor
#             vlm_line_items: line items from VLM extractor
#             low_conf_field_names: set of field names identified as low-confidence
#
#         Returns:
#             (merged_fields, merged_line_items)
#         """
#         # Build ordered dict preserving fast field order
#         merged: dict[str, dict] = {f["field_name"]: f for f in fast_fields}
#
#         for vlm_f in vlm_fields:
#             name = vlm_f.get("field_name", "")
#             if not name:
#                 continue
#             if name in merged:
#                 if name in low_conf_field_names:
#                     fast_conf = merged[name].get("confidence", 0.0)
#                     vlm_conf = vlm_f.get("confidence", 0.0)
#                     if vlm_conf > fast_conf:
#                         merged[name] = vlm_f
#             else:
#                 # VLM found a field the fast extractor missed — add it
#                 merged[name] = vlm_f
#
#         merged_fields = list(merged.values())
#         merged_items = vlm_line_items if vlm_line_items else fast_line_items
#         return merged_fields, merged_items
#
#     @property
#     def stats(self) -> dict[str, int]:
#         """Return a copy of routing stats: fast_path count and vlm_path count."""
#         return dict(self._stats)
