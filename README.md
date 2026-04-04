# DocuMind v3 — AI Customer Support Copilot

> Production-ready AI SaaS system with hybrid RAG, streaming responses, and premium UI.

![Python](https://img.shields.io/badge/Python-3.11+-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green)
![OpenAI](https://img.shields.io/badge/LLM-OpenAI-blue)
![License](https://img.shields.io/badge/License-MIT-yellow)

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        FRONTEND (SPA)                          │
│  ┌──────────┐  ┌──────────────┐  ┌───────────┐  ┌───────────┐ │
│  │ Sidebar  │  │   Chat Area  │  │  Input    │  │ Streaming │ │
│  │ • Upload │  │ • Messages   │  │ • Toggle  │  │ • SSE     │ │
│  │ • Files  │  │ • Citations  │  │ • Actions │  │ • Tokens  │ │
│  │ • Export │  │ • Actions    │  │ • Hotkeys │  │ • Cursor  │ │
│  └──────────┘  └──────────────┘  └───────────┘  └───────────┘ │
└────────────────────────┬────────────────────────────────────────┘
                         │ HTTP / SSE
┌────────────────────────▼────────────────────────────────────────┐
│                    FASTAPI BACKEND                              │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  Routes: /health  /upload  /query  /chat/stream         │   │
│  └───────────┬─────────────────┬───────────────────────────┘   │
│              │                 │                                │
│  ┌───────────▼─────┐  ┌───────▼───────────────────────────┐   │
│  │  Document Mgmt  │  │        RAG Pipeline               │   │
│  │  • Upload PDF   │  │  Query → Rewrite → Hybrid Search  │   │
│  │  • Ingest       │  │  → BM25+Vector → Rerank → LLM    │   │
│  │  • Chunk        │  │  → Actions → Memory → Response    │   │
│  │  • Embed        │  │                                   │   │
│  └─────────────────┘  └───────────────────────────────────┘   │
│                                │                                │
│  ┌──────────────┐  ┌──────────▼──────┐  ┌─────────────────┐   │
│  │  TTL Cache   │  │  Memory System  │  │  Prompt Engine  │   │
│  │  • Embedding │  │  • Short-term   │  │  • System       │   │
│  │  • Query     │  │  • Long-term    │  │  • RAG Template │   │
│  │  • LLM       │  │  • Disk persist │  │  • Rewrite      │   │
│  └──────────────┘  └─────────────────┘  │  • Actions      │   │
│                                          └─────────────────┘   │
└────────────────────────┬────────────────────────────────────────┘
                         │
              ┌──────────▼──────────┐
              │   OpenAI (LLM)      │
              │  • gpt-4o-mini      │
              │  • Embeddings       │
              │  • Streaming        │
              └─────────────────────┘
```

---

## Features

| Feature | Description |
|---------|-------------|
| **Hybrid Search** | BM25 (sparse) + Vector Cosine (dense) with weighted fusion |
| **LLM Reranking** | Cross-encoder style relevance scoring via LLM |
| **SSE Streaming** | Real-time token streaming with cursor animation |
| **Memory System** | Short-term window + long-term disk persistence |
| **Smart Actions** | Contextual follow-up suggestions per response |
| **Query Rewriting** | History-aware query reformulation for better retrieval |
| **TTL Caching** | Embedding, query, and LLM response caching with hit stats |
| **PDF Export** | One-click conversation export to formatted PDF |
| **Health Dashboard** | OpenAI status, cache stats, indexed documents |

---

## Quick Start

### Prerequisites
- Python 3.11+
- OpenAI API key (set `OPENAI_API_KEY` in `.env`)

### Install & Run

```bash
# Clone
git clone https://github.com/yourusername/documind-ai-copilot.git
cd documind-ai-copilot

# Virtual environment
python -m venv .venv
.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -r requirements.txt

# Run DocuMind
uvicorn app.main:app --reload --port 8000
```

Open **http://localhost:8000** in your browser.

---

## Project Structure

```
documind-ai-copilot/
├── app/
│   ├── main.py                 # FastAPI entry point
│   ├── config.py               # Settings & structured logging
│   ├── routes/
│   │   ├── health.py           # Health check + diagnostics
│   │   ├── documents.py        # Upload, list, delete docs
│   │   └── chat.py             # Query + SSE streaming
│   ├── services/
│   │   ├── llm.py              # OpenAI LLM (generate + stream)
│   │   ├── memory.py           # Dual memory system
│   │   └── suggestions.py      # Action suggestion engine
│   ├── rag/
│   │   ├── chunking.py         # Semantic paragraph chunking
│   │   ├── embeddings.py       # Embedding service + cache
│   │   ├── ingestion.py        # PDF → chunks → embeddings → store
│   │   ├── retriever.py        # Hybrid BM25 + vector search
│   │   ├── reranker.py         # LLM-based relevance reranking
│   │   └── pipeline.py         # Full RAG orchestrator
│   ├── models/
│   │   └── schemas.py          # Pydantic request/response models
│   ├── core/
│   │   ├── prompts.py          # All prompt templates
│   │   └── cache.py            # TTL cache implementation
│   └── static/
│       ├── index.html          # SPA shell
│       ├── styles.css          # Premium dark-mode design system
│       └── app.js              # Frontend application
├── data/                        # Indexed document storage
├── .env                         # Environment configuration
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── render.yaml                  # Render.com deployment blueprint
```

---

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/health` | Health check + OpenAI status + cache stats |
| `POST` | `/api/v1/upload` | Upload and index PDF files |
| `GET` | `/api/v1/documents` | List indexed documents |
| `DELETE` | `/api/v1/documents/{id}` | Remove a document |
| `POST` | `/api/v1/query` | Standard query (JSON response) |
| `POST` | `/api/v1/chat/stream` | Streaming query (SSE) |

---

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_API_KEY` | (required) | OpenAI API key |
| `OPENAI_CHAT_MODEL` | `gpt-4o-mini` | Primary LLM model |
| `LLM_TEMPERATURE` | `0.15` | Generation temperature |
| `CHUNK_SIZE` | `512` | Max characters per chunk |
| `CHUNK_OVERLAP` | `64` | Overlap between chunks |
| `TOP_K_RETRIEVAL` | `5` | Number of chunks to retrieve |
| `BM25_WEIGHT` | `0.35` | BM25 score weight in fusion |
| `VECTOR_WEIGHT` | `0.65` | Vector score weight in fusion |
| `RERANK_ENABLED` | `true` | Enable LLM-based reranking |
| `MEMORY_WINDOW_SIZE` | `10` | Conversation turns in memory |

---

## Deployment

### Docker
```bash
OPENAI_API_KEY=sk-... docker-compose up -d
```

### Render.com
1. Push to GitHub
2. Connect repo to Render
3. `render.yaml` handles the rest
4. Set `OPENAI_API_KEY` environment variable in Render dashboard

### Vercel (Frontend Only)
Deploy `app/static/` as a static site pointing to your backend URL.

---

## License

MIT
