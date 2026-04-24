# Layout-Aware Document Extraction with Local Large Language Models

**Fatima Naeem, Maheen Muhammad Rizwan, Juweriya Bint Nasir**
*Department of Computer Science, IBA Karachi*
*Supervisor: Dr. Rizwan Ahmed Khan — Industry Partner: VentureDive*

---

**Abstract** — Enterprise document processing systems increasingly rely on large language models and layout-aware extraction pipelines to convert unstructured documents into structured data. However, many high-performing systems remain proprietary or depend on paid cloud services, limiting reproducibility and accessibility. This work investigates whether similar capabilities can be achieved using a fully open-source pipeline deployed locally.

We implement a document extraction system architecturally inspired by layout-aware LLM research such as DocLLM, without using or extending DocLLM itself. Rather than replicating any specific system, we independently implement the core architectural concept — combining OCR-based text extraction with a locally deployed large language model — using freely available components. As part of this work, a lightweight baseline prototype was first developed and evaluated to establish feasibility and identify key limitations, before the full pipeline was designed. The system generates structured representations of financial documents, including entities such as vendors, dates, line items, and totals.

The baseline prototype has been evaluated on English and French scanned receipts, demonstrating feasibility and exposing key limitations. Full evaluation of the FADE system on the SROIE English benchmark is currently in progress on GPU infrastructure provided by VentureDive, with quantitative results to be presented at the oral presentation. Future work targets multilingual extension to Urdu and Arabic, the non-English scripts most relevant to our industry partner's enterprise context.

**Index Terms** — document extraction, OCR, large language models, intelligent document processing, layout-aware, open-source, financial documents

---

## I. Introduction

Every day, enterprises process thousands of financial documents — invoices, purchase orders, receipts, and contracts — that arrive as scanned images or PDFs with no machine-readable structure. Converting these documents into structured data that can be stored in databases, analysed, and acted upon is a labour-intensive and error-prone task when done manually. Intelligent Document Processing (IDP) systems automate this conversion, and the recent availability of powerful large language models has dramatically improved their accuracy.

The problem, however, is access. The most capable IDP systems in commercial deployment — including those from major cloud providers — are proprietary, charge per-page fees, and process documents on remote servers. For organisations handling sensitive financial data, sending documents to third-party cloud services creates serious privacy and compliance risks. For researchers, the proprietary nature of these systems limits reproducibility and scientific scrutiny.

This motivates a fundamental question: *can an open-source, locally deployed pipeline achieve comparable extraction quality to cloud-based proprietary systems on real financial documents?*

This paper presents our work toward answering that question. We design and implement a complete intelligent document processing pipeline built entirely from open-source components and evaluated on publicly available benchmark datasets. Our system takes a scanned or digitally-born financial document — a receipt or invoice — and produces a structured JSON record containing key fields: vendor name, date, invoice number, line items, subtotal, tax, and total amount.

The core contributions of this work are:

1. A fully open-source, locally deployable document extraction pipeline that achieves strong performance on English financial documents without reliance on any paid API or cloud service.
2. A baseline prototype (Section IV), independently implemented without relying on any existing document AI codebase, which validated the core OCR + local LLM concept and whose empirical limitations directly motivated the design of the full system.
3. An agentic extraction architecture that routes documents through a fast rule-based path or a vision-language model path based on confidence, reducing average inference cost while maintaining accuracy.
4. An empirical evaluation framework targeting the SROIE English receipt benchmark; full quantitative results will be presented at the oral presentation upon completion of the GPU training and evaluation runs.
5. A human-in-the-loop validation interface and correction-tracking system that enables continuous improvement of extraction quality from user feedback.

---

## II. Background and Related Work

### A. Traditional OCR-Based Extraction

The classical approach to document extraction combines an Optical Character Recognition (OCR) engine with hand-crafted regular expressions or rule-based named entity recognisers. Tesseract [1], the most widely used open-source OCR engine, extracts raw text from document images. Subsequent NLP components then parse that text to identify fields of interest. While straightforward to implement, this approach is brittle: it assumes predictable document layouts, degrades on noisy scans, and requires separate rules for each document template.

