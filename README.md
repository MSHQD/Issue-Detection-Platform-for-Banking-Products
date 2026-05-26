
# Real-Time Customer Sentiment Tracking and Issue Detection Platform for Banking Products

A research project investigating **Aspect-Based Sentiment Analysis (ABSA)** approaches for Russian banking reviews. The goal is to evaluate which pipeline architecture is most suitable for near-real-time banking ABSA — comparing dictionary-based, zero-shot, generative, and encoder-based methods.

> Bachelor's Research Project — HSE Faculty of Computer Science, Data Science and Business Analytics, 2026

---

## Overview

Banks accumulate large volumes of unstructured customer feedback across review platforms. Manual analysis is slow, selective, and difficult to scale. At the same time, overall sentiment classification is not enough for business users: they need to know **which specific service** caused a problem and **what exactly** the customer said about it.

This project addresses that gap by formulating the task as **Aspect-Based Sentiment Analysis**: each prediction is a structured pair of an aspect-sentiment label and an evidence fragment extracted from the review text.

```
aspect_sentiment + evidence fragment
```

For example: `CARDS_NEG` + *"карту заблокировали без предупреждения"*

Since a single review may cover multiple topics (card issue, mobile app, support), the task is formulated as **multilabel classification with span extraction**.

The work focuses on the research and experimental part: collecting data, annotating a gold sample, and comparing several ABSA approaches to identify the most defensible architecture for future near-real-time monitoring.

---

## Repository Structure

```
├── banki_ru/                   # Scraper for Banki.ru (Playwright)
├── otzovik/                    # Scraper for Otzovik (Selenium)
├── sravni_ru/                  # Scraper for Sravni.ru (Selenium)
├── EDA_analysis.ipynb          # Exploratory data analysis and topic modelling
├── rubert_dictionary.ipynb     # Baseline: RuBERT embeddings + dictionary classification
├── sentiment_analysis.ipynb    # Sentiment analysis experiments
├── qwen_zero_shot.ipynb        # Zero-shot classification with Qwen3-1.7B
├── qwen_teacher.ipynb          # Teacher model fine-tuning (Qwen3-8B) + pseudo-label generation
├── qwen_student_pipeline.ipynb # Student model fine-tuning: Qwen3-1.7B
├── bert_student_pipeline.ipynb # Student model fine-tuning: ModernBERT (token classification)
└── labels_statistics.ipynb     # Label distribution analysis
```

---

## Data Collection

Reviews were scraped from three major Russian banking review platforms:

| Source | Tool | Reviews
|---|---|---|
| Banki.ru | Playwright | 5 894
| Otzovik | Selenium | 329
| Sravni.ru | Selenium | 175

2024–2026 

**Total corpus: 6 398 reviews** after merging and deduplication.

Each review was preprocessed with spaCy: HTML removal, lemmatisation, stop word filtering, and banking entity normalisation (e.g. various names for the same service → unified tag like `CARD`, `APP`, `SUPPORT`).

---

## Aspect Label Schema

The system classifies reviews into aspect-sentiment pairs. Aspect categories include:

`CARDS` · `DIGITAL` · `SUPPORT` · `PAYMENTS` · `CREDITS` · `OFFICE` · `FRAUD` · `INSURANCE` · `INVESTMENTS` · `ACCOUNT` · `PREMIUM` · `FEES`

Each paired with `_POS` or `_NEG` sentiment, e.g. `SUPPORT_NEG`, `DIGITAL_POS`.

---

## Approaches & Results

Four approaches were developed and compared:

### 1. RuBERT + Dictionary Baseline (`rubert_dictionary.ipynb`)
Sentence embeddings from `cointegrated/rubert-tiny2` combined with manually constructed banking service dictionaries and rule-based sentiment detection. Fast and interpretable, but limited by dictionary coverage.

### 2. Zero-Shot Qwen3-1.7B (`qwen_zero_shot.ipynb`)
Compact LLM prompted to output structured JSON with aspect labels and evidence spans — no training required. Showed the model understands the task structure but produced unstable outputs (5 101 out of 6 398 reviews had generation errors).

### 3. Teacher–Student Distillation: Qwen3-8B → Qwen3-1.7B (`qwen_teacher.ipynb`, `qwen_student_pipeline.ipynb`)
Qwen3-8B fine-tuned with QLoRA on 311 manually annotated reviews, then used to generate pseudo-labels for the remaining corpus. Qwen3-1.7B trained as a generative student on these pseudo-labels.

### 4. Teacher–Student Distillation: Qwen3-8B → ModernBERT (`bert_student_pipeline.ipynb`)
Same teacher, but student reformulated as a **token classification** model with BIO tagging using `deepvk/RuModernBERT-base`. Faster inference, no JSON generation required.

### Quantitative Comparison

| Approach | Precision | Recall | F1 | Soft Acc. | Exact Match |
|---|---|---|---|---|---|
| RuBERT + Dictionary | 0.501 | 0.425 | 0.460 | 0.440 | 0.032 |
| Zero-Shot Qwen3-1.7B | — | — | — | — | — |
| Qwen3-1.7B Student | 0.788 | **0.802** | **0.795** | **0.685** | **0.293** |
| ModernBERT Student | **0.890** | 0.639 | 0.744 | 0.671 | 0.230 |

**Key takeaway:** Qwen3-1.7B student achieves higher recall and F1 (better at recovering all aspects); ModernBERT achieves higher precision with structurally stable, faster predictions — better suited for production near-real-time monitoring.

---

## Annotation

Manual annotation was performed in **Label Studio** on 311 reviews. For each banking aspect mention, the corresponding text span was highlighted and assigned a label. The annotated subset served as gold labels for validation and testing across all experiments.

---

## Tech Stack

- **Scraping:** Playwright, Selenium WebDriver
- **NLP / Embeddings:** spaCy, `cointegrated/rubert-tiny2`, TF-IDF + NMF
- **Models:** Qwen3-1.7B, Qwen3-8B, `deepvk/RuModernBERT-base`
- **Training:** Hugging Face Transformers, TRL (SFTTrainer), QLoRA / LoRA, PEFT
- **Clustering:** UMAP + HDBSCAN / KMeans
- **Annotation:** Label Studio
- **Evaluation:** seqeval, multilabel Precision / Recall / F1, Soft Accuracy, Exact Match

---

## Setup

```bash
git clone https://github.com/MSHQD/Issue-Detection-Platform-for-Banking-Products.git
cd Issue-Detection-Platform-for-Banking-Products
pip install -r requirements.txt
```

> The notebooks were developed and tested in Google Colab. Teacher model fine-tuning (Qwen3-8B) requires a GPU with at least 24 GB VRAM. Student models (Qwen3-1.7B, ModernBERT) can run on Colab free tier with 4-bit quantisation.

---

## Future Work

- Expand manual annotations, especially for rare positive categories (`PAYMENTS_POS`, `CREDITS_POS`, `FRAUD_POS`)
- Multi-annotator setup with inter-annotator agreement measurement
- Confidence thresholding and active learning for continuous dataset improvement
- Inference speed benchmarks (latency, GPU memory, throughput)
- Interactive analytical dashboard for visualising sentiment dynamics by banking category

---

## Author

**Maria Degtyarenko**  
Bachelor's Programme "Data Science and Business Analytics"  
HSE Faculty of Computer Science, Group БПАД232  
Supervisor: Anna Matveeva, Senior Systems Analyst, Axenix
