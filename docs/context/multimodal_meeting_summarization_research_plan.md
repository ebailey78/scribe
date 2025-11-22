# Multimodal Meeting Summarization Research Plan

**Category:** Project Scope, Architecture, and Roadmap  
**Purpose:** Resource Constraints Documentation

## Overview

This document stresses the architectural necessity of **dynamic resource allocation** and **cognitive specialization** to manage the tight VRAM budget in the **Advanced Meeting Processing System (AMPS)**. The fundamental design premise centers on maximizing computational throughput by strategically managing heterogeneous computing resources—namely, the CPU, the **6GB NVIDIA GPU**, and the **Intel Neural Processing Unit (NPU)**. The goal is to maximize information density and coherence while operating strictly within a computationally constrained, local environment.

The adoption of a **serialized "Record Now, Process Later" workflow** and the strict enforcement of memory constraints are **architectural necessities**. Synchronous, real-time processing paradigms invariably lead to catastrophic failure, severe performance degradation, and aggressive thermal throttling due to simultaneous demands exceeding the **6GB VRAM limit**.

## Resource Constraints

The architecture is defined by the constraints of the target hardware, which is a classic example of a "RAM-Rich, VRAM-Poor" environment.

| Hardware Component | Constraint/Limit | Consequence for Pipeline Design |
| :--- | :--- | :--- |
| **NVIDIA GPU** | **6GB VRAM** | **Mandatory aggressive quantization** (Q4/Q5 bit precision) for models > 1.5 billion parameters. |
| **System RAM** | **32GB DDR5** | Provides substantial operational buffer and supports memory-mapped models (GGUF offloading), acting as a crucial fallback for CPU inference. |
| **Intel NPU** | **Static 1024-token prompt limit** | Requires the LLM workflow to use the **Map-Reduce pattern**; the NPU cannot perform full-context summarization on long transcripts. |

The 6GB VRAM constraint is the **single most significant architectural constraint**. It immediately disqualifies standard floating-point precision models (FP16/BF16) above $1.5$ billion parameters. Furthermore, standard 8-billion parameter models, even when quantized, consume approximately **4.5GB to 5GB of VRAM**, leaving minimal room for overhead.

## VRAM Budget Management

Rigid adherence to the VRAM budget requires mandatory optimization techniques and strict accounting for overhead.

1.  **Quantization Mandate:** Aggressive quantization (specifically **Q4 or Q5 bit precision**) is mandatory for 7B to 8B parameter class models to fit within the 6GB VRAM. The **GGUF format** is the required standard for storing and loading these quantized local models via engines like `llama.cpp`.
2.  **Overhead Accounting:** The architecture must account for several types of memory overhead that consume VRAM *beyond* the base model weights:
    *   **Vision Encoder:** VLM vision encoders consume approximately **800MB to 1.5GB** of VRAM. For maximum OCR accuracy, this encoder is often kept at higher precision (FP16).
    *   **KV Cache:** The Key-Value (KV) cache, which stores context history, must reside in VRAM. This cache can consume 1GB to 2GB for reasonably sized contexts.
    *   **High-Resolution Input Tax:** Processing a single high-resolution image consumes an additional **1.2 GB to 1.5 GB** of VRAM for the prompt and generated output.
3.  **Feasibility Example (Qwen 7B):** The **Qwen 2.5 7B** model in **Q5\_K\_M quantization** is approximately **5.53 GB**, fitting tightly but functionally within the 6GB envelope. The LLaVA-1.5 7B multimodal model requires approximately 5–6 GB VRAM when quantized. Models in the 8B class, such as the Qwen3-VL-8B in Q4\_K\_M ($\sim$ 5.03 GB), are considered a **FAILURE** risk due to insufficient VRAM remaining for context or image overhead.

## Dynamic Resource Allocation

Resource contention is managed by architecting a **hybrid concurrency model** that uses explicit separation and scheduling.