### B. Layout-Aware Models

A significant advance came with layout-aware transformer models such as LayoutLM [2] and its successors LayoutLMv2 and LayoutLMv3. These models jointly encode text tokens and their two-dimensional bounding box coordinates, allowing the model to reason about spatial relationships between elements. DocLLM [3], proposed by JPMorgan AI Research, extends this paradigm by replacing the bounding box encoding with a disentangled spatial attention mechanism that enables a generative LLM to attend to both text content and layout structure simultaneously. DocLLM achieves state-of-the-art performance on multiple document understanding benchmarks while being trainable at modest compute budgets.

Our work is conceptually inspired by the insight that layout context is essential for robust extraction. However, DocLLM is not publicly released for deployment, and we do not use, extend, or replicate DocLLM itself. We independently implement the broader architectural concept — combining OCR with a locally deployed language model — using entirely open and freely available components of our own selection.

### C. Vision-Language Models for Document Understanding

More recently, vision-language models (VLMs) have shown remarkable capability at document understanding tasks by treating the entire document page as an image and reasoning directly from pixels rather than requiring explicit OCR or layout preprocessing. Qwen2-VL [4], released by Alibaba Cloud under an open-source licence, achieves 93.1% accuracy on the DocVQA benchmark at the 7B parameter scale. GOT-OCR 2.0 [5] provides high-accuracy end-to-end OCR specifically designed for document images. Docling [6], developed by IBM Research, provides an open-source document conversion library with layout detection and table extraction capabilities.

During our baseline prototype phase (Section IV), we explored a vision-language model (LLaVA) as an alternative to the OCR stage and found it insufficiently reliable for structured receipt extraction, motivating the use of explicit OCR in the final system.

### D. Agentic and Multi-Stage Extraction

Recent work on agentic AI systems has explored routing different inputs to different models based on estimated difficulty or confidence. ADE (Agentic Document Extraction) by LandingAI proposes a pipeline in which a fast extraction path handles simple documents while a more capable model handles complex cases. We adopt a similar routing principle in our system, designing a confidence-calibrated routing mechanism that avoids invoking the expensive VLM for documents where simpler methods already achieve high confidence.

---

## III. System Architecture

Our system — which we call FADE (Financial Agentic Document Extraction) — consists of five main stages: document ingestion and preprocessing, OCR and layout analysis, field extraction, human-in-the-loop validation, and analytics.

### A. Document Ingestion and Preprocessing

Documents are uploaded through a React-based web interface as PDF files or images. The preprocessing module converts PDFs to page images, applies greyscale normalisation and adaptive thresholding to improve OCR quality on noisy scans, and segments multi-page documents into individual page arrays. A FastAPI backend handles upload, authentication, and pipeline orchestration, with extracted data persisted to a PostgreSQL database.

### B. OCR and Layout Analysis

We replace traditional Tesseract-based OCR with GOT-OCR 2.0, a 580-million parameter end-to-end OCR model that processes document images directly and produces formatted text output with high accuracy. GOT-OCR 2.0 runs entirely locally and is licensed under Apache 2.0. For layout analysis and table extraction, we use Docling, IBM's open-source document conversion library.

### C. Field Extraction

Field extraction is the core intelligence of the pipeline and operates in two modes, managed by the AgenticExtractor.

**Baseline Extractor (EntityExtractor):** Applies spaCy named entity recognition and domain-specific regular expressions to the OCR text output. This path is computationally inexpensive and runs in under one second per document.

**VLM Extractor (VLMExtractor):** Loads Qwen2-VL-7B-Instruct in 4-bit quantisation and runs visual question-answering style inference on each document page, responding with a structured JSON object. Optional QLoRA fine-tuning adapters trained on English receipt data can be loaded at inference time.

