## Sprint 0: Infrastructure and Core Dependency Setup

**Goal:** Establish the necessary environment and access credentials for specialized components before coding begins.

| Task | Prompt for LLM Agent | Rationale & Cited Requirements |
| :--- | :--- | :--- |
| **0.1 Pyannote Authentication** | **TASK:** Create a setup script or environment variable check that ensures the Hugging Face access token (for Pyannote models) is present and validated. Provide clear instructions on where the user must input the token to enable `pyannote.audio` model download and usage. | The state-of-the-art diarization model (`pyannote/speaker-diarization-3.1`) requires explicit user conditions acceptance and a **Hugging Face access token** for authentication, even for local inference. |
| **0.2 Core Dependency Installation** | **TASK:** Update `requirements.txt` to include essential libraries required by the new pipeline architecture. This must include `whisperx` (or `faster-whisper` and `pyannote.audio` separately), `fuzzywuzzy`, and `readless`. Ensure the installation guide mentions the requirement for **`ffmpeg`** to be installed system-wide. | **`whisperx`** (which includes `faster-whisper` and integrates Pyannote logic) is the recommended solution for transcription and alignment. `fuzzywuzzy` is needed for L3 Jargon Correction. `readless` supports TextTiling for semantic segmentation. |
| **0.3 LLM Runtime Configuration** | **TASK:** Prepare the `llama-cpp-python` environment within Scribe's Python stack, prioritizing CUDA support. Update `config.yaml` to specify the optimal target LLM model path (e.g., `LLaMA-3.1-8B-Instruct.gguf` or `Qwen-2.5-7B-Chat.gguf`) and configure GPU layer offloading (e.g., `--n-gpu-layers`). | Deployment must utilize **quantized formats (GGUF)** via `llama.cpp` to fit resource constraints and maximize inference speed on local GPUs. LLaMA 3.1-8B-Instruct is strategically chosen for superior long-context scaling. |

---

## Sprint 1: L1 Text Normalization and Dysfluency Removal

**Goal:** Convert raw ASR output (which is low-cased and runs-on) into linguistically clean text, minimizing noise before upstream processing. This replaces reliance on the LLM for character-level cleanup.

| Task | Prompt for LLM Agent | Rationale & Cited Requirements |
| :--- | :--- | :--- |
| **1.1 Punctuation Restoration Layer** | **TASK:** Implement a module for Punctuation Restoration and Truecasing (capitalization recovery). Integrate a specialized model (e.g., using a GECToR-based approach or rpunct). This must execute immediately after raw transcription within `src/scribe/core/transcriber.py`. The output must define clear sentence boundaries, which is essential for accurate downstream segmentation. | Punctuation restoration and truecasing significantly improve text readability and tokenization accuracy for downstream tasks. Specialized models are computationally cheap compared to forcing the final LLM to perform this task. |
| **1.2 Dysfluency Removal Module** | **TASK:** Create a high-efficiency module (`DysfluencyFilter`) designed to strip out common filler words (`um`, `uh`, `like`) and simple repetitions using a predefined dictionary/regex list. Integrate this module immediately following the punctuation step (1.1). Specify use of a resource-light algorithm like **FlashText** due to its linear time complexity, ensuring maximum speed. | Dysfluencies introduce noise and severely reduce the information density of the transcript, harming summarization quality. This filtering must happen *after* punctuation restoration for accurate word segmentation. |
| **1.3 Update Data Flow** | **TASK:** Modify the `Transcriber` component to ensure that the saved `transcript_full.txt` (the input to `MeetingSynthesizer`) is the **fully cleaned and punctuated output** of the L1 Enhancement stage, enforcing the Sequential Cascading requirement. | The clean text (L1 output) must serve as the input base for all subsequent structuring and correction steps (L2/L3). |

---

## Sprint 2: L2 Transcript Structuring (Speaker Diarization)

**Goal:** Transform the cleaned monologue into attributed dialogue by integrating state-of-the-art diarization, a non-negotiable step for summarizing meetings.

| Task | Prompt for LLM Agent | Rationale & Cited Requirements |
| :--- | :--- | :--- |
| **2.1 Implement Diarization Pipeline** | **TASK:** Refactor the transcription logic in `src/scribe/core/transcriber.py` to use an integrated solution (e.g., implementing WhisperX logic) that runs `faster-whisper` for transcription and `pyannote.audio` for diarization sequentially on the input audio. The Pyannote VAD, embedding extraction, and clustering should be leveraged. | Diarization, which assigns labels like `SPEAKER_00` and `SPEAKER_01`, is mandatory for contextual summarization tasks like action item extraction. The integrated approach avoids manual management of multiple complex components. |
| **2.2 Enforce Word-Level Timestamps** | **TASK:** Ensure that the `faster-whisper` engine is configured to output **precise word-level timestamps**. This granular timing data is critical for accurate speaker alignment. | Accurate speaker attribution requires aligning each word’s specific start/end time with the overlapping speaker segment provided by Pyannote. |
| **2.3 Implement Alignment/Gluing Logic** | **TASK:** Develop a script that performs the **"glue" operation**. This script must accept the L1-cleaned transcript (with word-level timestamps) and the Pyannote RTTM-style output (speaker segments). It must assign the correct `SPEAKER_ID` to each corresponding utterance based on temporal overlap. The final output of this stage is the fully attributed transcript. | The "transcribe-then-align" strategy ensures that the flow of the transcript is preserved while enriching it with speaker metadata, creating attributed dialogue for the LLM. |
| **2.4 GPU Acceleration Check** | **TASK:** Introduce logic in the initialization sequence to explicitly check for and configure the use of CUDA/GPU for the `pyannote.audio` component, as speed is often severely degraded on CPU-only setups (1 hour of audio takes 2-4 hours to process). | Deploying a GPU is strongly recommended to achieve acceptable processing times for the intensive neural inference required by diarization. |

