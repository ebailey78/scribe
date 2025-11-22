The following document defines the strategic approach for managing and allocating compute resources across the system's heterogeneous hardware (CPU, NVIDIA GPU, Intel NPU) under the strict **6GB VRAM constraint**.

---

# Hardware Offloading Strategy

**Category:** Asynchronous & Hardware Management

## Overview

The deployment of a sophisticated, multimodal AI pipeline on constrained consumer hardware (specifically targeting a system with a **6GB VRAM GPU** and an **Intel NPU**) necessitates a fundamental shift away from synchronous, real-time processing. The foundational strategy is **Specialized Offloading**.

This architectural philosophy is governed by the **separation of concerns** principle. Instead of running all memory-intensive tasks simultaneously—which would exceed the **6GB VRAM limit** and trigger performance-degrading memory swapping—the system utilizes an asynchronous, serialized **"Record Now, Process Later"** workflow. This approach ensures that the entire thermal and memory envelope of the device can be dedicated to **each specific task in sequence**.

## Specialized Offloading Principle

The principle of Specialized Offloading dictates that specific tasks are routed to the processor best suited for their architectural profile, energy consumption, and compute demands. This strategy ensures maximum computational throughput by strategically managing heterogeneous computing resources.

*   **NPU (Endurance Engine):** Reserved for tasks that benefit from energy efficiency and continuous stream processing, such as the non-autoregressive **Audio Encoder**.
*   **GPU (Burst Processor):** Reserved for high-throughput, memory-intensive inference tasks that require the massive parallel processing of CUDA cores, such as **Diarization**, **VLM Inference**, and **Final LLM Synthesis**.
*   **CPU (Orchestrator):** Handles sequential logic, file I/O, state management (via the task queue), and serves as the general fallback for compute failures.

## NPU Assignment

The Intel Neural Processing Unit (NPU) is designated to handle specific AI tasks to free up the constrained GPU VRAM.

### Audio Encoder Stage (Whisper)

The NPU is assigned as the primary engine for the **Audio Encoder** stage of the Whisper transcription process. The Whisper architecture—an Encoder-Decoder Transformer—presents a unique optimization opportunity for the NPU.

*   **Split Execution:** The pipeline uses a split-execution model where the **Transformer encoder**, which processes the raw audio mel-spectrograms in parallel, is offloaded to the NPU. This is a computationally dense matrix-multiplication task that aligns well with the NPU's architecture.
*   **Decoder Assignment:** The autoregressive decoder component (which generates text token by token) remains on the CPU. This prevents the NPU from stalling on serial tasks it is less optimized for.
*   **Implementation:** This is achieved using inference engines optimized for Intel hardware, such as `whisper.cpp` compiled with **OpenVINO support**.

### Energy Efficiency

The NPU is optimized for **energy efficiency and continuous stream processing**. By offloading the constant audio processing workload from the GPU, the NPU prevents the GPU from being continuously utilized for background tasks. This strategy ensures the GPU remains completely free for burst-heavy workloads like **visual analysis**.

## GPU Exclusive Access Policy

The 6GB NVIDIA GPU is the system's most powerful, yet most constrained asset. The memory footprint of 7B and 8B models, even when highly quantized, requires this resource to be used as a Burst Processor, necessitating a strict access policy.

### Mutual Exclusion

The orchestration layer must enforce a strict **Exclusive Access Policy** (Mutual Exclusion). The primary goal is to ensure that the **Visual Language Model (VLM)** and the **Large Language Model (LLM)** **never attempt to occupy the 6GB VRAM simultaneously**. Simultaneous execution would exceed the capacity and cause performance-degrading memory paging across the slow PCIe bus.

*   **GPU Role:** The GPU is reserved exclusively for the most demanding tasks: **Speaker Diarization**, **VLM Inference** (analyzing screenshots), and **LLM Summarization** (final synthesis).
*   **Sequencing Mandate:** The architecture must sequence VLM and LLM jobs so that one is processed and fully unloaded before the other begins.

### GPU Lock Mechanism

The resource locking is managed by a central command structure known as the **Foreman**.

*   **Lock Management:** The Foreman maintains a persistent resource lock, typically a **database flag** or **semaphore**, to prevent the GPU from being double-booked.
*   **Load-Inference-Unload Cycle:** When a worker (e.g., the Visual Worker) acquires the lock, it loads its specific model (e.g., Qwen3-VL-8B). After completing its batch, the worker must **explicitly unload the model** from VRAM by deleting the model object and invoking memory cleanup routines (e.g., `torch.cuda.empty_cache()`) before releasing the lock. This ensures the memory is available for the next worker.

## VRAM Budget (6GB)

The **6GB VRAM** constraint dictates the selection of model sizes and required optimization techniques.

### VLM/LLM Resource Management

Standard floating-point precision models (FP16) are disqualified, making **quantization mandatory**.

*   **Quantization Mandate:** To fit models in the target 7B–8B parameter range within the 6GB limit, **aggressive quantization** (specifically 4-bit or 5-bit precision, like **GGUF Q4\_K\_M**) must be adopted.
*   **LLM Fit:** A 7B model quantized to Q4 can consume approximately **4.5GB**. This leaves only about **1.5GB** of VRAM for the Key-Value (KV) cache (which stores context history) and system overhead.
*   **VLM Overhead:** Multimodal models (VLMs) like LLaVA-1.5 7B or Qwen3-VL-8B consume VRAM not only for the language model but also for a heavy **Vision Encoder** (upwards of 1.3GB), which may need to be kept at a higher precision (FP16) for OCR accuracy. This overhead makes it **physically impossible** to run a standard 7B VLM entirely on the GPU without offloading components.
*   **KV Cache Priority:** Due to its continuous access requirement, the **Key-Value (KV) Cache** for the LLM must be prioritized for VRAM residency. This cache can be optimized using **quantized cache techniques** (e.g., 8-bit or 4-bit integer cache) to reduce its memory footprint by $2\times$ to $4\times$.

## Implementation Guidelines

The overall implementation of the Hardware Offloading Strategy is supported by the **hybrid concurrency model** that separates I/O-bound tasks from compute-heavy tasks.

1.  **Concurrency Model:** Utilize the `asyncio` event loop for high-rate data streams (I/O) and the `multiprocessing` library for heavy inference tasks (Compute) to achieve true parallelism and bypass the GIL bottleneck.
2.  **Diarization Configuration:** The Speaker Diarization pipeline, which uses PyTorch-based models like `pyannote.audio`, must be explicitly configured to run on the GPU via CUDA (e.g., `pipeline.to(torch.device("cuda"))`) to prevent the severe 2–4 hour processing bottleneck experienced on CPU-only setups.
3.  **NPU Workflow Integration:** The Map-Reduce LLM workflow must be integrated with the NPU's constraints. Since the NPU has a static prompt limit (often 1024 tokens), the system should route the small, segment-level summarization tasks (**Map Phase**) to the NPU, while reserving the flexible, powerful **GPU LLM** for the final **Reduce Phase** (synthesis).
4.  **Process Management:** To maintain system responsiveness, the heavy compute processes running the LLMs should be set to **BELOW\_NORMAL\_PRIORITY\_CLASS**. If applicable, inference threads should be pinned to the high-performance P-Cores to avoid using the E-Cores, which lack the necessary AVX instructions for fast inference.
