# Map-Reduce Workflow (L5)

**Priority:** HIGH - Long-Context Management

## Objective

The objective is to process transcripts exceeding **10,000 tokens** (typical for one hour of audio) within the practical context limits of small, locally deployed Large Language Models (LLMs) (7B-8B). This multi-step prompt engineering workflow is necessary to handle long documents that exceed the finite context window capacity of these small LLMs.

## Why Map-Reduce

The Map-Reduce pattern is the **industry standard for handling long documents**.

*   **More robust than Iterative Refinement (less recency bias):** The Map-Reduce pattern is the **demonstrably more robust choice** compared to the Iterative Refinement (Refine) mechanism. It is less prone to **"recency bias"** (where the model forgets information at the beginning of the meeting).
*   **Parallelizable (faster execution):** The Map step is **highly distributed and parallelizable**. This allows the creation of segment summaries in parallel, which is faster than the sequential approach of Iterative Refinement.
*   **Error isolation (one chunk error doesn't corrupt entire draft):** Because the Map step processes chunks independently, an **error in one chunk summary does not corrupt the entire draft**.

## Map Phase: Extraction

The Map phase is the **extraction phase**. It involves the LLM individually applying an extraction chain to each chunk.

*   **Input:** The Map phase utilizes the **semantically segmented blocks** (chunks) that were created by the L4 Segmentation stage (TextTiling). Using these logical blocks ensures contextual coherence for summarization.
*   **Process:** The LLM applies an extraction chain to **EACH chunk**.
*   **Output:** The result is a list of atomic facts, themes, or **distilled mini-summaries** for each segment.
*   **Prompt Strategy:**
    *   The **Map Prompt** instructs the model to extract all **key entities, facts, and themes *only*** from the provided segment.
    *   The prompt must **strictly maintain the speaker attribution context** that was supplied by the Diarization stage (L2 Structuring).
*   **Execution:** The Map step is **highly distributed and parallelizable**.

## Reduce Phase: Synthesis

The Reduce step is the **synthesis phase**, which consolidates the outputs from the Map step.

*   **Input:** The resulting Mapped summaries—a **significantly condensed text**—are concatenated to form a "summary of summaries".
*   **Process:** The consolidated input is fed back into the LLM, which performs the **final, single abstractive synthesis** of the entire document. This approach minimizes the cognitive load and complexity placed on the smaller LLM.
*   **Output:** A coherent final summary.
*   **LLM Target:** This final synthesis is handled by the primary, **more powerful GPU-based LLM**. The LLM reserved for this step (e.g., LLaMA 3.1-8B) is the **strategic choice** because of its demonstrated **superior long-context scaling capability**.

## Context Window Strategy

Map-Reduce is necessary because LLMs are **token-count-limited**.

*   **Semantic chunks fit within LLM limits:** The Map phase utilizes the semantically segmented blocks. The segmentation output must be sized to fit within the model’s context window. For instance, chunks are sized to **800 tokens** to comfortably fit within the NPU's static prompt constraint of **1024 tokens**.
*   **Small overlap between chunks (1-2 sentences) for continuity:** A **small overlap** (e.g., 1-2 sentences) between chunks is **advisable** to ensure continuity across segments.
*   **Metadata headers provide cross-chunk context:** To mitigate the inevitable context loss caused by segmentation, the pipeline should **inject metadata headers** (e.g., previous topic summaries, active speaker lists) into every chunk. This helps the LLM **resolve anaphora** across segment boundaries.

## Implementation Pattern

```python
# Map
map_outputs = []
for chunk in semantic_chunks:
    summary = llm.extract(chunk, preserve_speakers=True)
    map_outputs.append(summary)

# Reduce
condensed_input = "\n".join(map_outputs)
final_summary = llm.synthesize(condensed_input)
```

## Hardware Offloading (Optional)

This tiered approach is crucial for managing the 6GB VRAM constraint and the NPU's limitations.

*   **NPU:** The Map phase is executed in parallel and is ideally offloaded to the **Intel NPU** via OpenVINO. The NPU is leveraged for this task because generating distilled mini-summaries requires **minimal deep reasoning**, making it an ideal candidate for offloading. The NPU's static **1024-token limit** means it is restricted to processing these small **Map** segments.
*   **GPU:** The **NVIDIA GPU** is reserved for the **Reduce phase** (final consolidation and synthesis). This ensures the more powerful LLM (e.g., Qwen 2.5 7B) can dedicate its full computational power to the final, high-quality output generation.

## Integration

The output of the Map-Reduce workflow (the consolidated summary) **feeds directly into L6 Chain of Density** for final refinement. CoD is applied **exclusively to the final, consolidated output** generated by the Reduce step, optimizing the small LLM's processing cycles.