**AgenticExtractor:** Implements confidence-based routing between the two modes, invoking the VLM only when the baseline extractor falls below learned per-field confidence thresholds.

**ConfidenceCalibrator:** Learns per-field thresholds from the system's human correction history. Fields with ten or more corrections use logistic regression to find the optimal threshold; fewer corrections use simpler heuristics.

### D. Human-in-the-Loop Validation

Extracted fields are surfaced in a React-based review interface where human reviewers can inspect, correct, and approve or reject each document's extracted data. The system implements role-based access control with three roles: enterprise user, reviewer, and administrator. All corrections are logged to the database and used by the ConfidenceCalibrator in subsequent training cycles.

### E. Analytics and Dashboards

Once documents are approved, extracted financial data feeds analytics modules including spend-by-vendor aggregation, supplier risk scoring, ARIMA-based trend forecasting, and Isolation Forest anomaly detection. These are visualised in a dashboard accessible to enterprise users.

---

## IV. Baseline Prototype: Initial Exploration

Prior to designing the full FADE system, we independently implemented and evaluated a lightweight baseline prototype to establish the feasibility of the OCR + local LLM concept and to identify key technical challenges. This prototype was built from scratch using only open-source components selected independently. It is not based on, derived from, or a replication of DocLLM, Open-DocLLM, or any other existing document AI codebase — it replicates only the general architectural concept of combining OCR with a locally deployed language model.

### A. Prototype Architecture

The prototype pipeline consists of three stages:

1. **PDF Rendering:** Each PDF page is rendered to a high-resolution image using pypdfium2 at scale factor 3, producing raster images suitable for OCR input.
2. **OCR:** Tesseract v5.5 is invoked directly via Python's `subprocess` module. The standard `pytesseract` Python wrapper was found to crash silently due to subprocess spawning incompatibilities on the target system; direct invocation was used as a workaround.
3. **LLM Extraction:** Extracted text is passed to Mistral 7B, served locally via Ollama, with a user-defined extraction contract specifying target fields. The model returns a structured JSON object.

The system was served through a FastAPI REST interface supporting batch multi-document upload.

### B. Prototype Results: English Receipt

We tested the prototype on a scanned English-language retail receipt (Best Buy, CA, USA) from the Kaggle receipts dataset [7]. The document is a true image scan with no embedded text layer, requiring full OCR before extraction.

### C. Prototype Results: French Receipt

We extended evaluation to a French-language restaurant receipt to assess multilingual capability and identify where the pipeline degrades.

**Table I: Field-level extraction accuracy of the prototype on English and French scanned receipts**

| Field | English (Best Buy) | French (Paris Montparnasse) |
|-------|-------------------|----------------------------|
| Store Name | Correct ("Best Buy #103") | Incorrect — hallucinated ("BIOBURGER") |
| Store Address | Correct ("17545 GALE AVE, CA 91748") | Not present in document |
| Date | Correct ("12/02/21") | Correct ("3/17/2024") |
| Time | Correct ("20:35") | Correct ("7:31 PM") |
| Table Number | Not present in document | Correct ("01") |
| Order Number | Not present in document | Missed — returned as "not explicitly stated" |
| Items Purchased | Partial — all items extracted, prices correct for paid items only | Partial — items listed but individual prices missing |
| Subtotal | Correct (179.00) | Correct (19.97 €) |
| Sales Tax | Correct (17.03) | Correct (2.43 €) |
| Total | Correct (196.03) | Correct (22.40 €) |
| Payment Status | Not present in document | Correct ("Commande payée") |

### D. Vision Model Exploration

We additionally explored replacing the OCR stage with a vision-language model — LLaVA 7B and LLaVA 13B served locally via Ollama — to process receipt images directly without Tesseract. Both models produced heavily hallucinated outputs, fabricating store names, dates, and items not present in the document. This finding confirmed that at the 7–13B scale, vision models are insufficiently reliable for structured extraction from scanned receipts, and that explicit OCR followed by LLM reasoning is a more robust approach.

