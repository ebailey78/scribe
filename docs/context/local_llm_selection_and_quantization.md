# Local LLM Selection and Quantization

**Category:** LLM Workflows and Optimization  
**Stage:** Stage 6

## Overview

Selecting the appropriate local Large Language Model (LLM) in the **7B–14B parameter range** is the final critical step of the optimized summarization pipeline. Since the preceding pre-processing stages (Normalization, Structuring, Correction) have already cleaned and structured the input text, the small LLM can dedicate its limited capacity exclusively to high-level **abstractive summarization**.

The primary selection criteria for this stage must prioritize **long-context performance and stability** to handle the output of the Map-Reduce workflow. Furthermore, deployment mandates aggressive resource optimization using quantization to fit within resource constraints (e.g., 6GB VRAM).

## Recommended Models

The final LLM selection is governed by two key criteria: **robust long-context capabilities** (for Map-Reduce processing) and **exceptional instruction adherence** (for executing the complex Chain of Density prompt).

### LLaMA 3.1-8B-Instruct

**LLaMA 3.1-8B-Instruct** is a highly competitive model strategically chosen for the core summarization task.

*   **Strategic Advantage:** LLaMA 3.1-8B-Instruct exhibits a **distinct advantage in handling and scaling to extremely long texts** (up to 128K tokens) compared to other small models. This superior long-context scaling capability is essential for synthesizing the multi-chunk summaries produced by the Map-Reduce workflow.
*   **General Performance:** It is recognized for its strong general performance, conversational AI capabilities, and impressive cost efficiency.
*   **Structured Output:** It is effective for generating structured output from text, such as extracting concepts into a JSON payload.

### Qwen 2.5 14B / Qwen3-8B

The Qwen series is a strong alternative or, in some cases, the preferred choice, particularly regarding feature set and instruction following.

*   **Qwen 2.5 14B (Structured Output Specialist):** This model is noted for its **exceptional adherence to JSON schemas** and is recommended as the preferred choice if VRAM permits (though it requires approximately 9 GB in Q4\_K\_M quantization). Its strength lies in structured generation and coding benchmarks.
*   **Qwen3-8B (Dual-Mode Reasoning):** The Qwen3-8B model is cited as a **frontrunner** in the LLM landscape due to its extensive long-context support and demonstrated strong instruction-following capabilities. It uniquely supports seamless switching between a **"thinking mode"** (for complex logical reasoning, math, and coding) and a **"non-thinking mode"** (for efficient, general-purpose dialogue). The native context length is 32,768 tokens, extendable up to **131,072 tokens** using the YaRN (Yet Another RoPE Next) context extension technique.

## Long-Context Stability

Long-context stability is the **most critical requirement** for a robust summarization pipeline that uses the Map-Reduce pattern.

*   **Performance Discrepancy:** While LLaMA 3.1-8B-Instruct may have a marginally lower "base ability" score on shorter texts, it shows superior performance in scaling to extremely long contexts (up to 128k+), highlighting its superior long-context extension capability.
*   **Evaluation Metrics:** Traditional Perplexity (PPL) has proven unreliable for assessing long-context capabilities because it averages across all tokens, obscuring true performance. Instead, the metric **LongPPL** is proposed, which focuses only on "key tokens" strongly tied to long-context information. **LongPPL** is recognized for correlating well (e.g., -0.96 Pearson correlation) with a model's true long-context performance.
*   **Architectural Reliance:** The Map-Reduce workflow (Segment 6) is specifically designed to manage documents that exceed the finite context window capacity of small LLMs. The model must maintain coherence and accuracy when processing the condensed "summary of summaries" during the **Reduce Phase**.

## Structured Output Capabilities

The final synthesis output (Stage 6) must be actionable, which often requires a structured format (e.g., JSON).

*   **Instruction Adherence:** The specialized pipeline mandates the LLM be capable of consistently executing the iterative Chain of Density (CoD) prompt, which requires strong instruction adherence.
*   **LLM Role:** LLMs generally offer a unified reasoning framework that leverages broad semantic understanding, enabling them to support various analytical tasks across diverse data modalities with greater flexibility. This allows them to generate complex, structured artifacts.
*   **Prompt Engineering:** To ensure reliable generation, the output formats are explicitly specified in the prompt, often requiring results to be returned in a format like **JSON**. Models like the **Qwen 2.5 14B** are fine-tuned to excel at this type of JSON generation.

## GGUF Quantization

**Quantization** is the cornerstone technology that makes running large language models feasible on consumer-grade hardware by drastically reducing the memory footprint.

*   **Necessity:** A 7-billion-parameter model in full precision (FP16) typically requires approximately 14GB, which is infeasible for most consumer GPUs. Quantization, such as using 4-bit integers, reduces this requirement to as little as 4–5GB.
*   **Format Standard:** The **GGUF format** (or General Graph Universal Format) has emerged as the standard for storing and loading quantized local models, offering broad compatibility across various inference engines.

### Q4_K_M Format

**Q4\_K\_M** is the mandated quantization format for stable deployment due to its optimized efficiency.

*   **VRAM Feasibility:** For a strict **6GB VRAM constraint**, the **4-bit (Q4\_K\_M) format is the only viable solution**. It reduces the base model footprint to 3–4 GB, leaving a crucial safety margin of 0.5 GB to 1.5 GB after accounting for input and KV cache overhead, ensuring operational stability.
*   **Quality/Efficiency Balance:** Q4\_K\_M is frequently recommended as it strikes a balanced compromise between file size, quality, and inference speed. Pushing to very low bit rates, such as Q2\_K, can lead to a noticeable degradation in model quality.

## llama-cpp-python Integration

The deployment strategy hinges on using high-performance inference engines optimized for the GGUF format.

*   **Core Engine:** **Llama.cpp** is a high-performance inference engine written in C++ that primarily utilizes the GGUF format and supports acceleration on both CPUs and GPUs.
*   **Python Binding:** The Python binding, **`llama-cpp-python`**, must be used for integration into the Python-based Scribe pipeline.
*   **Hybrid Inference:** `llama.cpp` supports **CPU+GPU hybrid inference** to partially accelerate models larger than the total VRAM capacity. This is managed by the `-ngl` (Number of GPU Layers) flag.
*   **Multimodal Support:** `llama.cpp` has merged multimodal support, including LLaVA and Qwen2-VL models, facilitating potential future feature integration.

## Deployment Guidelines

The LLM is deployed via the Summary Worker component (or `MeetingSynthesizer`) as Stage 6 of the pipeline.

1.  **Model Acquisition:** Download the chosen model in the highly optimized **GGUF Q4\_K\_M format**.
2.  **Configuration:** The deployment must target the chosen, optimized, quantized LLM (e.g., LLaMA 3.1-8B) via the `llama-cpp-python` binding.
3.  **VRAM Tuning:** Implement the `-ngl` (Number of GPU Layers) configuration flag within the `llama.cpp` wrapper to precisely control how many layers are offloaded to the GPU versus the CPU, maximizing VRAM utilization while ensuring model stability.
4.  **Workflow Integration:** The deployed LLM is explicitly used in the sequential **Map-Reduce workflow**, handling the final synthesis during the **Reduce Phase**. The subsequent refinement is achieved by applying the **Chain of Density (CoD) prompt template** to the synthesis output.
5.  **Efficiency Notes:** Utilizing modern attention mechanisms like **Flash Attention** and **KV Cache Quantization** (e.g., 8-bit or 4-bit integer cache) is crucial to reduce the memory footprint of the context window by 2x–4x, allowing the model to fit and process significantly longer meeting transcripts.