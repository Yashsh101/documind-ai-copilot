# DocuMind — AI Customer Support Copilot

![CI Status](https://github.com/asharma/documind/actions/workflows/ci.yml/badge.svg)
![GitHub license](https://img.shields.io/badge/license-MIT-blue.svg)

A production-grade Retrieval-Augmented Generation (RAG) system that answers customer queries from your own documents.

**Author:** Yash Sharma, MCA student, AI Engineer

---

## Tech Stack

| Component | Technology |
|---|---|
| **Language** | Python 3.11 |
| **API Framework** | FastAPI |
| **Vector Database** | FAISS |
| **AI / LLM** | OpenAI (GPT models) |
| **PDF Parsing** | PyMuPDF |
| **Testing** | Pytest |
| **Deployment** | Docker & GitHub Actions |

---

## Architecture

```
PDF upload  →  PyMuPDF  →  Chunking  →  Embeddings  →  FAISS
                                                           ↓
User query  →  Rewriter  →  Embed  →  Retrieve  →  LLM  →  Answer + Citations
```

---

## Features

- **RAG pipeline**: Robust pipeline to ingest, embed, and query custom knowledge
- **FAISS vector search**: High-speed, in-memory similarity search for document chunks
- **Query rewriting**: LLM-powered query optimization for better context retrieval
- **Source citations**: Provides verifiable source chunks and scores for every answer
- **Eval metrics**: Automatically scores context recall and answer faithfulness
- **Conversation memory**: Maintains chat history to support multi-turn dialogue
- **Docker**: fully containerized setup for reproducible deployments
- **CI/CD**: Automated testing and Docker builds via GitHub Actions

---

## Quickstart (local)

### 1. Clone and set up environment

```bash
git clone https://github.com/YOUR_USERNAME/documind-ai-copilot.git
cd documind-ai-copilot

python -m venv .venv
# Windows: .venv\Scripts\activate
# Mac/Linux: source .venv/bin/activate        
pip install -r requirements.txt
```

### 2. Configure secrets

```bash
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY
```

### 3. Run the server

```bash
uvicorn app.main:app --reload --port 8000
```

### 4. Open the API docs

Visit **http://localhost:8000/docs** — full interactive Swagger UI.

### 5. Test it

```bash
# Upload a PDF
curl -X POST http://localhost:8000/api/v1/upload-documents \
  -F "files=@your_document.pdf"

# Ask a question
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"question": "What is the refund policy?", "session_id": "user_123"}'

# Get chat history
curl http://localhost:8000/api/v1/chat-history/user_123

# Health check
curl http://localhost:8000/api/v1/health
```

---

## Run with Docker

```bash
# Build and start
docker compose up --build

# Stop
docker compose down
```

The FAISS index and uploads persist in `./vector_store` and `./uploads` via Docker volumes.

---

## Run tests

```bash
pytest tests/ -v
```

---

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/upload-documents` | Upload one or more PDFs |
| POST | `/api/v1/query` | Ask a question, get a cited answer |
| GET | `/api/v1/chat-history/{session_id}` | Retrieve conversation history |
| DELETE | `/api/v1/chat-history/{session_id}` | Clear session history |
| GET | `/api/v1/health` | Health + index status check |

### Sample query response

```json
{
  "answer": "The refund window is 30 days from purchase date.",
  "citations": [
    {
      "chunk_id": 4,
      "preview": "Customers may request a full refund within 30 days...",
      "relevance_score": 0.921
    }
  ],
  "rewritten_query": "What is the customer refund policy and time window?",
  "eval_metrics": {
    "context_recall": 1.0,
    "answer_faithfulness": 0.87,
    "avg_relevance_score": 0.921
  },
  "session_id": "user_123",
  "latency_ms": 843.2
}
```

---

## Project Structure

```
app/
├── main.py               # App factory, lifespan, middleware
├── config.py             # Pydantic settings from .env
├── api/
│   ├── routes.py         # FastAPI endpoints (thin layer)
│   └── schemas.py        # Request/response Pydantic models
├── services/
│   ├── ingestion.py      # PDF parsing + chunking
│   ├── embedding.py      # OpenAI embeddings with retry
│   ├── retrieval.py      # FAISS vector store
│   ├── llm.py            # LLM generation with grounded prompt
│   └── memory.py         # Session conversation history
├── rag/
│   ├── pipeline.py       # Orchestrates full query flow
│   └── query_rewriter.py # LLM-based query rewriting
└── utils/
    ├── logger.py          # Structured JSON logger + middleware
    ├── citations.py       # Citation extraction and cleaning
    ├── evaluator.py       # Inline RAG quality metrics
    └── exceptions.py      # Custom exceptions + global handlers
```

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_API_KEY` | — | **Required.** Your OpenAI API key |
| `EMBEDDING_MODEL` | `text-embedding-3-small` | Embedding model |
| `LLM_MODEL` | `gpt-4o-mini` | Generation model |
| `CHUNK_SIZE` | `512` | Token size per chunk |
| `CHUNK_OVERLAP` | `64` | Overlap between chunks |
| `TOP_K_RETRIEVAL` | `5` | Number of chunks to retrieve |
| `MIN_RELEVANCE_SCORE` | `0.30` | Minimum cosine similarity threshold |
| `MAX_HISTORY_TURNS` | `6` | Conversation turns to keep in memory |

---

## License

MIT
