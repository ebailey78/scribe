# Asynchronous Meeting Processing Pipeline

**Category:** Asynchronous & Hardware Management

## Overview

The deployment of sophisticated AI pipelines on constrained consumer-grade hardware (such as a system with a 6GB VRAM GPU and an Intel NPU) necessitates a fundamental architectural shift away from synchronous, real-time processing. A synchronous workflow attempting to run simultaneous memory-intensive tasks—such as ASR, Diarization, and LLM inference—would invariably exceed the 6GB VRAM limit, causing performance to degrade by orders of magnitude due to memory swapping across the PCIe bus and triggering aggressive thermal throttling.

This document justifies the adoption of an asynchronous, serialized **"Record Now, Process Later"** workflow. This approach transforms the meeting from a real-time stream demanding immediate servicing into a static dataset that can be processed sequentially. Central to this architecture is the use of a **persistent, SQLite-backed task queue** that ensures data integrity and allows processing to occur invisibly in the background.

## "Record Now, Process Later" Workflow

This workflow represents a fundamental architectural compromise to ensure stability and maximum throughput on edge constraints.

*   **Decoupling Capture and Compute:** The workflow strictly **decouples the high-speed data capture phase** (I/O-bound tasks like audio capture) from the **inference phase** (compute-heavy tasks like LLM synthesis).
*   **Sequential Resource Utilization:** By serializing the compute tasks, the architecture allows the system to leverage the **entire thermal and memory envelope** of the device for each specific task in sequence. For example, a Vision Language Model (VLM) can be granted exclusive access to the full 6GB VRAM for visual analysis, and once unloaded, the Large Language Model (LLM) can be loaded for synthesis.
*   **Resilience:** Decoupling ensures that sudden latency spikes in the compute stage do not propagate backward and block the critical, time-sensitive data capture process. The flow transforms the meeting into a static dataset that can be mined with precision, even overnight.
*   **Efficiency:** This shift allows computational tasks to be executed in parallel operating system processes using the `multiprocessing` library, maximizing parallel compute capacity across the CPU, GPU, and NPU.

## SQLite as Task Queue

For a local, single-user application, **SQLite** is identified as the ideal "serverless" queue, avoiding the unnecessary overhead of server-based queues like Redis or RabbitMQ.

*   **ACID Compliance:** SQLite supports **ACID transactions** (Atomicity, Consistency, Isolation, Durability), meaning if the laptop shuts down mid-write, the database will not be corrupted, making the system resilient to crashes and reboots.
*   **Concurrency Support:** SQLite supports concurrent access via the **Write-Ahead Logging (WAL) journal mode**, allowing the ingestion script to write new jobs while the worker scripts read and process them.
*   **Producer-Consumer Facilitation:** The queue serves as the buffer and communication point between **producers** (ingestion scripts that add items) and **consumers** (worker scripts that pull items), enabling a scalable and responsive system.

## Persistent Data Backbone

The SQLite database functions as the resilient **data backbone** and state machine for the entire pipeline.

*   **State Management:** The database tracks the complex state of the pipeline, which is essential for a resilient "set and forget" workflow.
*   **Schema Design:** The schema defines the state of the pipeline using a `jobs` table that tracks every unit of work. Key columns include `job_id`, `meeting_id` (linking chunks to a session), `task_type` (`AUDIO`, `VISUAL`, `SUMMARY`), and `status` (`PENDING`, `PROCESSING`, `COMPLETED`, `FAILED`).
*   **Data Integrity:** This persistence layer ensures that processing continues even after failures, guaranteeing that jobs will eventually complete and delivering high-fidelity intelligence. Each 1-2 minute audio chunk is treated as an independent job unit, creating natural **"checkpoints"** for the processing pipeline and preventing single failures from corrupting the entire meeting record.

## Asynchronous Processing Benefits

The shift to asynchronous processing is an **architectural necessity** driven by resource constraints.

*   **VRAM Protection:** The methodology eliminates the memory contention and paging issues caused by trying to run multiple large models simultaneously on the **6GB VRAM GPU**.
*   **High Throughput:** The **Producer-Consumer pattern** facilitates high-throughput data ingestion while performing high-latency AI inference simultaneously. The producer (I/O) rapidly ingests data chunks and places them into the queue, while slower consumers (compute) pull items at their own pace.
*   **Hardware Specialization:** It enables **Specialized Offloading**, where the Intel NPU is designated for power-efficient audio encoding (Whisper Encoder) while the GPU is reserved exclusively for burst-heavy tasks (VLM/LLM inference).
*   **Context Management:** Sophisticated long-document summarization strategies, such as the **Map-Reduce pattern**, are inherently parallelizable, taking advantage of asynchronous execution to reduce overall latency compared to sequential refinement approaches.

## Implementation Architecture

The architecture relies on a **hybrid concurrency model** that leverages the specific strengths of Python's concurrency mechanisms.

| Processing Stage | Concurrency Mechanism | Hardware Target | GIL Management |
| :--- | :--- | :--- | :--- |
| **I/O Capture Loops** | `asyncio` Event Loop, `asyncio.Queue` | CPU/RAM | Non-blocking scheduling for high-rate data streams |
| **Blocking I/O** (File Saves) | `asyncio.to_thread()` | CPU Thread Pool | Safely isolates synchronous system calls from the event loop |
| **Heavy Inference** (ASR, LLM, VLM) | `multiprocessing` Pool | NVIDIA GPU (CUDA), Intel NPU (OpenVINO) | Bypasses the GIL to achieve true parallelism |

The logical flow is a **Pipeline or Chain processing** sequence, where the output of the L1 Normalization job feeds the L2 Structuring job, and so on.

## Task Management

The central command and control structure for the asynchronous pipeline is managed by a dedicated software agent called the **Foreman**.

*   **Resource Locking (Mutual Exclusion):** The Foreman implements the critical **Resource Locking** logic, typically using a database flag (`gpu_locked`) or semaphore to ensure the VLM (Visual Worker) and the LLM (Summary Worker) never attempt to occupy the 6GB VRAM simultaneously. The Visual Worker processes a batch of screenshots, explicitly **unloads the model** from VRAM (e.g., using `del model` and `torch.cuda.empty_cache()`), and then releases the lock.
*   **Prioritization:** The Foreman manages the task queue, ensuring heavy computation tasks are scheduled logically (e.g., visual analysis must finish before final summarization begins).
*   **Process Tuning:** To prevent the background pipeline from degrading the user experience, the inference process should be set to **`BELOW_NORMAL_PRIORITY_CLASS`**. Furthermore, when deploying on hybrid CPUs (Intel Core Ultra), inference threads must be constrained or pinned to the **P-Cores** (Performance Cores) to avoid the drastic slowdown caused by using E-Cores (Efficiency Cores), which lack the necessary AVX instructions for fast inference.
