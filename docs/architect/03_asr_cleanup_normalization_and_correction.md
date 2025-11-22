# ASR Cleanup (L1 + L3)

**Priority:** HIGH - Foundation Layer

## L1 Normalization: Punctuation

**Objective:** Restore sentence boundaries and capitalization in the raw ASR output.

| Detail | Specification | Source Reference |
| :--- | :--- | :--- |
| **Model** | **BERT-based** or **GECToR-based** specialized models. Solutions like the **rpunct package** (utilizing the Bert Restore Punctuation model) are highly effective open-source options specifically designed for ASR output restoration. | |
| **Target** | The **Bert Restore Punctuation model** exhibits a **remarkable 91% overall accuracy** on held-out text samples. This method is necessary because ASR output is often unpunctuated and all-lowercase. | |
| **Integration** | Must be executed **immediately after** the raw transcription output within the `Transcriber` component. This enforces the **Sequential Cascading** rule. | |
| **Output** | Restores proper punctuation (periods (.), commas (,), question marks (?), exclamation marks (!)), as well as **truecasing** (upper-casing of words). | |
| **Critical** | The restored punctuation defines **sentence boundaries**. This structure is **essential for accurate downstream tasks** such as named entity recognition and **L4 Semantic Segmentation**. | |
| **Punctuation Note** | Though highly accurate overall, specialized marks like the comma may exhibit lower F1-scores, sometimes around 0.55 on ASR test sets. | |

## L1 Normalization: Dysfluencies

**Objective:** Remove acoustic noise (fillers, repetitions, stutters, false starts). The presence of dysfluencies is highly detrimental to summarization as they reduce the information density of the transcript.

| Detail | Specification | Source Reference |
| :--- | :--- | :--- |
| **Algorithm** | **FlashText** is the superior solution for high-performance keyword removal. It utilizes the **Aho-Corasick algorithm**. | |
| **Complexity** | **$O(N)$ complexity** (linear with document length $N$). This performance is **independent of the size of the keyword dictionary**. | |
| **Targets** | Common filler words in spontaneous speech include **`um`** and **`uh`**. Other targets include repetitions and known filler phrases. Disfluencies occur at a rate of approximately **4–6% in regular speech**. | |
| **Sequence** | This cleanup module **must be executed AFTER punctuation restoration** (L1 Normalization) to ensure accurate word segmentation. | |

```python
from flashtext import KeywordProcessor
processor = KeywordProcessor()
processor.add_keywords_from_dict({'': ['um', 'uh', 'like']})
cleaned = processor.replace_keywords(text)
```

## L3 Jargon Correction

**Objective:** 100% entity fidelity for domain terms. This non-LLM correction phase safeguards the accuracy of critical terminology prior to abstraction.

| Detail | Specification | Source Reference |
| :--- | :--- | :--- |
| **Tool** | The Python library **`fuzzywuzzy`** (or `TheFuzz`/`RapidFuzz`). | |
| **Metric** | The foundational metric used is the **Levenshtein distance** (or edit distance). This calculates the minimum number of single-character edits required to transform one string into another, effectively correcting phonetic ASR errors (e.g., "moxiperil" to "moexipril"). | |
| **Threshold** | The similarity score must **exceed a specified, high confidence threshold**, typically **$\ge$ 85%**. A threshold of **90%** is often recommended for reliable replacement. | |
| **Dictionary** | The correction runs against an **authoritative list of canonical domain-specific terms** provided by the user (e.g., `Documents/Scribe/config/jargon.txt`). | |
| **Why** | This preprocessing **reduces the cognitive burden** on the small LLM and prevents it from trying to infer plausible meaning from nonsense phonetic transcriptions. It **guarantees key entity fidelity**, which directly **enables accurate CoD entity extraction** in the final stage (L6). | |
| **Dependency** | This stage is **architecturally dependent** on the preceding Punctuation Restoration (L1) to ensure robust word boundaries, as flawed tokenization would nullify the fuzzy matching effectiveness. | |

```python
from fuzzywuzzy import process
for token in tokens:
    match, score = process.extractOne(token, jargon_list)
    if score >= 90:
        token = match
```

## Data Flow

This flow maintains the required **Sequential Cascading** for cleanup:

```
Raw ASR → Punctuation (L1) → Dysfluency (L1) → Jargon (L3) → transcript_full.txt (Input for L2 Structuring)
```

## Performance Targets

The architectural reliance on specialized, lightweight models ensures rapid processing:

| Stage | Target Latency (per 1000 words) | Rationale |
| :--- | :--- | :--- |
| Punctuation | <100ms/1000 words | BERT-based models add punctuation and truecasing efficiently. |
| Dysfluency | <50ms/1000 words | **FlashText** has $O(N)$ complexity, ensuring minimal latency even with large dictionaries. |
| Jargon | <200ms/1000 words | Fuzzy matching is fast (polynomial time complexity). |