# Hardware Constraints & Async Orchestration

**Priority:** CRITICAL - Defines All Architectural Decisions

## VRAM Constraint: 6GB

The **6GB NVIDIA GPU VRAM** represents the **single most significant architectural constraint**.

**Impact:**
*   **Mandatory Q4/Q5 quantization for 7B+ models:** Standard FP16 models above 1.5B parameters are immediately disqualified. Quantization, such as using 4-bit or 8-bit integers, drastically reduces the memory footprint.
*   **Aggressive optimization required:** The LLM architecture must utilize optimization techniques like **Flash Attention** and **KV Cache Quantization** (e.g., storing the cache in 8-bit or 4-bit integer format) to reduce context memory footprint by $2\times$ to $4\times$.
*   **Sequential task execution (not parallel):** A synchronous workflow attempting to run simultaneous memory-intensive tasks would exceed the VRAM limit, causing performance to degrade by orders of magnitude.

**Budget Breakdown:**
| Component | Requirement | Estimate | Source |
| :--- | :--- | :--- | :--- |
| **Model weights (Q4\_K\_M)** | Base weights for 7B/8B models | **~4.5-5.5 GB** | Qwen 2.5 7B Q5\_K\_M is $\approx$ 5.53 GB; LLaMA 3.1 8B is 4.9GB. |
| **KV Cache** | Context history storage | **~1-2 GB** | A 10,000 token context can consume over 5GB VRAM just for the cache in FP16; this must be reduced via quantization. |
| **Vision Encoder (VLMs)** | For multimodal tasks (LLaVA/Qwen3-VL) | **~800MB-1.5 GB** | The VLM vision encoder consumes substantial VRAM. The Qwen3-VL Vision Encoder is $\sim$1.3 GB in FP16. |
| **GPU overhead** | OS / Display buffers / System | **~500MB-1 GB** | The OS typically reserves 0.5GB to 1GB for display/background buffers. |

**Result:** **Only one major model can be active in VRAM at a time**. The total consumption of an 8B LLM/VLM plus overhead mathematically exceeds the 6GB capacity, making **hybrid inference mandatory**.

## Asynchronous Workflow

**Paradigm Shift:** **"Record Now, Process Later"**

**Why:**
*   **Synchronous real-time = VRAM overflow → memory swapping → thermal throttling:** Attempts at real-time processing force the OS to swap memory across the PCIe bus, resulting in severe performance degradation and thermal load.
*   **Serialized async = each task gets full memory envelope:** By decoupling the data capture from the inference, the system can leverage the entire thermal and memory envelope of the device for **each specific task in sequence**.

**Architecture:**
*   **I/O (Capture):** Handled by the **asyncio event loop**. Capture must be fast and **non-blocking**.
*   **Compute (Inference):** Must be slow and **serialized** on the GPU to manage the VRAM constraint. Compute tasks run in separate OS processes using the `multiprocessing` library to achieve **true parallelism**.
*   **Queue:** **SQLite** is the preferred ideal "serverless" queue for a local, single-user application.

**Concurrency Model:**
| Layer | Mechanism | Hardware | Notes on GIL Management |
| :--- | :--- | :--- | :--- |
| **Audio/Visual Capture** | **asyncio Event Loop** / `asyncio.Queue` (Producer-Consumer) | CPU/RAM | Non-blocking scheduling for high-rate data streams. |
| **Heavy Inference** (ASR/LLM/VLM) | **multiprocessing Pool** (Dedicated processes) | NVIDIA GPU (CUDA), Intel NPU (OpenVINO) | Essential for parallel execution of compute-heavy tasks; bypasses the GIL. |
| **Blocking I/O** (File Saves, Tesseract OCR) | **asyncio.to_thread()** | CPU Thread Pool | Safely isolates synchronous system calls from the event loop. |

## Specialized Offloading

The overarching strategy is **Specialized Offloading**, where tasks are partitioned based on their computational specialization and framework dependencies.

| Processor | Role | Tasks | Source |
| :--- | :--- | :--- | :--- |
| **NVIDIA GPU (6GB)** | **Burst Processor** | **VLM Inference** (Visual Analysis); **LLM Reduce Phase** (Final Synthesis); **Speaker Diarization** (Must run on CUDA for performance). |
| **Intel NPU** | **Endurance Engine** | **Audio Encoder** stage (Whisper Encoder via OpenVINO); **LLM Map Phase** (chunk-level summarization). |
| **CPU (32GB RAM)** | **Orchestrator** | **SQLite Task Queue** management; Whisper Decoder phase; Scene detection; **Fallback execution environment** for LLM if GPU VRAM is exceeded. |

## GPU Exclusive Access Policy

**MANDATE:** **VLM and LLM NEVER occupy VRAM simultaneously**.

**Mechanism:**
*   **Foreman manages GPU lock (database flag/semaphore):** A central script, the **Foreman**, manages the persistent **Resource Locking** logic, typically using a database flag or semaphore.
*   **Load-Inference-Unload cycle:** The worker must load its model (e.g., LLaVA-1.5 7B), process a batch of tasks, and then **immediately unload the model** from VRAM (involving deleting the object and calling memory cleanup routines like `torch.cuda.empty_cache()`) before releasing the lock.

**Latency Trade-off:** The "load-inference-unload" cycle adds a **latency penalty of 2–5 seconds** during model reloading. This cost is accepted because it guarantees reliability and prevents catastrophic Out-Of-Memory (OOM) crashes in the constrained environment.

## SQLite Task Queue

SQLite is the ideal "serverless" queue for local, single-user applications, avoiding the overhead of external servers.

**Schema:**
```sql
CREATE TABLE jobs (
  job_id INTEGER PRIMARY KEY,
  meeting_id TEXT,
  task_type TEXT,  -- 'AUDIO', 'VISUAL', 'SUMMARY'
  status TEXT,     -- 'PENDING', 'PROCESSING', 'COMPLETED', 'FAILED'
  chunk_path TEXT,
  created_at TIMESTAMP
);
```

**Benefits:**
*   **ACID transactions (crash-resilient):** Ensures data integrity, meaning the database will not be corrupted if the system fails mid-write.
*   **WAL mode (concurrent read/write):** Supports concurrent access via the Write-Ahead Logging journal mode, allowing ingestion (Producer) and processing (Consumer) to operate simultaneously.
*   **Persistent state machine:** Tracks the complex state of the pipeline, ensuring jobs can resume after reboots.
*   **Natural checkpoints (1-2min chunks):** Pre-chunking the audio into small units creates natural "checkpoints" for the processing pipeline, preventing a single failure from corrupting the entire meeting record.

## Process Priority

Active management of process scheduling is required to ensure the asynchronous pipeline does not render the system unresponsive during a user's active session.

*   **Windows:** The heavy inference process should be set to **`BELOW_NORMAL_PRIORITY_CLASS`**. This allows user interactions and foreground applications to preempt the AI workload, preserving system responsiveness.
*   **CPU Affinity:** If the hardware uses Intel's Hybrid Architecture (Core Ultra), it is crucial to pin the inference threads to the **P-Cores** (Performance Cores). This prevents the heavy AVX/AVX2 instructions, used by inference engines like `llama.cpp`, from being scheduled on E-Cores (Efficiency Cores), which lack these instructions and would drastically slow down the pipeline.