1.  **Decoupling and Serialization:** The architecture is fundamentally based on the **"Record Now, Process Later"** workflow. This decouples I/O-bound tasks (capture) from compute-heavy tasks (inference), allowing the pipeline to operate asynchronously and ensuring jobs complete reliably, even if processing must occur invisibly in the background.
2.  **Concurrency Model:** The system uses Python's `asyncio` for non-blocking I/O tasks and the **`multiprocessing` library** for compute-heavy tasks to achieve true parallelism and utilize the GPU/NPU. The process flow is serialized, orchestrated by a CPU-managed, persistent **SQLite-backed task queue**.
3.  **Exclusive Access Policy (Mutual Exclusion):** The orchestration layer must enforce a strict **Exclusive Access Policy** using a resource lock (GPU Lock or semaphore). This is critical to ensure the memory-intensive VLM and LLM/Summary Worker **never attempt to occupy the 6GB VRAM simultaneously**.
4.  **Load-Inference-Unload Cycle:** Workers must execute a **load-inference-unload cycle**. The Visual Worker acquires the lock, loads its VLM, processes a batch of screenshots, and then **explicitly unloads the model** (e.g., calling `torch.cuda.empty_cache()`) before releasing the lock, freeing up memory for the next worker.

## Cognitive Specialization

The pipeline's high performance is achieved by implementing a **separation of concerns** strategy, leveraging specialized models and processors for distinct cognitive stages.

| Specialized Hardware/Module | Designated Role | Task Focus | Source |
| :--- | :--- | :--- | :--- |
| **NVIDIA GPU (Burst Processor)** | High-throughput, memory-intensive inference. | **VLM Inference** (Visual Analysis), **LLM Reduction** (Final Synthesis), and Diarization. | |
| **Intel NPU (Endurance Engine)** | Energy-efficient, continuous stream processing. | **Audio Encoder** stage (Whisper), and LLM **Map Phase** (simple, chunk-level summarization). | |
| **Lightweight CVM (MobileViT-S)** | Compute Filter. | Rapid content classification (e.g., filtering static screenshots) to conserve VRAM by preventing irrelevant images from reaching the VLM. | |
| **SLM (Qwen2.5-Coder-1.5B)** | Syntax Repair. | Deployed on the NPU to fix OCR errors in code snippets without consuming GPU VRAM. | |

This specialization is an **architectural necessity** because raw ASR output forces the small LLM to simultaneously solve multiple NLP problems (cleaning, structuring, and abstraction), which inevitably degrades final summary quality.

## Trade-offs and Optimization Strategies

Achieving the required performance demands accepting certain trade-offs and implementing advanced optimization techniques:

1.  **Map-Reduce Necessity:** To process long transcripts (e.g., 10,000+ tokens) and respect the NPU's static 1024-token constraint, the pipeline must employ the **Map-Reduce pattern**. The constrained **NPU** is leveraged only for the simple **Map phase** (chunk-level summaries), while the powerful **GPU LLM** is reserved for the complex **Reduce phase** (final synthesis).
2.  **Context Window Optimization:** To fit long contexts within the 6GB VRAM, the LLM must utilize **Flash Attention** (a memory-efficient attention mechanism) and **KV Cache Quantization** (storing the cache in 4-bit or 8-bit integer format). Quantizing the cache can reduce its memory footprint by **2x to 4x** with negligible quality degradation.
3.  **Latency vs. Stability:** The reliance on the "load-inference-unload" cycle (Dynamic Model Swapping) adds a latency penalty of **2–5 seconds** during model reloading. This is a necessary trade-off to guarantee stability and prevent Out-Of-Memory (OOM) crashes in the constrained environment.
4.  **Data Structuring:** To mitigate context loss inherent in chunking, **Metadata Header Injection** is mandated for every chunk. This prepends context such as active speakers or the previous topic summary, helping the small LLM resolve anaphora across chunk boundaries.
