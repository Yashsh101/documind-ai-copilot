# Deployment

DocuMind is a FastAPI application with a bundled static UI and local document index. Deploy it as a long-running web service, not as a serverless function.

## Recommended Hosts

- Render Web Service
- Railway Web Service
- Google Cloud Run with a persistent external storage layer

## Render

The repository includes `render.yaml`.

1. Create a new Render Blueprint from this repository.
2. Set production environment variables:
   - `OPENAI_API_KEY`
   - `OPENAI_CHAT_MODEL`
   - `OPENAI_EMBEDDING_MODEL`
   - `DATA_DIR`
   - retrieval and reranking settings from `.env.example`
3. Use the existing start command:

```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

4. Add a persistent disk if you want uploaded documents to survive redeploys.

## Railway

1. Create a Railway service from the GitHub repo.
2. Set the start command:

```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

3. Add variables from `.env.example`.
4. Add persistent storage or move indexes to external storage before production use.

## Docker

```bash
docker build -t documind-ai-copilot .
docker run -p 8000:8000 --env-file .env documind-ai-copilot
```

## Production Checklist

- Use a real `OPENAI_API_KEY`.
- Set explicit CORS origins before exposing a public upload endpoint.
- Add authentication before accepting arbitrary uploads.
- Use persistent storage for indexed document data.
- Keep sample PDFs in examples or demo data, not as production content.
- Monitor request latency and failed retrievals.
