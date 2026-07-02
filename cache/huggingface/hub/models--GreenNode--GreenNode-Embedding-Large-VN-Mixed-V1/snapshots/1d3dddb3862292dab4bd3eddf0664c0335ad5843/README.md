---
datasets:
- GreenNode/GreenNode-Table-Markdown-Retrieval
language:
- vi
- en
library_name: sentence-transformers
pipeline_tag: sentence-similarity
tags:
- sentence-transformers
- sentence-similarity
- feature-extraction
widget: []
metrics:
- InfoNCE
license: mit
---

# SentenceTransformer

This is a [sentence-transformers](https://www.SBERT.net) model trained. It maps sentences & paragraphs to a 1024-dimensional dense vector space and can be used for semantic textual similarity, semantic search, paraphrase mining, text classification, clustering, and more.

## Model Details

### Model Description
- **Model Type:** Sentence Transformer
- **Maximum Sequence Length:** 8192 tokens
- **Output Dimensionality:** 1024 tokens
- **Similarity Function:** Cosine Similarity
- **Training Dataset:** - [GreenNode/GreenNode-Table-Markdown-Retrieval](https://huggingface.co/datasets/GreenNode/GreenNode-Table-Markdown-Retrieval-VN)
- **Language:** Vietnamese

### Model Sources

- **Documentation:** [Sentence Transformers Documentation](https://sbert.net)
- **Repository:** [Sentence Transformers on GitHub](https://github.com/UKPLab/sentence-transformers)
- **Hugging Face:** [Sentence Transformers on Hugging Face](https://huggingface.co/models?library=sentence-transformers)

### Full Model Architecture

```
SentenceTransformer(
  (0): Transformer({'max_seq_length': 8192, 'do_lower_case': False}) with Transformer model: XLMRobertaModel 
  (1): Pooling({'word_embedding_dimension': 1024, 'pooling_mode_cls_token': True, 'pooling_mode_mean_tokens': False, 'pooling_mode_max_tokens': False, 'pooling_mode_mean_sqrt_len_tokens': False, 'pooling_mode_weightedmean_tokens': False, 'pooling_mode_lasttoken': False, 'include_prompt': True})
  (2): Normalize()
)
```

## Usage

### Direct Usage (Sentence Transformers)

First install the Sentence Transformers library:

```bash
pip install -U sentence-transformers
```

Then you can load this model and run inference.
```python
from sentence_transformers import SentenceTransformer

# Download from the 🤗 Hub
model = SentenceTransformer("GreenNode/GreenNode-Embedding-Large-VN-Mixed-V1")
# Run inference
sentences = [
    'The weather is lovely today.',
    "It's so sunny outside!",
    'He drove to the stadium.',
]
embeddings = model.encode(sentences)
print(embeddings.shape)
# [3, 1024]

# Get the similarity scores for the embeddings
similarities = model.similarity(embeddings, embeddings)
print(similarities.shape)
# [3, 3]
```

## Evaluation
### Table: Performance comparison of various models on GreenNodeTableRetrieval
Dataset:  [GreenNode/GreenNode-Table-Markdown-Retrieval](https://huggingface.co/datasets/GreenNode/GreenNode-Table-Markdown-Retrieval-VN)

| Model Name                                  | MAP@5 ↑ | MRR@5 ↑ | NDCG@5 ↑ | Recall@5 ↑ | Mean ↑ |
|--------------------------------------------|--------:|--------:|---------:|-----------:|-------:|
| **Multilingual Embedding models**          |         |         |          |            |        |
| me5_small                                   | 33.75   | 33.75   | 35.68    | 41.49      | 36.17  |
| me5_large                                   | 38.16   | 38.16   | 40.27    | 46.62      | 40.80  |
| M3-Embedding                                | 36.52   | 36.52   | 38.60    | 44.84      | 39.12  |
| OpenAI-embedding-v3                         | 30.61   | 30.61   | 32.57    | 38.46      | 33.06  |
| **Vietnamese Embedding models (Prior Work)**|         |         |          |            |        |
| halong-embedding                            | 32.15   | 32.15   | 34.13    | 40.09      | 34.63  |
| sup-SimCSE-VietNamese-phobert_base          | 10.90   | 10.90   | 12.03    | 15.41      | 12.31  |
| vietnamese-bi-encoder                       | 13.61   | 13.61   | 14.63    | 17.68      | 14.89  |
| **GreenNode-Embedding (Our Work)**          |         |         |          |            |        |
| *M3-GN-VN*                                   | _41.85_ | _41.85_ | _44.15_  | _57.05_    | _46.23_ |
| **M3-GN-VN-Mixed**                           | **42.08** | **42.08** | **44.33** | **51.06** | **44.89** |
### Table: Performance comparison of various models on ZacLegalTextRetrieval
Dataset:  [GreenNode/zalo-ai-legal-text-retrieval-vn](https://huggingface.co/datasets/GreenNode/zalo-ai-legal-text-retrieval-vn)

| Model Name                                  | MAP@5 ↑ | MRR@5 ↑ | NDCG@5 ↑ | Recall@5 ↑ | Mean ↑ |
|--------------------------------------------|--------:|--------:|---------:|-----------:|-------:|
| **Multilingual Embedding models**          |         |         |          |            |        |
| me5_small                                   | 54.68   | 54.37   | 58.32    | 69.16      | 59.13  |
| me5_large                                   | 60.14   | 59.62   | 64.17    | 76.02      | 64.99  |
| *M3-Embedding*                              | _69.34_ | _68.96_ | _73.70_  | _86.68_    | _74.67_ |
| OpenAI-embedding-v3                         | 38.68   | 38.80   | 41.53    | 49.94      | 41.74  |
| **Vietnamese Embedding models (Prior Work)**|         |         |          |            |        |
| halong-embedding                            | 52.57   | 52.28   | 56.64    | 68.72      | 57.55  |
| sup-SimCSE-VietNamese-phobert_base          | 25.15   | 25.07   | 27.81    | 35.79      | 28.46  |
| vietnamese-bi-encoder                       | 54.88   | 54.47   | 59.10    | 79.51      | 61.99  |
| **GreenNode-Embedding (Our Work)**          |         |         |          |            |        |
| M3-GN-VN                                     | 65.03   | 64.80   | 69.19    | 81.66      | 70.17  |
| **M3-GN-VN-Mixed**                           | **69.75** | **69.28** | **74.01** | **86.74** | **74.95** |
### Table: Performance comparison of various models on VieQuADRetrieval
Dataset: [taidng/UIT-ViQuAD2.0](https://huggingface.co/datasets/taidng/UIT-ViQuAD2.0)

| Model Name                                  | MAP@5 ↑ | MRR@5 ↑ | NDCG@5 ↑ | Recall@5 ↑ | Mean ↑ |
|--------------------------------------------|--------:|--------:|---------:|-----------:|-------:|
| **Multilingual Embedding models**          |         |         |          |            |        |
| me5_small                                   | 40.42   | 69.21   | 50.05    | 50.71      | 52.60  |
| me5_large                                   | 44.18   | 67.81   | 53.04    | 55.86      | 55.22  |
| *M3-Embedding*                              | _44.08_ | _72.28_ | _54.07_  | _56.01_    | _56.61_ |
| OpenAI-embedding-v3                         | 32.39   | 53.97   | 40.48    | 43.02      | 42.47  |
| **Vietnamese Embedding models (Prior Work)**|         |         |          |            |        |
| halong-embedding                            | 39.42   | 62.31   | 48.63    | 52.73      | 50.77  |
| sup-SimCSE-VietNamese-phobert_base          | 20.45   | 35.99   | 26.73    | 29.59      | 28.19  |
| vietnamese-bi-encoder                       | 31.89   | 54.62   | 40.26    | 42.53      | 42.33  |
| **GreenNode-Embedding (Our Work)**          |         |         |          |            |        |
| M3-GN-VN                                     | 42.85   | 71.98   | 52.90    | 54.25      | 55.50  |
| **M3-GN-VN-Mixed**                           | **44.20** | **72.64** | **54.30** | **56.30** | **56.86** |

### Table: Performance comparison of various models on GreenNodeTableRetrieval (Hit Rate)

| Model Name                                     | Hit Rate@1 ↑ | Hit Rate@5 ↑ | Hit Rate@10 ↑ | Hit Rate@20 ↑ |
|------------------------------------------------|--------------|--------------|---------------|---------------|
| **Multilingual Embedding models**              |              |              |               |               |
| me5_small                                      | 38.99        | 53.37        | 59.28         | 65.09         |
| me5_large                                      | 43.99        | 59.74        | 65.74         | 71.59         |
| bge-m3                                         | 42.15        | 57.00        | 63.05         | 68.96         |
| OpenAI-embedding-v3                            | -            | -            | -             | -             |
| **Vietnamese Embedding models (Prior Work)**   |              |              |               |               |
| halong-embedding                               | 37.22        | 52.49        | 58.57         | 64.64         |
| sup-SimCSE-VietNamese-phobert_base             | 14.00        | 24.74        | 30.32         | 36.44         |
| vietnamese-bi-encoder                          | 16.89        | 25.94        | 30.50         | 35.70         |
| **GreenNode-Embedding (Our Work)**             |              |              |               |               |
| **M3-GN-VN**                                    | **48.31**    | **64.60**    | **70.83**     | **76.46**     |
| *M3-GN-VN-Mixed*                               | _47.94_      | _64.24_      | _70.43_       | _76.14_       |


### Framework Versions
- Python: 3.10.14
- Sentence Transformers: 3.0.1
- Transformers: 4.42.4
- PyTorch: 2.3.1
- Accelerate: 0.33.0
- Datasets: 2.20.0
- Tokenizers: 0.19.1

## Follow us
https://x.com/greennode23

## Support
https://discord.gg/B6MJFM3J3a 

## License

This repository and the model weights are licensed under the [MIT License](LICENSE).

## Citation

## Contact Us

- General & Collaboration: tung.vu@greennode.ai, thuvt@greennode.ai
- Technical: viethq5@greennode.ai
