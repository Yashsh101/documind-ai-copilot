# DocuMind AI — Architecture

## Stack

| Layer | Technology |
|---|---|
| Frontend | React + Vite, deployed on Vercel |
| Backend | FastAPI, deployed on Render (Docker) |
| Embeddings | sentence-transformers `all-MiniLM-L6-v2` |
| Vector store | FAISS (in-memory, ephemeral on free tier) |
| Retrieval | BM25 + dense hybrid + cross-encoder reranking |
| LLM | Configurable via `LLM_MODEL` env var (OpenRouter/OpenAI/Anthropic) |
| Streaming | SSE (`text/event-stream`) |

## RAG Pipeline

```
Upload PDF
  → chunk (size=512, overlap=64)
  → embed (MiniLM)
  → store in FAISS

Query
  → HyDE expansion
  → BM25 + dense hybrid retrieval (top_k=5)
  → cross-encoder rerank
  → LLM answer generation (streaming SSE)
```

## Deployment

```
Render (Backend)
  runtime: Docker
  healthcheck: GET /health
  env: CORS_ORIGINS=https://<your-app>.vercel.app

Vercel (Frontend)
  framework: Vite
  root: frontend/
  build: npm run build
  output: dist/
  env: VITE_API_BASE_URL=https://<your-backend>.onrender.com
```

## Security Notes

- CORS locked to Vercel domain in production via `CORS_ORIGINS` env var
- `/docs` and `/redoc` disabled in production (`ENVIRONMENT=production`)
- No secrets in repo — all via environment variables
- FAISS index and uploads are ephemeral on free tier (`/tmp`)
