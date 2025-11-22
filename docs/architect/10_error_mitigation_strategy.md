# Error Mitigation Strategy

**Priority:** HIGH - Quality Assurance

## Core Principle

**Pre-LLM correction is essential.** The architectural premise is the utilization of aggressive, lightweight pre-processing components that act as cascading filters to resolve structural and lexical errors using computationally cheap NLP models *before* the text enters the LLM context window. Relying on LLM self-correction is inefficient and unreliable.

## LLM Repair Limitations

LLMs cannot be fully relied upon to identify and resolve their own errors due to their generative nature.

**Research Findings (Text-to-SQL Repair Study):**

*   **Limited Fix Rate:** Existing repairing attempts achieved **limited correctness improvement**, fixing only **$10.9-23.3\%$ of errors**.
*   **High Mis-Repair Rate:** These attempts introduced **$5.3-40.1\%$ more errors**.
*   **Latency Overhead:** Repairing solutions introduced high computational overhead, specifically **$1.03-3.82 \times$ latency overhead**.
*   **Error Exacerbation:** An **improper repairing attempt would exacerbate the errors**, often transforming simple errors (like syntax, schema, or logic) into complex semantic errors that are harder to detect and repair.

**Conclusion:** The strategy of simply adding "fix this error" to LLM prompts is an **anti-pattern**. The pipeline must focus complexity reduction upstream to **dramatically reduce the token cost** consumed by the LLM for correction purposes.

## Error Taxonomy

The pipeline primarily mitigates linguistic and structural errors that feed into the semantic problems LLMs struggle with.

| Error Type | Frequency (in ICL-based tasks) | Mitigation Strategy |
| :--- | :--- | :--- |
| **Semantic Errors** | $\mathbf{30.9\%}$ to $\mathbf{36.1\%}$ of total errors (on harder tasks) | Context files, L5 Map-Reduce, L6 Chain of Density (CoD) |
| **Format-Related Errors** | $\mathbf{26.0\%}$ of all errors (Syntax, Schema, Logic, Convention) | L1 Normalization, L3 Jargon Correction |
| **Schema Errors** | Cause $\mathbf{81.2\%}$ of execution failures | L3 Jargon Correction (avoids spelling/hallucination) |
| **Syntactic Errors** | Cause $18.8\%$ of execution failures | L1 Normalization (punctuation restoration) |

**Key Insight:** **Semantic errors** are common, caused by LLM misinterpretation of natural language and misunderstanding of the database schema. Fixing upstream format and schema issues reduces the likelihood of these downstream semantic failures.

## Mitigation Strategies by Stage

### L1 Normalization
| Detail | Specification | Source Reference |
| :--- | :--- | :--- |
| **Prevents** | Loss of sentence boundaries, which are critical for accurate semantic segmentation. Also prevents linguistic noise (disfluencies, repetitions) from degrading summary quality. | |
| **Mechanism** | **Punctuation Restoration and Truecasing** using specialized models (e.g., BERT-based or GECToR). **Dysfluency Removal** via highly efficient string-searching algorithms like **FlashText** ($O(N)$ complexity). | |
| **Validation** | Verifies the establishment of clean, grammatically marked sentence boundaries, ensuring the correct input required by L4 Segmentation. | |

### L3 Jargon Correction
| Detail | Specification | Source Reference |
| :--- | :--- | :--- |
| **Prevents** | ASR phonetic errors in technical terminology (e.g., "moxiperil" to "moexipril"). Prevents LLM **hallucination** or misrepresentation of key entities. | |
| **Mechanism** | **Fuzzy matching** (e.g., `fuzzywuzzy`) based on **Levenshtein distance** against a canonical, user-defined jargon list. Requires a high confidence threshold ($\ge 85\%$) for replacement. | |
| **Validation** | Guarantees that all key entities are **$100\%$ faithful** to the authoritative list before the text proceeds to the Map-Reduce and Chain of Density (CoD) stages. | |

