# DocuMind v2 — AI Customer Support Copilot

![CI](https://github.com/Yashsh101/documind-ai-copilot/actions/workflows/ci.yml/badge.svg)
![Python](https://img.shields.io/badge/python-3.11+-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green)
![License](https://img.shields.io/badge/license-MIT-blue)

> "A production-grade RAG system with HyDE, hybrid retrieval, cross-encoder reranking, and confidence scoring — built to outperform Intercom Fin and Zendesk AI on accuracy and transparency."

Built by **Yash Sharma** | MCA Student | Aspiring AI/ML Engineer  
GitHub: https://github.com/Yashsh101  
LinkedIn: https://linkedin.com/in/yash-sharma-262923183

## What makes v2 different (vs competitors)
- **HyDE**: Embeds hypothetical answers instead of raw queries to dramatically boost recall on complex questions.
- **Hybrid Retrieval**: Fuses dense semantic search (text-embedding-3-small) with sparse keyword search (BM25) to catch precise product codes or version numbers.
- **Cross-encoder Reranking**: Uses an LLM to judge the top-20 retrieved chunks and precisely re-sort them to the top-5 before generation.
- **Confidence Scoring & Escalation**: Generates a composite confidence score based on retrieval/generation metrics. Automatically flags low-confidence answers to escalate to a human agent natively.
- **Context Compression**: Strips out irrelevant sentences from retrieved chunks, feeding only the highest-signal context into the LLM context window.

## Architecture

```text
User Query --> Query Rewriter --> HyDE Answer Generation
                                        |
  +-------------------------------------+-----------------------------------+
  |                                                                         |
Dense Search (FAISS/Embeddings)                               Sparse Search (BM25)
  |                                                                         |
  +---------------------------> Merged Results <----------------------------+
                                        |
                            Cross-Encoder Reranker
                                        |
                              Context Compressor
                                        |
                          GPT-4o-mini Generator
                                        |
                         Confidence Scorer + Evaluator
                                        |
                      Final Cited Answer + Quality Metrics
```

## Tech Stack
| Layer | Technology |
|-------|------------|
| API | FastAPI + Uvicorn |
| Ingestion | PyMuPDF + Langchain Recursive Splitter |
| Dense Vector Store | FAISS (IndexFlatIP) |
| Sparse Index | Rank-BM25 |
| Embeddings | OpenAI text-embedding-3-small |
| LLMs | OpenAI GPT-4o-mini |
| Testing | Pytest + Pytest-Asyncio |

## Features
- Fully local in-memory indices for Blazing Fast latency
- Chunk-level semantic citations
- Live streaming pipeline steps
- Animated Real-time evaluation indicators (Faithfulness, Recall)
- Escalation thresholds

## Quick Start

```bash
git clone https://github.com/Yashsh101/documind-ai-copilot
cd documind-ai-copilot
python -m venv .venv
# Activate: On Windows: .venv\Scripts\activate | Unix: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# [!] Add your OPENAI_API_KEY to .env
uvicorn app.main:app --port 8000
```

## API Reference
- `POST /api/v1/upload-documents` — Multipart file upload and full index rebuild.
- `POST /api/v1/query` — RAG pipeline execution.
- `GET /api/v1/chat-history/{sid}` — Retrieve conversational turns.
- `DELETE /api/v1/chat-history/{sid}` — Clear history.
- `GET /api/v1/health` — Ensure index and features status.

## Project Structure
```
app/
  config.py
  main.py
  api/ (routes.py, schemas.py)
  services/ (ingestion, bm25_index, embedding, llm, memory, reranker, retrieval)
  rag/ (pipeline, query_rewriter, hyde, context_compressor)
  utils/ (logger, exceptions, citations, evaluator, confidence)
tests/
index.html
```

## Environment Variables
- `OPENAI_API_KEY` (required)
- Model configs (`LLM_MODEL`, `EMBEDDING_MODEL`)
- Tuning parameters (`CHUNK_SIZE`, `TOP_K_RETRIEVAL`)

## Running Tests
Run the deterministic pipeline test suite:
```bash
pytest tests/ -v
```

## License
MIT