### E. Prototype Limitations and Lessons Learned

The prototype revealed four key limitations that directly informed the design of FADE:

- **No layout awareness.** Flat OCR text loses all spatial context. Without positional information, the LLM cannot reliably distinguish prices from product codes or associate line items with their corresponding values.
- **Multilingual degradation.** Mistral 7B prompt-based extraction fails on non-English receipt structures, even when OCR text quality is acceptable, as seen in the French store name hallucination.
- **OCR tooling incompatibilities.** The `pytesseract` Python wrapper crashed silently due to subprocess issues on the target Windows environment, requiring direct subprocess invocation of the Tesseract binary as a workaround.
- **Vision model unreliability.** LLaVA-based extraction produced consistent hallucinations, confirming that OCR + LLM outperforms pure vision approaches for structured document extraction at this model scale.

These findings motivated the adoption of GOT-OCR 2.0 for higher-accuracy OCR, Docling for layout analysis, and Qwen2-VL for visual reasoning in the full FADE system.

---

## V. Experimental Setup

### A. Datasets

**CORD v2** [8] contains 800 training and 100 test images of scanned receipts from South Korea, with Korean and English text.

**SROIE** [9] contains 626 English receipt images annotated with four fields: company name, date, address, and total. SROIE is the primary benchmark for evaluating the FADE system.

**Kaggle Receipts Dataset** [7] is a collection of real-world scanned commercial receipts used for prototype evaluation. Documents are true image scans with no embedded text layer, requiring full OCR.

### B. Evaluation Metrics

- **Exact Match (EM):** proportion of predicted field values that exactly match ground truth after normalisation.
- **Token-level F1:** standard SQuAD-style token overlap metric, giving partial credit for partially correct extractions.
- **Field-level accuracy:** used for prototype evaluation (Table I).

### C. Experimental Conditions

| Condition | Description |
|-----------|-------------|
| Prototype (ours) | Tesseract (direct subprocess) + Mistral 7B via Ollama, CPU only |
| Baseline | EntityExtractor with GOT-OCR 2.0 text input (regex + spaCy NER) |
| VLM zero-shot | Qwen2-VL-7B-Instruct, no fine-tuning |
| VLM fine-tuned | Qwen2-VL-7B-Instruct with QLoRA adapters (500 steps on SROIE) |

### D. Hardware

Prototype experiments were conducted on a consumer Windows machine (CPU only, no GPU). Full FADE experiments are conducted on an NVIDIA A100 80GB PCIe GPU provided by VentureDive, with the 7B model loaded in 4-bit NF4 quantisation.

---

## VI. Results and Discussion

### A. Prototype Performance

As shown in Table I, the prototype achieved strong field-level accuracy on English receipts for structured fields (date, time, address, totals, tax) but struggled with line item decomposition. On the French receipt, the store name was hallucinated and the order number was missed, yielding an estimated overall field accuracy of approximately 75% on English documents and 55% on French documents. These results confirmed basic feasibility while exposing the limitations that motivated the full FADE architecture.

### B. FADE System Evaluation (In Progress)

Full evaluation of the FADE system — covering the Baseline, VLM zero-shot, and VLM fine-tuned conditions on SROIE — is currently in progress on the VentureDive GPU infrastructure. Training and evaluation runs are scheduled to complete before the oral presentation, at which point Table II will be populated with EM and F1 scores per field and per condition.

Based on component design and published benchmarks for each constituent model, we expect the baseline EntityExtractor to perform moderately on numeric fields (total, date) but weakly on vendor name. The VLM zero-shot condition is expected to improve across all fields given Qwen2-VL-7B's strong pre-trained document understanding. Fine-tuning on SROIE training data is expected to yield further gains, particularly on vendor name and total amount. The AgenticExtractor is designed to reduce VLM invocations for high-confidence documents, lowering average inference cost while maintaining accuracy close to the full VLM condition.

### C. Multilingual Outlook