---

## Sprint 3: L3 Correction and Semantic Segmentation

**Goal:** Enhance fidelity of domain-specific language and strategically divide the long transcript into logical, context-coherent blocks.

| Task | Prompt for LLM Agent | Rationale & Cited Requirements |
| :--- | :--- | :--- |
| **3.1 Jargon Correction Layer** | **TASK:** Implement the domain correction module using the `fuzzywuzzy` library within a new class, `JargonCorrector`. This module must load the canonical terms from `Documents/Scribe/config/jargon.txt`. For every token in the attributed transcript (L2 output), calculate the **Levenshtein Distance** (similarity ratio) against the jargon list and replace the token with the canonical term if the confidence threshold (e.g., > 85/100) is met. | Fuzzy matching efficiently corrects technical terms misrecognized by ASR (e.g., correcting "moxiperil" to "moexipril"). This ensures key entities are 100% faithful before the LLM sees them, supporting the final Chain of Density stage. |
| **3.2 Semantic Segmentation Module** | **TASK:** Replace the antiquated fixed-size `split_into_blocks_with_timestamps` method in `MeetingSynthesizer` with a new, dedicated `SemanticSegmenter` module. This module must utilize a topic-based segmentation strategy like **TextTiling** (`readless` library is recommended) or a semantic embedding approach (Sentence-BERT, calculating cosine similarity divergence) to divide the text only at logical topic shifts. | Arbitrary chunking destroys context. Semantic segmentation produces coherent chunks, which is the prerequisite for the efficient and high-quality operation of the subsequent Map-Reduce pipeline. |
| **3.3 Metadata Header Injection** | **TASK:** Augment the `SemanticSegmenter` to prepend a **structured metadata header** to *every* segmented chunk before it is passed to the LLM. This header must include the active speaker list and, if possible, a brief summary of the immediately preceding topic, explicitly mitigating context loss across chunk boundaries. | Injecting metadata helps the small LLM resolve anaphora (pronouns/references) and maintain narrative continuity during the Map step. |

---

## Sprint 4: LLM Context Management (Map-Reduce Workflow)

**Goal:** Refactor the `MeetingSynthesizer` into a robust, multi-step orchestration engine capable of synthesizing long documents that exceed the small LLM's context window limits.

| Task | Prompt for LLM Agent | Rationale & Cited Requirements |
| :--- | :--- | :--- |
| **4.1 Implement Map Phase Logic** | **TASK:** Create the `MapProcessor` function within `MeetingSynthesizer`. This function iterates through the list of semantic chunks (from 3.2), applies a specific **Map Prompt** to each chunk, and aggregates the results into a single list of intermediate summaries. **Map Prompt instruction:** "Analyze the following segment (Chunk [X] of [Y]). Extract all technical decisions, assigned action items, and factual statements. Preserve the speaker attribution (e.g., SPEAKER\_01: Decided Y). Do not summarize or synthesize. Output only a list of atomic facts.". | The Map phase handles the long document by reducing each chunk to high-density facts while crucially maintaining the speaker attribution context supplied by L2 Structuring. |
| **4.2 Implement Reduce Phase Logic** | **TASK:** Create the `ReduceSynthesizer` function. This function takes the consolidated list of intermediate summaries (Map output) as its input. **Reduce Prompt instruction:** "You are an expert meeting secretary. Synthesize the following collection of atomic facts and mini-summaries into a single, cohesive, high-level meeting minutes document. Group related facts by topic and clearly structure the final output.". | The Reduce step focuses the entire context of the meeting into one manageable payload for the final, resource-intensive synthesis by the primary LLM. Map-Reduce is highly robust and parallelizable. |
| **4.3 Configure LLM Endpoint** | **TASK:** Update `MeetingSynthesizer` to ensure it targets the chosen, optimized, quantized LLM (e.g., LLaMA 3.1-8B) via the `llama-cpp-python` binding, replacing the current generic Ollama API calls where direct model control is required. | This step solidifies the shift from generic chat models to models optimized for long-context tasks, such as LLaMA 3.1-8B-Instruct, which are superior in long-context scaling stability. |

---

## Sprint 5: LLM Output Refinement (Chain of Density)

**Goal:** Maximize the information density and quality of the final summary output by implementing iterative prompting techniques.

| Task | Prompt for LLM Agent | Rationale & Cited Requirements |
| :--- | :--- | :--- |
| **5.1 Implement Chain of Density (CoD) Loop** | **TASK:** Integrate the **Chain of Density (CoD) iterative refinement loop** into the `ReduceSynthesizer` (4.2). The function must execute **3 fixed iterations** on the final, consolidated summary output. In each iteration, the LLM must be forced to identify 1-3 novel, high-value entities from the original Map input and rewrite the entire summary to include them while strictly maintaining the original length/token count. | CoD is an advanced prompting technique specifically designed to maximize informativeness and compress verbose language, overcoming the inherent limitations of smaller LLMs. |
| **5.2 CoD Prompt Template Integration** | **TASK:** Implement the structured CoD prompt template within the `ReduceSynthesizer` function, ensuring it enforces the strict rules for entity identification and fusion: **Step 1:** Identify 1-3 informative Entities (";" delimited) from the full meeting context (provided as reference) which are missing from the previously generated summary. **Step 2:** Write a new, denser summary of identical length which covers every entity and detail from the previous summary plus the Missing Entities. **Constraints:** Entities must be **Novel**, **Specific** (5 words or fewer), and **Faithful** (present in the source text). | Adherence to the specific iterative prompt structure is critical for CoD to function correctly and generate dense, concise, and self-contained summaries. |