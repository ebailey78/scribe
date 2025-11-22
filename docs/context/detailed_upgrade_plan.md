This plan details the steps necessary to upgrade the existing Scribe application (which currently handles real-time transcription and basic LLM synthesis) into the comprehensive, multi-stage **Optimized Offline ASR-to-LLM Summarization Pipeline**.

The core architectural philosophy of this upgrade is the **separation of concerns**, ensuring that resource-intensive, specialized tasks (like cleaning and structuring) are performed by dedicated modules before the text reaches the resource-constrained Large Language Model (LLM).

---

## Detailed Upgrade Plan: Scribe to Optimized Pipeline

The upgrade will proceed through six primary phases, corresponding to the stages defined in the architecture blueprints.

### Phase 0: Infrastructure and Core Dependency Setup

This phase focuses on preparing the execution environment, particularly securing the components required for speaker diarization and optimized LLM inference.

| Step | Goal/Action Item | Rationale & Key Technologies |
| :--- | :--- | :--- |
| **0.1** | **Configure Pyannote Access** | Diarization requires **`pyannote.audio`**, which necessitates obtaining and authenticating a **Hugging Face access token** for model downloads (e.g., `pyannote/speaker-diarization-3.1`). |
| **0.2** | **Install Diarization/ASR Components** | Install integrated solutions like **`whisperx`** (which includes `faster-whisper` and `pyannote` integration logic) or manually install core components: `pyannote.audio`, `faster-whisper`, and `ffmpeg`. |
| **0.3** | **Optimize GPU/Diarization Setup** | Due to known stability/performance constraints on Windows, deploy the pipeline within a **Windows Subsystem for Linux (WSL2)** environment with native CUDA pass-through, or ensure that the necessary CUDA toolkit and `onnxruntime-gpu` package are correctly installed and active for the diarization step. A **GPU is strongly recommended** to prevent the process from taking 2-4 hours for one hour of audio. |
| **0.4** | **Install Utility Libraries** | Install required libraries for correction and segmentation, such as **`fuzzywuzzy`** (for Jargon Correction) and **`readless`** (for TextTiling segmentation). |

### Phase 1: L1 Text Normalization and Dysfluency Removal

This stage converts the raw, unstructured ASR output into linguistically coherent and correctly cased text, minimizing structural noise.

| Step | Goal/Action Item | Rationale & Key Mechanisms |
| :--- | :--- | :--- |
| **1.1** | **Implement Punctuation Restoration and Truecasing** | Introduce a dedicated model (e.g., **`rpunct`** or a GECToR-based model) immediately following ASR to restore capitalization and sentence boundaries. This is critical for accurate downstream tasks like semantic segmentation and tokenization. |
| **1.2** | **Develop Dysfluency Removal Module** | Create a lightweight post-ASR cleanup module that uses custom scripting, dictionary lookups (for common fillers like 'uhh', 'hmm', 'like'), and regular expressions for simple repetitions. Using high-efficiency string-searching algorithms like **FlashText** is recommended due to its speed. |
| **1.3** | **Modify Transcription Flow** | Ensure the raw transcript saved by Scribe's **`Transcriber`** is the *cleaned* output of this L1 Enhancement stage, establishing the **Sequential Cascading** rule: clean text must enable the next phase. |

### Phase 2: L2 Transcript Structuring (Speaker Diarization)

This stage transforms the cleaned, linear text into attributed dialogue, which is non-negotiable for summarizing meetings.

| Step | Goal/Action Item | Rationale & Key Mechanisms |
| :--- | :--- | :--- |
| **2.1** | **Integrate Diarization Pipeline** | Integrate the Pyannote VAD, Embedding Extraction, and Clustering algorithms into the workflow (using a system like WhisperX logic). The output must be an RTTM-style file of speaker turn segments. |
| **2.2** | **Ensure Word-Level Timestamps** | Verify that the `faster-whisper` output is transcribed with **precise word-level timestamps**. This precision is mandatory for accurate speaker attribution. |
| **2.3** | **Implement Alignment and Gluing Logic** | Develop the alignment script to **"glue"** the transcribed words (and their timestamps) to the overlapping Pyannote speaker segments, thus assigning a **Speaker ID** (e.g., SPEAKER\_00, SPEAKER\_01) to every utterance. This output transforms the monologue into dialogue for the LLM. |

### Phase 3: L3 Correction and Semantic Segmentation

