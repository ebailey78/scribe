# Speaker Diarization (L2 Structuring)

**Category:** Core Processing Mechanisms  
**Stage:** L2 Structuring

## Overview

Speaker Diarization, which constitutes **Stage 3: Structuring** of the pipeline, is a crucial step that transforms the cleaned, linear text into **attributed dialogue**. This structural attribution is non-negotiable for summarizing conversations, meetings, or interviews, as it provides the **speaker context** required by the Large Language Model (LLM) to accurately generate a concise summary and extract items like action items ("Speaker A said X; Speaker B replied Y"). Speaker diarization aims to answer the question, **“who spoke when?”**.

The architectural strategy mandates combining high-performance transcription (Whisper) with state-of-the-art neural diarization (Pyannote) using the integrated **WhisperX logic**.

## Whisper Integration

While the original OpenAI Whisper model offers robust transcription, the optimized pipeline mandates the use of **highly optimized variants** to achieve the necessary speed and low memory footprint.

*   **Faster-Whisper Backend:** The primary choice is **`faster-whisper`**, a re-implementation of Whisper built on **CTranslate2** (an optimized C++ inference engine). This provides significant benefits, including **up to 4x faster inference** and **lower memory usage** compared to the original implementation.
*   **Efficiency:** Using `faster-whisper` ensures the ASR component is as efficient as possible on the target hardware. It also supports quantization, which cuts down memory use and speeds up inference.
*   **Output:** The ASR component must generate raw, unpunctuated text with **precise word-level timestamps**.

## Pyannote Integration

**Pyannote.audio** is the current **state-of-the-art open-source solution** for speaker diarization. It is based on the PyTorch machine learning framework and offers state-of-the-art pretrained models and pipelines.

*   **Architectural Components:** Pyannote employs a sophisticated, deep-learning pipeline involving specialized steps:
    1.  **Voice Activity Detection (VAD):** Detects the presence or absence of speech to distinguish speech from silence/noise.
    2.  **Speaker Embedding Extraction:** Generates dense vector representations (embeddings) of voice characteristics.
    3.  **Clustering:** Algorithms group these embeddings to assign distinct speaker IDs (e.g., SPEAKER\_00, SPEAKER\_01).
*   **High Accuracy:** Pyannote 3.1 achieves competitive accuracy, even handling **overlapping speech** reasonably well.
*   **Prerequisites:** To use the state-of-the-art models (such as `pyannote/speaker-diarization-3.1`), the user **must accept specific user conditions** on the Hugging Face platform and provide a **Hugging Face Access Token** during pipeline instantiation.
*   **Platform Constraint:** The toolkit's documentation notes that `pyannote.audio` only officially supports Linux and macOS, with no guarantee or plan for official Windows support, which necessitates using robust wrapper-based solutions or specialized environments like WSL2 for stable operation.

## WhisperX Logic

**WhisperX** is the integrated pipeline solution chosen for the Scribe architecture. It **extends Whisper** into a more complete transcription pipeline that handles word-level timestamps and speaker labels.

*   **Integrated Workflow:** WhisperX combines the transcription capabilities of **OpenAI Whisper** (or its optimized variants like `faster-whisper`) with the diarization capabilities of **Pyannote.audio**.
*   **Components:** WhisperX utilizes the Whisper model for transcription, Pyannote 3.1 for speaker diarization, and specialized models (like wav2vec2) for **word-level alignment** to improve accuracy for speaker assignment.
*   **Function:** WhisperX performs **speaker-word mapping**, assigning speaker labels to individual words and producing a complete transcript showing what was said and who said it.

## Word-Level Timestamps

Word-level timestamp precision is a **structural requirement** for successful speaker mapping.

*   **Inadequacy of Coarse Timestamps:** Standard Whisper models output timestamps at the segment level, which can be inaccurate by several seconds. This coarse granularity is insufficient for precise speaker mapping, especially during rapid dialogue, and can lead to words being attributed to the wrong speaker, which **poisons the context for the summarization model**.
*   **Forced Alignment:** WhisperX resolves this issue by introducing a secondary stage of **Phoneme-Based Forced Alignment**. The alignment step uses a separate acoustic model (like wav2vec2) to align the generated transcript with the audio waveform, producing highly accurate start and end timestamps for **every individual word**.
*   **Enabling Segmentation:** This precision is critical because it allows the pipeline to project speaker labels onto the text with high fidelity, ensuring that even rapid turn-taking is correctly attributed.

## Alignment Strategy

The alignment phase is where the transcribed text (from ASR) is **"glued"** to the speaker boundaries (from Pyannote), transforming the sequential transcription into structured dialogue.

*   **"Transcribe-Then-Align" Pattern:** The recommended methodology is the "transcribe-then-align" pattern, which maximizes context and semantic coherence by transcribing the entire audio first, then running diarization separately.
*   **Projecting Speaker Labels:** The final step involves fusing the high-accuracy transcript text with the speaker segmentation boundaries.
*   **Intersection Logic:** The core mechanism involves iterating through every word and assigning the speaker ID whose segment **overlaps most significantly** (the greatest temporal overlap) with the word's start and end timestamp interval $[t_{start}, t_{end}]$.

## Implementation Details

*   **Speed Constraint:** The sequential execution of transcription and diarization components is often **slower than real-time** on CPU-only setups; one hour of audio can take **2-4 hours to process**.
*   **GPU Mandate:** **Deployment of a suitable GPU is strongly recommended** to achieve practical speed (roughly 0.1-0.3x the audio length, or 6-18 minutes for one hour of audio).
*   **Configuration for GPU:** To avoid the severe performance bottleneck caused by CPU-bound diarization, the deployment environment requires careful configuration, including the specific CUDA toolkit and forcing the use of the **`onnxruntime-gpu`** package. Alternatively, using a **Windows Subsystem for Linux (WSL2)** environment with native CUDA pass-through offers the necessary Linux kernel compatibility for stable PyTorch and Pyannote operation.
*   **Resource Requirements:** WhisperX requires higher resource usage than standalone transcription because it runs two heavy models sequentially. Recommended system resources include **8GB+ RAM** and **4-8GB GPU VRAM** for optimal performance.
*   **Model Loading:** The Pyannote pipeline must be explicitly configured to run on the GPU by moving the pipeline to the CUDA device using `pipeline.to(torch.device("cuda"))`.
