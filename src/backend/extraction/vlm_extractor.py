# =============================================================================
# DEPRECATED  —  legacy code retired on 2026-04-24.
#
# Qwen2-VL-7B VLM extractor wired through the legacy OCREngine +
# EntityExtractor fallback path. Superseded by
# src/backend/extraction/neural_fallback.py (Gemini 2.5 Flash via BAML) in
# the agentic pipeline.
#
# The implementation below is preserved as comments for reference and git
# history. Nothing in the active pipeline imports from this module; any
# accidental `from ... import X` will raise ImportError, which is intentional.
# =============================================================================

# import json
# import logging
# import os
# import re
# import tempfile
# from dataclasses import dataclass, field
#
# import numpy as np
# from PIL import Image
#
# from src.backend.extraction.entity_extractor import EntityExtractor, ExtractedData
# from src.backend.ingestion.preprocessing import Preprocessing
# from src.backend.ocr.ocr_engine import DocumentOCRResult, OCREngine
# from src.backend.pipeline.orchestrator import ExtractorInterface
#
# logger = logging.getLogger(__name__)
#
# try:
#     from qwen_vl_utils import process_vision_info as _process_vision_info  # type: ignore[import]
#     _QWEN_VL_UTILS_AVAILABLE = True
# except ImportError:
#     _process_vision_info = None
#     _QWEN_VL_UTILS_AVAILABLE = False
#
#
# class VLMExtractor(ExtractorInterface):
#     """Field extractor using Qwen2-VL-7B-Instruct (4-bit quantised).
#
#     Implements ExtractorInterface — drop-in replacement for RealExtractor.
#     Optionally loads QLoRA adapters after fine-tuning (Phase 7B.2).
#
#     On JSON parse failure it transparently falls back to EntityExtractor output,
#     so it never returns empty fields due to model error alone.
#     """
#
#     EXTRACTION_PROMPT = (
#         "You are a financial document extraction assistant. "
#         "Extract the following fields from this document image. "
#         "Return ONLY valid JSON with exactly these keys (use null for missing fields):\n"
#         "{\n"
#         '  "invoice_number": "string or null",\n'
#         '  "date": "YYYY-MM-DD or null",\n'
#         '  "vendor_name": "string or null",\n'
#         '  "total_amount": "numeric string or null",\n'
#         '  "subtotal": "numeric string or null",\n'
#         '  "tax": "numeric string or null",\n'
#         '  "line_items": [\n'
#         '    {"description": "string", "quantity": 0.0, "unit_price": 0.0, "total": 0.0}\n'
#         "  ]\n"
#         "}"
#     )
#
#     _FIELD_NAMES = ("invoice_number", "date", "vendor_name", "total_amount", "subtotal", "tax")
#
#     def __init__(
#         self,
#         model_name: str = "Qwen/Qwen2-VL-7B-Instruct",
#         adapter_path: str | None = None,
#     ):
#         self._model_name = model_name
#         self._adapter_path = adapter_path
#         self._model = None      # lazy-loaded on first inference call
#         self._processor = None  # lazy-loaded together with model
#         self._preprocessing = Preprocessing()
#
#     # ------------------------------------------------------------------
#     # Lazy model loading
#     # ------------------------------------------------------------------
#
#     def _load_model(self) -> None:
#         """Load Qwen2-VL-7B-Instruct in 4-bit quantisation.
#
#         Optionally merges QLoRA adapters if adapter_path was supplied.
#         Sets self._model and self._processor.
#         """
#         import torch
#         from transformers import (  # type: ignore[import]
#             AutoProcessor,
#             BitsAndBytesConfig,
#             Qwen2VLForConditionalGeneration,
#         )
#
#         logger.info("Loading Qwen2-VL model: %s (4-bit)", self._model_name)
#
#         bnb_config = BitsAndBytesConfig(
#             load_in_4bit=True,
#             bnb_4bit_compute_dtype=torch.float16,
#             bnb_4bit_use_double_quant=True,
#             bnb_4bit_quant_type="nf4",
#         )
#
#         model = Qwen2VLForConditionalGeneration.from_pretrained(
#             self._model_name,
#             quantization_config=bnb_config,
#             device_map="auto",
#             trust_remote_code=True,
#         )
#
#         if self._adapter_path is not None:
#             from peft import PeftModel  # type: ignore[import]
#             logger.info("Loading QLoRA adapters from: %s", self._adapter_path)
#             model = PeftModel.from_pretrained(model, self._adapter_path)
#
#         model.eval()
#
#         processor = AutoProcessor.from_pretrained(
#             self._model_name, trust_remote_code=True
#         )
#
#         self._model = model
#         self._processor = processor
#
#     @property
#     def model(self):
#         """Lazy-load model on first access."""
#         if self._model is None:
#             self._load_model()
#         return self._model
#
#     @property
#     def processor(self):
#         """Lazy-load processor on first access (triggers model load if needed)."""
#         if self._processor is None:
#             self._load_model()
#         return self._processor
#
#     # ------------------------------------------------------------------
#     # Inference helpers
#     # ------------------------------------------------------------------
#
#     @staticmethod
#     def _page_to_pil(image: np.ndarray) -> Image.Image:
#         """Convert a preprocessed numpy page to an RGB PIL Image."""
#         pil = Image.fromarray(image)
#         if pil.mode != "RGB":
#             pil = pil.convert("RGB")
#         return pil
#
#     def _run_inference(self, pil_image: Image.Image) -> tuple[str, float]:
#         """Run Qwen2-VL on a single page image.
#
#         Returns:
#             (raw_text, confidence) where confidence is the mean per-token
#             probability of the generated JSON tokens, normalised to [0, 1].
#         """
#         import torch
#
#         messages = [
#             {
#                 "role": "user",
#                 "content": [
#                     {"type": "image", "image": pil_image},
#                     {"type": "text", "text": self.EXTRACTION_PROMPT},
#                 ],
#             }
#         ]
#
#         text_prompt = self.processor.apply_chat_template(
#             messages, tokenize=False, add_generation_prompt=True
#         )
#
#         if _QWEN_VL_UTILS_AVAILABLE:
#             image_inputs, video_inputs = _process_vision_info(messages)
#             inputs = self.processor(
#                 text=[text_prompt],
#                 images=image_inputs,
#                 videos=video_inputs,
#                 padding=True,
#                 return_tensors="pt",
#             )
#         else:
#             # Fallback: pass image directly; works with newer transformers builds
#             inputs = self.processor(
#                 text=[text_prompt],
#                 images=[pil_image],
#                 padding=True,
#                 return_tensors="pt",
#             )
#
#         inputs = inputs.to(self.model.device)
#         input_len = inputs.input_ids.shape[1]
#
#         with torch.no_grad():
#             output = self.model.generate(
#                 **inputs,
#                 max_new_tokens=512,
#                 do_sample=False,
#                 output_scores=True,
#                 return_dict_in_generate=True,
#             )
#
#         generated_ids = output.sequences[:, input_len:]
#         raw_text = self.processor.batch_decode(
#             generated_ids, skip_special_tokens=True
#         )[0]
#
#         # Mean probability of each chosen token as confidence signal
#         confidence = 0.75  # default if scores unavailable
#         if output.scores:
#             token_probs = []
#             for step_idx, score in enumerate(output.scores):
#                 if step_idx >= generated_ids.shape[1]:
#                     break
#                 chosen = generated_ids[0, step_idx]
#                 prob = torch.softmax(score[0], dim=-1)[chosen].item()
#                 token_probs.append(prob)
#             if token_probs:
#                 confidence = float(sum(token_probs) / len(token_probs))
#                 confidence = max(0.0, min(1.0, confidence))
#
#         return raw_text, confidence
#
#     def _parse_response(
#         self,
#         raw: str,
#         confidence: float,
#         fallback_extractor: EntityExtractor,
#         ocr_result: DocumentOCRResult,
#     ) -> ExtractedData:
#         """Parse the VLM JSON response into ExtractedData.
#
#         Falls back to EntityExtractor on any parse failure so the pipeline
#         always returns something useful.
#         """
#         # Strip markdown code fences if present
#         cleaned = re.sub(r"```(?:json)?\s*|\s*```", "", raw).strip()
#         # Extract first {...} block in case of surrounding text
#         brace_match = re.search(r"\{.*\}", cleaned, re.DOTALL)
#         if brace_match:
#             cleaned = brace_match.group(0)
#
#         try:
#             data = json.loads(cleaned)
#         except (json.JSONDecodeError, ValueError):
#             logger.warning(
#                 "VLMExtractor: JSON parse failed (raw=%r…), falling back to EntityExtractor",
#                 raw[:120],
#             )
#             return fallback_extractor.extract(ocr_result)
#
#         fields = []
#         for field_name in self._FIELD_NAMES:
#             value = data.get(field_name)
#             if value is not None and str(value).strip() and str(value).lower() != "null":
#                 fields.append(
#                     {
#                         "field_name": field_name,
#                         "field_value": str(value).strip(),
#                         "confidence": confidence,
#                     }
#                 )
#
#         line_items = []
#         for item in data.get("line_items") or []:
#             if not isinstance(item, dict):
#                 continue
#             description = str(item.get("description", "")).strip()
#             if not description:
#                 continue
#             try:
#                 quantity = float(item.get("quantity") or 0.0)
#                 unit_price = float(item.get("unit_price") or 0.0)
#                 total = float(item.get("total") or 0.0)
#             except (ValueError, TypeError):
#                 quantity, unit_price, total = 0.0, 0.0, 0.0
#             line_items.append(
#                 {
#                     "description": description,
#                     "quantity": quantity,
#                     "unit_price": unit_price,
#                     "total": total,
#                 }
#             )
#
#         return ExtractedData(fields=fields, line_items=line_items)
#
#     # ------------------------------------------------------------------
#     # Public interface
#     # ------------------------------------------------------------------
#
#     def extract_from_image(
#         self, pil_image: Image.Image
#     ) -> tuple[list[dict], list[dict]]:
#         """Extract fields directly from a PIL Image (used by evaluate.py).
#
#         Bypasses PDF preprocessing — suitable for dataset evaluation where
#         samples are already images.
#         """
#         try:
#             raw, confidence = self._run_inference(pil_image)
#             # Build a minimal OCR result for fallback use
#             ocr_result = DocumentOCRResult(pages=[], tables=[], full_text="")
#             extracted = self._parse_response(
#                 raw, confidence, EntityExtractor(), ocr_result
#             )
#             return extracted.fields, extracted.line_items
#         except Exception as e:
#             logger.error("VLMExtractor.extract_from_image failed: %s", e)
#             return [], []
#
#     def extract(self, document_id: str, filename: str) -> tuple[list[dict], list[dict]]:
#         """Full pipeline: preprocess PDF → OCR → VLM extraction.
#
#         Implements ExtractorInterface — can replace RealExtractor in
#         PipelineOrchestrator.
#         """
#         pdf_path = os.path.join("uploads", filename)
#         try:
#             pages = self._preprocessing.preprocess_document(pdf_path)
#             ocr_result = OCREngine(use_got_ocr=False).process_document(pages, pdf_path=pdf_path)
#
#             logger.info("OCR FULL TEXT LENGTH: %s", len(ocr_result.full_text))
#             logger.info("OCR FULL TEXT PREVIEW: %s", ocr_result.full_text[:200])
#
#             # Use first page for VLM; iterate remaining pages for better coverage
#             all_fields: list[dict] = []
#             all_line_items: list[dict] = []
#
#             for page in pages:
#                 logger.info("RUNNING VLM ON PAGE: %s", page.page_number)
#                 pil_image = self._page_to_pil(page.processed)
#                 raw, confidence = self._run_inference(pil_image)
#                 extracted = self._parse_response(
#                     raw, confidence, EntityExtractor(), ocr_result
#                 )
#                 # Merge fields: prefer higher-confidence values for duplicate field names
#                 existing_names = {f["field_name"] for f in all_fields}
#                 for f in extracted.fields:
#                     if f["field_name"] not in existing_names:
#                         all_fields.append(f)
#                         existing_names.add(f["field_name"])
#                 all_line_items.extend(extracted.line_items)
#
#             return all_fields, all_line_items
#
#         except Exception as e:
#             logger.error(
#                 "VLMExtractor failed for document %s: %s", document_id, e
#             )
#             return [], []
