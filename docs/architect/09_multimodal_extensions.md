# Multimodal Extensions (Optional)

**Priority:** MEDIUM - Advanced Features

## Visual Capture Integration

**Use Case:** Screen recording during meetings (slides, code, diagrams). The visual data is critical, as in technical sessions, the "truth" is often in the pixels, such as scrolling SQL code.

**Challenge:** The **6GB VRAM constraint** prevents simultaneous VLM + LLM. A standard 7B model requires $\approx 5$ GB, and the Vision Encoder adds $\approx 0.8$ GB to $1.5$ GB. This mathematically exceeds the 6GB capacity, making concurrent execution impossible.

## Hybrid VLM-SLM Architecture

**Principle:** **Compound AI System** or **Multi-Agent Pipeline**. This architecture leverages **cognitive specialization**, decoupling visual recognition from syntactic logic to manage the tight memory budget.

**Components:**

| Model | Size (Quantized) | Role | Hardware |
| :--- | :--- | :--- | :--- |
| **VLM (Perception)** | **Qwen3-VL-2B** or **4B** ($\approx 1.5$–$2.8$ GB) | Multimodal OCR, Dense Captioning, Visual Extraction, preserves small text fidelity via **DeepStack**. | **NVIDIA GPU (CUDA)** |
| **SLM (Repair)** | **Qwen2.5-Coder-1.5B** ($\approx 1.0$ GB) | **Syntax Repair**, Logic Verification, corrects OCR errors in code. | **Intel NPU (OpenVINO)** or **GPU** (Sequential) |
| **Filter** | **MobileViT-S** (CVM) | Low-latency content filtering and classification. | **CPU/GPU (CPU Preferred)** |

**Why:** This hybrid architecture is necessary because the **Qwen3-VL** series (e.g., 2B/4B) uses **DeepStack** to preserve fine-grained visual details (critical for 10pt SQL code), but even these models require a separate logic checker (SLM) for syntax correction. Deploying the micro-coder (SLM) on the NPU achieves **VRAM isolation** and **parallel execution**.

## Visual Processing Workflow

The pipeline must avoid feeding a continuous video stream due to VRAM limitations.

1.  **Gatekeeping:** Screen captures are filtered by a **Structural Similarity Index Measure (SSIM)** gate (or pHash) to ensure only frames with significant structural change (e.g., SSIM $< 0.85$) are captured, filtering out noise like blinking cursors.
2.  **Filtering:** If a change is detected, a lightweight Computer Vision Model (CVM) like **MobileViT-S** classifies the content (e.g., *'Code Editor'* or *'Presentation Slide'*).
3.  **Cropping:** **Active Window Detection** is used to dynamically crop the image to the Region of Interest (ROI), which significantly reduces the visual token count and preserves pixel density.
4.  **VLM Inference:** The unique, cropped keyframe is passed to the **Qwen3-VL** VLM for **Code-Optimized OCR** or **VLM Captioning**.

## Code Reconstruction

**Problem:** Scrolling code creates overlapping frames. When the user scrolls down 10 lines, the new frame is 90% identical but shifted. Simply aggregating these output streams fills the VLM’s context window with redundant code.

**Solution:** **Diff-Match-Patch (DMP)**. DMP is a high-performance library that calculates precise **line-based deltas** (insertions/deletions) to merge the overlapping OCR outputs from the VLM.

**Benefits:** DMP ensures that the overlapping segments are merged into a **single, canonical, minimal SQL script**. This prevents the saturation of the LLM context window with redundant visual tokens and guarantees the **Coherent Output** required for summarization.

## Resource Management

**Sequential Access:** The system must strictly enforce the **Exclusive Access Policy (Mutual Exclusion)**. The orchestration layer must ensure that the VLM is **fully unloaded** from the 6GB VRAM before the LLM/Summary Agent is loaded. This requires the worker to explicitly delete the model object and call memory cleanup routines (e.g., `torch.cuda.empty_cache()`).

**Latency:** This "load-inference-unload" cycle is a necessary compromise for stability but introduces a **latency penalty of 2–5 seconds** during model reloading.

## Multimodal Context Fusion

**Integration:** The raw output streams—the diarized text segments and the visual analysis features (OCR text and VLM-generated captions)—must be **chronologically interleaved**. This creates a **rich, grounded context** that allows the Synthesis LLM to resolve anaphoric references (e.g., "that chart" refers to the visual description).

**Output Format:** Visual descriptions must be inserted into the text stream at their precise time alignment, creating an aligned log for the final LLM synthesis.

```markdown
Speaker A (04:23): As we look at the Q3 numbers...
[04:20] Visual Event: Slide Title "Q3 Growth" detected. Key Data: Revenue up 15% YoY.
Speaker B (04:28): You can see a significant jump compared to last year.
```

## Small Language Model (SLM) for Code

**Purpose:** To perform **syntax repair** and fix character substitution errors introduced by OCR without consuming valuable GPU VRAM.

**Model:** **Qwen3-0.6B Micro-Coder** or **Qwen2.5-Coder-1.5B-Instruct**.

**Deployment:** The micro-coder model is architected for deployment on the **Intel NPU** via the **OpenVINO framework**. This offload strategy ensures the GPU VRAM is reserved for the VLM, achieving **true parallelism** (GPU processes vision, NPU repairs code).

**Task:** Corrects character substitution errors, such as confusing the numeral '1' with the lowercase letter 'l' in SQL syntax (e.g., correcting "SELECT 1" to "SELECT l").

**Example:**
```python
# SLM's role is syntactic repair based on coding knowledge
raw_ocr_input = "SELECT * FHOM users WHERE id-1;"
# SLM repair prompt is applied:
# Final output: SELECT * FROM users WHERE id=1;
```

## When to Implement

This extension focuses on **Advanced Features**. It should be implemented **after** the core unimodal pipeline (L1-L6) is fully functional and stable. The architectural complexity—requiring asynchronous orchestration, VLM integration, and code reconstruction—makes it a **future enhancement consideration**.