This phase enhances the fidelity of domain-specific language and prepares the text for efficient context management by the LLM.

| Step | Goal/Action Item | Rationale & Key Mechanisms |
| :--- | :--- | :--- |
| **3.1** | **Implement Jargon Correction Layer** | Implement fuzzy matching using **`fuzzywuzzy`** (based on **Levenshtein distance**) to correct common ASR misrecognitions of domain-specific jargon. The system should use Scribe's existing `jargon.txt` dictionary as the authoritative list. This step must occur *after* punctuation restoration (Phase 1) to ensure accurate tokenization. |
| **3.2** | **Implement Semantic Segmentation** | Replace Scribe's current fixed 1000-word block splitting with a **Semantic Segmentation** model. Use an algorithm like **TextTiling** (lexical cohesion based on vocabulary flow) via a library like **`readless`** to divide the transcript into logical blocks based on topic shifts. |
| **3.3** | **Inject Contextual Metadata** | Develop logic to prepend a structured **metadata header** to each segmented chunk. This header should contain context like the active speaker list, the previous topic summary, or the overall meeting context, allowing the LLM to resolve anaphora across chunk boundaries. |

### Phase 4: LLM Deployment and Optimization

This phase focuses on selecting the optimal small LLM and implementing the advanced long-context prompt engineering workflows.

| Step | Goal/Action Item | Rationale & Key Technologies |
| :--- | :--- | :--- |
| **4.1** | **Select and Quantize the LLM** | Choose the strategically optimal model based on long-context stability and instruction adherence. The sources recommend **LLaMA 3.1-8B-Instruct** for its superior long-context scaling capability or **Qwen 2.5 14B** for exceptional structured output and reasoning. Deploy this model using quantized formats (e.g., **GGUF**) via **`llama-cpp-python`** or an optimized Ollama configuration to maximize efficiency and fit within VRAM constraints. |
| **4.2** | **Implement Map-Reduce Workflow** | Integrate the two-step **Map-Reduce pattern** into Scribe's **`MeetingSynthesizer`**. The Map phase individually applies an extraction chain to **each semantic chunk** (from Phase 3), preserving speaker attribution. The Reduce phase combines these shorter, mapped summaries for the final synthesis. This workflow is highly scalable and parallelizable. |
| **4.3** | **Integrate Chain of Density (CoD)** | Implement the **Chain of Density (CoD) prompting technique** in the Reduce phase (or the direct summarization path for short documents). CoD forces the LLM to perform iterative refinement, integrating 1–3 new key **entities** while compressing existing content to maintain a fixed length. This maximizes the information density of the final summary output. |

### Phase 5: Asynchronous Orchestration and Advanced Features

This phase integrates architectural components that manage the pipeline flow and support advanced hardware/multimodal extensions discussed in the documents (like AMPS).

| Step | Goal/Action Item | Rationale & Key Mechanisms |
| :--- | :--- | :--- |
| **5.1** | **Transition to Asynchronous Orchestration** | Refactor Scribe's `SessionManager` logic to utilize a **Producer-Consumer pattern** facilitated by a persistent task queue (e.g., using **SQLite** or `asyncio.Queue` objects). This decouples the fast audio input/I/O tasks from the slower, GPU-intensive AI compute tasks. |
| **5.2** | **Implement Resource Locking Logic** | If the system utilizes constrained VRAM or multiple specialized models (like a separate VLM), implement a **Foreman** script with resource locking logic. This ensures that heavy models do not compete for GPU VRAM simultaneously, preventing crashes or severe performance degradation due to memory swapping. |
| **5.3** | **Integrate Multimodal Context Fusion (Optional)** | If future multimodal features (Visual Capture) are included, the diarized, cleaned transcript must be **chronologically interleaved** with extracted visual descriptions (e.g., OCR text and VLM captions) at the appropriate timestamps. This creates a rich, "grounded" context log for the final LLM synthesis. |

---
**Summary Metaphor:**

Upgrading Scribe is like transforming a competent single-stage food processor into a sophisticated, multi-station factory. Instead of dumping raw ingredients (ASR transcript) into one machine (the LLM) and hoping for a finished meal, we are installing specialized stations: a cleaning station (Normalization), an assembly line (Diarization/Structuring), a quality control check (Jargon Correction), and finally, a master chef (the LLM running Map-Reduce/CoD) that works with only the highest-quality, organized intermediate products to synthesize the final dish. This modular, sequential approach ensures the small, local "chef" can achieve professional-grade results.