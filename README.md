# DocuMind — AI Customer Support Copilot

![CI](https://github.com/Yashsh101/documind-ai-copilot/actions/workflows/ci.yml/badge.svg)
![Python](https://img.shields.io/badge/python-3.11+-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green)
![License](https://img.shields.io/badge/license-MIT-blue)

> A production-grade RAG system that reads your documents and answers 
> customer queries with source citations, zero hallucinations, and 
> real-time quality metrics.

Built by **Yash Sharma** — MCA Student | Aspiring AI/ML Engineer
[GitHub](https://github.com/Yashsh101) · [LinkedIn](https://linkedin.com/in/yash-sharma-262923183)

## What it does
- Upload any PDF knowledge base
- Ask questions in natural language  
- Get grounded answers with source citations
- Every answer includes faithfulness + recall metrics

## Architecture
PDF → PyMuPDF → Chunking → OpenAI Embeddings → FAISS
Query → LLM Rewrite → Embed → Retrieve → GPT-4o-mini → Cited Answer

## Tech Stack
| Layer | Technology |
|-------|-----------|
| API | FastAPI + Uvicorn |
| PDF Parsing | PyMuPDF |
| Chunking | LangChain RecursiveCharacterTextSplitter |
| Embeddings | OpenAI text-embedding-3-small |
| Vector Store | FAISS (IndexFlatIP, cosine similarity) |
| LLM | GPT-4o-mini |
| Deployment | Docker + GitHub Actions CI/CD |

## Features
- RAG pipeline with semantic chunking (512 tokens, 64 overlap)
- LLM-powered query rewriting for better retrieval
- Source citations with relevance scores
- Conversation memory (sliding window)
- Inline quality metrics (faithfulness, context recall, avg relevance)
- Structured JSON logging with latency tracking
- Hallucination guardrails via grounded system prompt
- 12 automated tests, all passing

## Quick Start

```bash
git clone https://github.com/Yashsh101/documind-ai-copilot
cd documind-ai-copilot
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# Add your OPENAI_API_KEY to .env
uvicorn app.main:app --port 8000
```

Open http://localhost:8000 for the UI
Open http://localhost:8000/docs for the API

## Run Tests
`pytest tests/ -v`

## Docker
`docker compose up --build`

## Project Structure
```text
app/
  main.py          — FastAPI app + static file serving
  config.py        — Pydantic settings
  api/             — Routes + schemas
  services/        — PDF ingestion, embeddings, FAISS, LLM, memory
  rag/             — Pipeline orchestration + query rewriter
  utils/           — Logger, exceptions, citations, evaluator
tests/             — 12 passing unit tests
index.html         — Production UI (single file, zero dependencies)
```

## License
MIT
