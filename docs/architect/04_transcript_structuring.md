# Transcript Structuring (L2 + L4)

**Priority:** HIGH - Enables Dialogue & Map-Reduce

## L2 Speaker Diarization

**Objective:** Attribute utterances to specific speakers (SPEAKER\_00, SPEAKER\_01). This structural attribution is **non-negotiable** for summarizing meetings or interviews, as the LLM requires speaker context ("Speaker A said X; Speaker B replied Y") to generate accurate summaries and extract items like action items.

### Stack:

*   **ASR: `faster-whisper` (optimized Whisper):** The foundation uses `faster-whisper`, a CTranslate2-based reimplementation, which is **up to 4 times faster** than the original Whisper implementation and uses less memory.
*   **Diarization: `pyannote.audio` (requires HF token):** **Pyannote.audio** is the current state-of-the-art open-source solution for speaker diarization. Its models (like `pyannote/speaker-diarization-3.1`) require the user to **accept specific user conditions** and provide a **Hugging Face Access Token** for local inference.
*   **Integration: WhisperX logic:** **WhisperX** is the recommended integrated pipeline, as it combines the robust transcription of `faster-whisper` with the diarization capabilities of Pyannote. WhisperX provides an **all-in-one solution** for transcription and diarization.

### Critical: Word-level Timestamp Precision

*   **Default Whisper segments: INSUFFICIENT:** The standard Whisper model outputs coarse timestamps at the segment level, which are insufficient for precise speaker mapping, especially during rapid dialogue. This low granularity can result in words being **attributed to the wrong speaker**, poisoning the context.
*   **Implement: Phoneme-Based Forced Alignment (wav2vec2):** WhisperX resolves this by introducing a secondary stage of **Phoneme-Based Forced Alignment**. This uses a separate acoustic model (like wav2vec2) to align the generated transcript with the audio waveform, producing **highly accurate start and end timestamps for every individual word**. This is crucial for **word-level speaker attribution**.

### Workflow:

The integration follows the **"transcribe-then-align" pattern**:

1.  **`faster-whisper` transcription → word timestamps:** Transcribe the entire audio to maximize context and semantic coherence.
2.  **Pyannote diarization → speaker segments:** Pyannote performs VAD, speaker embedding extraction, and clustering to produce segments labeled by speaker ID (e.g., SPEAKER\_00).
3.  **Align: word [t\_start, t\_end] → SPEAKER\_ID (max overlap):** Alignment logic (handled by WhisperX) **"glues"** the transcribed words to the speaker segments. For every word $W$, the algorithm assigns the speaker $S$ whose segment **overlaps most significantly** (the greatest temporal overlap) with the word's timestamp interval $[t_{start}, t_{end}]$.

### GPU Requirement:

*   **CPU: 2-4 hours per audio hour (UNACCEPTABLE):** Processing diarization on a CPU only is **very slow** (e.g., Pyannote 3.1 takes approximately 2-3 hours for one hour of audio; WhisperX takes 3-4 hours). This results in a severe performance bottleneck.
*   **GPU: 6-18 minutes per audio hour (TARGET):** GPU utilization is **strongly recommended** for practical processing speeds, achieving a real-time factor of around **0.1 to 0.3x the audio length** (6-18 minutes for a one-hour file).
*   **Configure: `pipeline.to(torch.device("cuda"))`:** The PyTorch-based Pyannote pipeline must be explicitly configured to run on the GPU by using this command to utilize CUDA acceleration.
*   **Platform: WSL2 recommended for Windows (Pyannote stability):** Since **Pyannote.audio** is only guaranteed to run reliably on Linux and macOS, a **Windows Subsystem for Linux (WSL2)** environment with native CUDA pass-through is the required environment for stable operation on Windows.

## L4 Semantic Segmentation

**Objective:** Topic-based chunking. This process replaces the current Scribe fixed 1000-word block splitting with a method that respects **semantic boundaries**, ensuring logical blocks for the Map-Reduce workflow.

### Algorithm: TextTiling

*   **Mechanism:** TextTiling is a **moving window-based approach** that detects subtopic boundaries by analyzing patterns of **lexical cohesion** (word recurrence and vocabulary changes).
*   **Logic:** It assumes a coherent topic uses a consistent vocabulary and places a boundary where a "valley" in lexical similarity is detected.
*   **Library: `readless`:** The **`readless`** Python module provides a practical implementation of the TextTiling algorithm.
*   **Type: Unsupervised:** TextTiling is an **unsupervised** technique that relies only on the textual content itself, avoiding the need for a large and relevant training corpus (which is a limitation of TopicTiling/LDA for proprietary niche transcripts).
*   **Why:** Arbitrary fixed-size cuts **destroy context**, increase fragmentation, and inevitably **increase the hallucination rate** of the LLM.

### Dependency:

*   **Requires L1 punctuation (sentence boundaries):** The success of semantic segmentation is **critically dependent** on the preceding **Normalization stage** (L1) because **Punctuation Restoration** must establish grammatically marked **sentence boundaries**, which segmentation algorithms rely upon to accurately detect topic shifts.

## Metadata Injection

**Purpose:** To mitigate the inevitable loss of global context that occurs when a long transcript is broken into chunks, thereby helping the LLM resolve anaphora (pronouns/references) and maintain narrative continuity.

*   **Mandate:** The pipeline **must inject a structured metadata header** into every chunk sent to the LLM.

```markdown
---
CHUNK: [X/Y] | SPEAKERS: [S_00, S_01]
PREV_TOPIC: [summary] | CONTEXT: [from context.md]
---
```
*   **Mechanism:** The header transforms the stateless text segment into a "stateful" data object, providing context such as the **Active Speakers in this section** and a **Previous Topic Summary**.

## Data Flow

This flow illustrates how clean text is structured into the final input for the LLM context management stages:

```
Cleaned Text (L1 Output) → Diarization (L2) → Attributed Dialogue (with timestamps)
Attributed Dialogue → TextTiling (L4) → Topic Chunks
Topic Chunks → Metadata Injection → Map-Reduce Input (L5)
```

## Performance

*   **Diarization Error Rate:** While accuracy is model-dependent, Pyannote 2.1 is benchmarked with a Diarization Error Rate (DER) ranging from **8.17% to 32.37%** across various datasets. **Lower is better** (e.g., 10% DER = 90% accuracy).
*   **Processing:** **<20min per hour (GPU)**. GPU utilization is necessary to achieve practical processing speeds, targeting **6-18 minutes** for one hour of audio. Without a GPU, processing is unacceptably slow (2-4 hours per audio hour).