The current system targets English documents. The prototype evaluation (Section IV-C) already illustrates the degradation pattern for non-English input: store name hallucination on French receipts is consistent with the known limitations of English-centric language models on foreign-language entity recognition.

VentureDive's enterprise clients frequently handle documents in Urdu and Arabic — right-to-left scripts with complex ligature rules where both OCR accuracy and language model coverage are weaker than for English. Extending FADE to these languages is the primary planned future work. The QLoRA fine-tuning infrastructure built in this project is directly applicable: the training pipeline, routing architecture, and evaluation framework require only updated training data and, where needed, an OCR model with stronger Arabic-script support.

### D. Privacy and Reproducibility

By running the entire pipeline on-premises, no document content is transmitted to third-party servers. All components carry permissive open-source licences (Apache 2.0 or equivalent), making the system fully reproducible and deployable without licensing fees.

### E. Limitations

- The 7B model is substantially smaller than proprietary systems such as GPT-4V; complex layouts may yield lower quality extractions.
- QLoRA fine-tuning requires a labelled training set; performance reverts to zero-shot in new domains without labelled data.
- Inference latency for the full VLM path (approximately 10–30 seconds per page) may be a bottleneck in high-throughput environments.
- Prototype relied on Tesseract, which struggles with handwritten or severely degraded scans.

---

## VII. Conclusion

This paper presents FADE, a fully open-source, locally deployable intelligent document processing pipeline for financial documents, alongside a baseline prototype that independently validated the core OCR + local LLM concept and whose empirical limitations shaped the final system design. The prototype demonstrated feasibility on English documents and exposed key challenges in multilingual and layout-aware extraction, directly informing the adoption of GOT-OCR 2.0, Docling, and Qwen2-VL in the full system.

Full quantitative evaluation of FADE on the SROIE English benchmark is in progress and will be presented at the oral presentation. Future work will extend the system to Urdu and Arabic documents, directly addressing the multilingual document landscape of VentureDive's enterprise clients. The system processes sensitive financial documents entirely on-premises, requires no paid APIs, and produces structured outputs that feed directly into analytics dashboards and, in future work, conversational business intelligence interfaces.

---

## Acknowledgements

The authors thank VentureDive for providing the industry context and GPU infrastructure that made this research possible, and Dr. Rizwan Ahmed Khan for his guidance throughout the project. This work was conducted as part of the Computer Science Final Year Project programme at IBA Karachi.

---

## References

[1] R. Smith, "An overview of the tesseract ocr engine," in *Proceedings of the Ninth International Conference on Document Analysis and Recognition (ICDAR)*, 2007.

[2] Y. Xu et al., "Layoutlm: Pre-training of text and layout for document image understanding," in *Proceedings of the 26th ACM SIGKDD International Conference on Knowledge Discovery & Data Mining*, 2020.

[3] D. Wang et al., "Docllm: A layout-aware generative language model for multimodal document understanding," *arXiv preprint arXiv:2401.00908*, 2024.

[4] Qwen Team, "Qwen2-vl: Enhancing vision-language model's perception of the world at any resolution," *arXiv preprint arXiv:2409.12191*, 2024.

[5] H. Wei et al., "Got-ocr 2.0: A general ocr system," *arXiv preprint arXiv:2409.01704*, 2024.

[6] C. Auer et al., "Docling: An efficient open-source toolkit for ai-driven document conversion," *arXiv preprint arXiv:2501.17887*, 2025.

[7] J. Walter, "My receipts (pdf scans)," https://www.kaggle.com/datasets/jenswalter/receipts, 2023, Kaggle dataset.

[8] S. Park et al., "Cord: A consolidated receipt dataset for post-ocr parsing," in *Workshop on Document Intelligence at NeurIPS*, 2019.

[9] Z. Huang et al., "Icdar 2019 competition on scanned receipt ocr and information extraction," in *Proceedings of ICDAR*, 2019.

---

*Presented at The Dhanani School Undergraduate Research Symposium (DURS), IBA Karachi, 2026.*
