# Project: Agentic Financial Auditor (2026 SOTA)

**Target:** Enterprise-grade Straight-Through Processing (STP) using a **Lean Fast-Path + Self-Correcting Multimodal Loop**.

---

## 1. Core Architecture: The "Dual-Brain" Strategy
The system is designed to be "Fast by Default, Intelligent by Exception."

### Tier 1: The High-Speed Extractor
* **Engine:** PaddleOCR v5 (Local/Quantized) + Heuristic Table Reconstructor.
* **Function:** Performs a brute-force scan of the document. Maps text to $x, y$ coordinates and groups them into a schema using distance-based logic.
* **Goal:** Processing in **<800ms**.
* **Constraint:** Does not attempt "reasoning." If the math is fuzzy, it hands the problem off.

### Tier 2: The Agentic Reconciler
* **Engine:** Gemini 2.5 Flash via **BAML**.
* **Function:** Multimodal "Visual Auditor." Triggered only when Tier 1 fails a deterministic check.
* **Decision:** Gemini analyzes the **raw image bytes** (or targeted crops) to resolve structural ambiguity, faint punctuation, or handwritten notes that Tier 1 ignored.

---

## 2. The Agentic Workflow (LangGraph StateGraph)
The system uses a Directed Cyclic Graph (DCG) to allow the "Judge" to send data back for correction.



1.  **[NODE] Initial_Extract:** Fast OCR pass into a BAML-defined `ExtractedInvoice` schema.
2.  **[NODE] Math_Audit (The Judge):** * **Strict Decimal Logic:** Converts all strings to `decimal.Decimal`. 
    * **Magnitude Guard:** Compares `Line_Items` vs `Total`. If a "Decimal Slip" is detected (e.g., 1000 misread as 10.00), it flags a high-priority `SCALE_ERROR`.
3.  **[ROUTER] Integrity Gate:**
    * **IF** (Math == Correct) AND (Confidence > 0.95) &rarr; **Finalize**.
    * **ELSE** &rarr; **Route to Reconciler**.
4.  **[NODE] Gemini_Reconcile:** * Receives image + error context (e.g., *"Audit failed: Total is off by 990.00. Check for misplaced decimal points"*).
    * Gemini performs a multimodal re-read.
5.  **[LOOP] Verification:** The correction is re-audited. (Max 3 loops to prevent hallucination).
6.  **[EXIT] HITL:** If unresolvable, the full `traceability_log` is sent to the React ReviewPage.

---

## 3. Disaster Prevention: Handling "The Decimal Slip"
To prevent the catastrophic misreading of **1000** as **10.00**, we implement three layers of defense:

| Layer | Method | Defense Mechanism |
| :--- | :--- | :--- |
| **Layer 1: Heuristic** | Coordinate Analysis | If a decimal point is suspiciously small or distant from the integers, Tier 1 marks it as "Low Confidence." |
| **Layer 2: Auditor** | Magnitude Check | Python checks if `Sum(Items) / Total` is a power of 10. If so, it forces a Tier 2 multimodal re-scan. |
| **Layer 3: BAML** | Visual Prompting | Gemini is explicitly told to zoom in on punctuation: *"Identify if '.' is a decimal or a stray artifact/comma."* |

---

## 4. Technical Standards & Traceability
* **Data Integrity:** **Zero Float Tolerance.** Any use of `float` in the financial pipeline results in an immediate build failure.
* **Contract-Driven Development:** All LLM inputs/outputs are strictly typed in `.baml` files.
* **Audit Trail:** Every document saves a `traceability_log` in Postgres:
    ```json
    {
      "iteration_1": {"engine": "Paddle", "error": "TOTAL_MISMATCH"},
      "iteration_2": {"engine": "Gemini", "reasoning": "Detected faint decimal point in handwritten field", "status": "FIXED"}
    }
    ```
* **HITL UI:** The React ReviewPage displays the image with overlays of exactly what the agent "saw" vs. what it "corrected."

---

## 5. Deployment Reality
Because Tier 1 is local (Paddle) and Tier 2 is serverless (Gemini API), the system scales horizontally. The "Blazingly Fast" success path (the 80%) remains cost-effective, while the "Cognitive" path (the 20%) ensures the enterprise-grade accuracy required for financial auditing.