### L2 Diarization
| Detail | Specification | Source Reference |
| :--- | :--- | :--- |
| **Prevents** | Loss of dialogue context and speaker attribution. Prevents misattributing dialogue, which **poisons the context** for the summarization model. | |
| **Mechanism** | **Pyannote** (diarization) combined with **WhisperX** logic to align speaker segments with **word-level timestamps** derived from Phoneme-Based Forced Alignment. | |
| **Validation** | Validation must confirm that the **word-level speaker assignment** is accurate and the diarization error rate (DER) is low. | |

### L4 Metadata Injection
| Detail | Specification | Source Reference |
| :--- | :--- | :--- |
| **Prevents** | **Context drift** and failure to resolve anaphora (references to previous nouns) when the transcript is broken into logical chunks. | |
| **Mechanism** | Prepending a structured header (e.g., Active Speakers, Previous Topic Summary) to **EVERY chunk** sent to the LLM. This transforms the stateless segment into a "stateful" data object. | |
| **Validation** | LLM output must be checked for maintained narrative continuity and correct contextual referencing across segment boundaries. | |

### Context Files
| Detail | Specification | Source Reference |
| :--- | :--- | :--- |
| **Prevents** | Errors caused by the LLM's lack of private domain knowledge, misinterpretation of schema, or over-reliance on internal (hallucinated) knowledge. | |
| **Mechanism** | The system integrates external formalized representations (e.g., domain jargon lists from L3 Correction). Providing **supplementary information**, such as value specifications or execution information, is beneficial for LLM correction. | |
| **Validation** | The use of external knowledge (via RAG or injected context) aims to **ensure the factual consistency** of LLM-generated content. | |

## Validation Workflow

The pipeline operates as a sequence of cascading filters. Validation must confirm the success of each stage before passing data to the next.

```
Raw ASR Output
  ↓
L1 Normalization (Punctuation/Dysfluency)
  → Validation: Sentence boundary coherence (required for TextTiling)
  ↓
L2 Diarization (Structuring)
  → Validation: Speaker-word alignment accuracy (ensures context integrity)
  ↓
L3 Jargon Correction (Fidelity)
  → Validation: 100% entity fidelity check against canonical list (required for CoD)
  ↓
L4 Segmentation (Context Management)
  → Validation: Semantic boundary integrity (ensures logical Map inputs)
  ↓
LLM Execution (Map-Reduce/CoD)
  → Validation: Output JSON structure adherence + Factual consistency
```

## Error Handling

**Detection:** Errors are primarily detected by **rule-based solutions** and checking for execution failures at early stages. This allows the use of low-overhead solutions based on error symptoms.

**Recovery:** Recovery is achieved through the persistence layer. The system uses a **SQLite-backed task queue** that treats each 1–2 minute audio chunk as an independent job unit, creating natural **"checkpoints"**. This ensures that processing continues even after failures, guaranteeing that jobs will eventually complete. If a chunk fails processing in the Map phase, it can be re-queued without corrupting the entire meeting record.

## Quality Metrics

Factual accuracy and structural adherence are the paramount quality metrics.

*   **Entity Fidelity:** Ensured by L3 Correction and leveraged by L6 CoD.
*   **Structural Coherence:** Ensured by L1/L4 stages, validated by the LLM's ability to maintain narrative flow across chunks.
*   **Structured Output:** Measured by adherence to the **JSON schema** required by the Chain of Density prompt.

## When Errors Occur

**Anti-Pattern:** Adding "fix this error" to LLM prompts → compounds problems. The research strongly suggests that asking LLMs to validate and repair their own errors is ineffective, introduces new errors, and incurs high computational overhead. The complexity should be shifted to specialized pre-processing stages (L1-L4).

***

**Analogy:** The error mitigation strategy is like assembling a delicate machine. Instead of letting the final, expensive assembly robot (the LLM) try to fix a hundred small, upstream flaws with brute force (which might bend components or jam the works), the process uses several cheap, specialized quality control stations (Normalization, Diarization, Correction) to ensure every component is perfect before it reaches the assembler, maximizing the final product's quality and minimizing waste.