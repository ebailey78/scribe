# Implementation Roadmap

**Priority:** CRITICAL - Sequential Execution Required

## Phase Sequence

| Phase | Steps | Rationale & Key Requirements |
| :--- | :--- | :--- |
| ### Phase 0: Infrastructure | **Hugging Face token (Pyannote requirement)** | Pyannote models (e.g., `pyannote/speaker-diarization-3.1`) require the user to **accept model agreements** and authenticate using a **Hugging Face Access Token**. |
| | **Install: `faster-whisper`, `pyannote.audio`, `fuzzywuzzy`, `readless`, `llama-cpp-python`** | `faster-whisper` (CTranslate2) is required for **up to 4x faster inference**. `fuzzywuzzy` and `readless` support L3 correction and L4 segmentation. `llama-cpp-python` is the binding for GGUF model deployment. **`ffmpeg`** must be installed system-wide. |
| | **GPU/CUDA verification** | GPU acceleration is **strongly recommended** for diarization, as CPU processing is **much slower** (1 hour audio takes 2–4 hours). Must confirm `onnxruntime-gpu` is correctly installed and active. |
| | **WSL2 setup (Windows, for Pyannote stability)** | **Pyannote.audio** is only guaranteed to run reliably on Linux/macOS. WSL2 with native CUDA pass-through is the required environment for stable operation on Windows. |
| ### Phase 1: L1 Normalization | **Punctuation restoration (rpunct or GECToR)** | This task, using specialized models (like rpunct, with $\mathbf{91\%}$ overall accuracy), must execute first to restore capitalization and define **sentence boundaries**, which are essential for downstream tasks like semantic segmentation. |
| | **Dysfluency removal (FlashText)** | Implements a lightweight cleanup module to strip filler words (`um`, `uh`) and repetitions. **FlashText** is specified due to its highly efficient **linear time complexity O(N)**. |
| | **Integrate into Transcriber output** | The output of this stage must be the **fully cleaned and punctuated text**, enforcing the **Sequential Cascading** rule that this clean output serves as the input base for all subsequent stages. |
| ### Phase 2: L2 Diarization | **WhisperX integration** | **WhisperX** is the recommended integrated solution, combining `faster-whisper` with `pyannote.audio`. It is ideal because it provides a **combined transcription + speaker diarization pipeline**. |
| | **Word-level timestamp verification** | This is a structural requirement. The pipeline must use **Phoneme-Based Forced Alignment** (via WhisperX/wav2vec2) to generate **precise timestamps for every individual word**. |
| | **Speaker alignment logic** | Implement the **"glue" operation** that assigns a **Speaker ID** (e.g., SPEAKER\_00) to each transcribed utterance based on the **greatest temporal overlap** with the Pyannote segments. Speaker attribution is **non-negotiable** for summarization. |
| ### Phase 3: L3 Correction + L4 Segmentation | **Jargon correction (fuzzywuzzy, threshold ≥85%)** | The module must use fuzzy matching (e.g., **`fuzzywuzzy`**) based on **Levenshtein Distance** to guarantee the **fidelity of domain-specific entities** against the authoritative jargon list. A high confidence threshold ($\ge$ 85%) is required for replacement. |
| | **TextTiling semantic segmentation** | This module must replace arbitrary 1000-word block splitting with **Semantic Segmentation**. The **TextTiling** algorithm is used to divide the text into logical blocks based on **topic shifts**, ensuring contextual coherence. |
| | **Metadata header injection** | Develop logic to prepend a structured **metadata header** (e.g., active speakers, previous topic summary) to each segment to **mitigate context loss** and aid the LLM in resolving anaphora across chunk boundaries. |
| ### Phase 4: L5 Map-Reduce | **Map phase: atomic fact extraction** | The LLM performs **atomic fact extraction** (not summarization) on **each semantic chunk**, strictly **preserving the speaker attribution context**. This process is **highly distributed and parallelizable**. |
| | **Reduce phase: final synthesis** | The primary GPU LLM performs the **final abstractive synthesis** on the consolidated, condensed Map summaries (a "summary of summaries"), focusing its power on high-level reasoning. |
| | **Parallel execution framework** | Implement a framework using the `multiprocessing Pool`. For resource efficiency, the **Map phase is ideally offloaded** to the **Intel NPU** via OpenVINO, reserving the more powerful **NVIDIA GPU** for the Reduce phase. |
| ### Phase 5: L6 Chain of Density | **CoD prompt template (3-5 iterations)** | Apply the **Chain of Density (CoD)** prompt to the Reduce output. This forces **iterative refinement** by integrating **1–3 novel entities** while maintaining **fixed length through compression**. Three iterations are often the human-preferred median. |
| | **JSON output validation** | The final output must adhere to a strict **JSON schema**, demonstrating the LLM's **instruction adherence**. The Qwen series is favored for excelling at JSON generation. |
| ### Phase 6: Async Orchestration | **SQLite task queue** | Implement a persistent, serverless queue using **SQLite** to manage the pipeline state and ensure data integrity in the **"Record Now, Process Later"** workflow. |
| | **Producer-Consumer pattern** | Utilize this pattern to **decouple the fast audio ingestion** (Producer, I/O bound) from the **slow AI compute** (Consumer, compute-bound) using `asyncio` and `multiprocessing`. |
| | **GPU resource locking** | Implement a **Foreman** script that enforces an **Exclusive Access Policy** (Mutual Exclusion) using a **GPU semaphore/lock** to prevent memory contention. This is mandatory to ensure the VLM/LLM **never attempt to occupy the 6GB VRAM simultaneously**. |

## Model Selection

The selection prioritizes **long-context stability** and **VRAM fit** under the strict 6GB constraint.

| Parameter | Selection | Rationale |
| :--- | :--- | :--- |
| **Primary** | **LLaMA 3.1-8B-Instruct** | Strategically chosen for its **superior long-context scaling capability** compared to other small models (up to 128K tokens), which is crucial for the Map-Reduce synthesis. |
| **Alternative** | **Qwen 2.5 7B** or **Qwen3-8B** | **Qwen 2.5 7B** is noted for its strong performance and, in **Q4\_K\_M quantization ($\approx$ 4.5GB)**, fits tightly but functionally within the 6GB envelope. The Qwen series is also noted for **superior instruction adherence** and structured output capabilities. |
| **Format** | **GGUF Q4\_K\_M** | **Aggressive quantization** (Q4 or Q5 bit precision) is **mandatory**. **GGUF** is the standard format used via `llama-cpp-python`, as the **6GB VRAM limit** immediately disqualifies standard floating-point precision models (FP16). |

## Validation

After each phase: import tests, integration tests, VRAM monitoring

*   **VRAM Monitoring:** Critical to ensure that the sequential loading pattern and GPU locking logic successfully keep the active model weights **strictly within dedicated VRAM** to maintain acceptable inference speeds and prevent system crashes caused by memory swapping.
*   **Timestamp/Attribution Tests (Phase 2):** Validation must confirm that the word-level speaker assignment is accurate to prevent **poisoning the context** for the LLM with misattributed dialogue.
*   **LLM Integrity Tests (Phases 4 & 5):** Validation should test for adherence to the **JSON output schema** and confirm that the Map-Reduce workflow successfully processes documents exceeding 10,000 tokens.