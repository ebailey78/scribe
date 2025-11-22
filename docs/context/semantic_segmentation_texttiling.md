# Semantic Segmentation (TextTiling)

**Category:** Core Processing Mechanisms
**Stage:** L3 Segmentation

## Overview

This document details the necessity of replacing fixed-size chunking with **Semantic Segmentation** (Stage 4 in the Optimized Pipeline, or L3 Segmentation in the naming of this document), ensuring that the long transcript is divided into logical, context-coherent blocks. This semantic approach is critical for guaranteeing input quality for the downstream Map-Reduce workflow. The recommended approach for this stage is the **TextTiling** algorithm.

Text Segmentation is a task in Natural Language Processing that aims to divide a text document into semantically or topically coherent sections. This is useful for creating topic-specific summaries, organizing long documents, reducing noise, and improving information retrieval. The goal is to identify breakpoints between pairs of sentences where the topic deviates significantly.

## Why Semantic Segmentation?

Semantic Segmentation is an **architectural necessity** for the Scribe pipeline to achieve high-quality abstractive summarization.

1.  **Contextual Coherence:** Semantic segmentation ensures that the chunks provided to the LLM (during the Map step) are **coherent and meaningful**, rather than arbitrary divisions. The output blocks are based on **topic shifts**.
2.  **LLM Performance:** By using semantically coherent blocks, the segmentation minimizes the cognitive load on the small LLM, enabling it to focus purely on summarization rather than trying to infer context from fragmented data.
3.  **Foundation for Map-Reduce:** Semantic segmentation is the **critical component that enables the efficient use of the Map-Reduce summarization workflow**. The structural coherence of the final summary is directly dependent on the quality of the input chunks.
4.  **Application to Spoken Text:** This approach is applicable to spoken text directly, although human conversations have cues like pauses or changes in tone or pitch that cannot be leveraged directly as this technique only uses lexical information to identify boundaries.

## Limitations of Arbitrary Chunking

The current Scribe application's method of splitting long transcripts by fixed length (e.g., fixed 1000-word blocks or fixed token count) is fundamentally flawed for meeting transcripts.

*   **Context Destruction:** Splitting text arbitrarily by token count **inevitably destroys context** by cutting across thematic shifts.
*   **Fragmentation:** Fixed-size cuts are agnostic to semantic boundaries, meaning they might sever a sentence in half, interrupt a logical argument, or separate a speaker label from their statement.
*   **Hallucination Risk:** This fragmentation forces the LLM to operate on incomplete data, significantly increasing the **hallucination rate**.
*   **RAG Flaw:** Simple chunking is destructive in RAG pipelines; a sentence might end up in a different chunk than the statement it refers to, losing context.

## TextTiling Algorithm

**TextTiling** is a foundational technique for discourse processing that segments expository texts into "passages" or subtopic segments. It is one of the first unsupervised topic segmentation algorithms.

*   **Mechanism:** TextTiling is a **moving window-based approach** that detects subtopic boundaries by analyzing patterns of **lexical co-occurrence and distribution** (lexical cohesion).
*   **Execution:** The technique runs a **sliding window** over sentences in the input text and calculates similarity scores between adjacent windows. The goal is to detect where the use of one set of terms ends and another set begins.
*   **Output:** The algorithm assumes that a subtopic discussion uses a consistent set of vocabulary, and when the topic shifts, a significant proportion of the vocabulary changes. It assumes that a coherent topic will use a consistent set of vocabulary, and detects a "valley" in the lexical similarity graph to place a boundary.
*   **Unsupervised Nature:** TextTiling is an **unsupervised learning task** that is robust to various document types and domains. It relies only on the textual content itself, eschewing other kinds of discourse cues.
*   **Implementation:** The Python module **`readless`** provides a mature, accessible implementation of the TextTiling algorithm, including options for both Block Score and Vocabulary Introduction methods, making it a highly practical choice for the local pipeline.

## Topic-Based Splitting

Semantic segmentation is achieved by identifying where the topic significantly deviates.

Alternative approaches exist for calculating similarity scores used to identify boundaries:

1.  **Topic-Based Segmentation (TopicTiling):** This method extends the original TextTiling by using **Topic IDs computed by Latent Dirichlet Allocation (LDA)** instead of bag-of-word features. Boundaries are placed where topic probabilities change significantly. However, a practical limitation is that LDA requires a substantial and relevant training corpus to generate high-quality topics, which is often difficult or impossible for proprietary, niche ASR transcripts.
2.  **LLM-Based Segmentation:** Variations use pre-trained **Large Language Models (LLMs) like BERT** or **Sentence-BERT embeddings** to compute semantic similarity between text blocks. This approach analyzes the text to evaluate a function called **local incoherence**, where maximum values indicate the likely presence of a semantic boundary. This method relies on calculating the **cosine similarity** or divergence between sentence embeddings. These deep learning segmentation models are highly sensitive to the quality of the source text derived from ASR processes, validating the necessity of preceding punctuation and truecasing stages (L1 Normalization).

Given the practical limitation of corpus availability for proprietary data, the simpler, corpus-agnostic **TextTiling** approach is often the default choice for reliability and ease of deployment in local, closed-domain pipelines.

## Integration with Map-Reduce

Semantic segmentation is not an end in itself; it is the **critical prerequisite** for the **Map-Reduce** summarization pattern (Stage 6).

*   **Input Alignment:** The semantically segmented blocks from this stage (L3 Segmentation) are used as the chunks for the Map-Reduce workflow.
*   **Structural Coherence:** By using **TextTiling**, the pipeline ensures that each chunk represents a single, cohesive subtopic. This design guarantees that the **Map operation** produces **distinct, non-redundant intermediate summaries**, drastically increasing the quality of the final **Reduce synthesis**.
*   **Efficiency:** The Map-Reduce pattern is inherently **parallelizable**, and this segmentation enables that parallelism by creating independent, yet contextually rich, segments. The chunks are constructed to fit within the context window limits of the specific LLM being used for the Map phase (e.g., 800 tokens to fit the NPU's 1024-token static constraint).

## Implementation Requirements

1.  **Pre-requisite:** The success of semantic segmentation is **critically dependent** on the output quality of the preceding stages. Specifically, the **Normalization stage (L1)** must restore punctuation and truecasing to establish grammatically marked sentence boundaries, which the segmentation algorithm relies upon to detect topic shifts.
2.  **Tooling:** Implementation should utilize the **`readless`** Python module to execute the TextTiling algorithm.
3.  **Metadata Injection:** To mitigate the inevitable context loss that occurs when segmenting a long, continuous discussion, the segmentation module must be augmented to **inject a structured metadata header** into every chunk. This header should contain essential context such as the **Active Speaker List** or a summary of the **Previous Topic** to help the LLM resolve anaphora across chunk boundaries during the Map step.
