# DocuMind \ AI Customer Support Copilot (Python FastAPI + SPA)

DocuMind v2 is a production-grade AI customer support copilot designed to ingest policy and FAQ documents (PDFs) and provide precise, citation-backed answers to user questions using a pure Python RAG pipeline and a modern SaaS-style interface. The architecture is cleanly decoupled, making it instantly adaptable for real-world enterprise deployments.

## Tech Stack

- **Backend**: Python 3, FastAPI, Uvicorn, PyMuPDF (fitz), and standard scalable ML/Python libraries.
- **Frontend**: Clean HTML, CSS, JavaScript SPA featuring a responsive dark SaaS UI.
- **AI Engine**: Local extractive RAG pipeline configured natively with pure Python embedding and retrieval stubs. Fully architected to accept LLM endpoints out of the box.

## Core Features

- **Document Ingestion**: Rapidly upload PDFs (e.g., refund policies) which are automatically parsed, chunked, and converted into structured knowledge base artifacts.
- **Natural Language Querying**: Ask contextual questions and retrieve precise answers mapped dynamically to direct citations within source documents.
- **Premium User Experience**: Notion/ChatGPT-style chat UI with smooth typing transitions, dynamic document status indicators, and resilient structured error handling wrapped via an exponential back-off API controller.
- **Zero-Dependency Core**: The default baseline uses an entirely local, pure Python NLP scoring stub, eliminating the need for expensive API keys or external dependencies under standard testing.

## Setup & Initialization

1. Create a native virtual environment:
   ```bash
   python -m venv .venv
   ```
2. Activate the virtual environment:
   - **Windows**: `.\.venv\Scripts\activate`
   - **Linux / macOS**: `source .venv/bin/activate`
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Running the Application

1. Boot the Uvicorn server:
   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```
2. Open your preferred browser and navigate to the mounted SPA:
   - `http://127.0.0.1:8000`

## Usage Example

- **Upload Stage**: Place or generate the `Company_Refund_Policy.pdf` inside the project directory. Drag and drop it into the "Knowledge Base" UI box, and click **Upload & Index**.
- **Query Stage**: In the chat box, type: *"What is the refund policy?"*
- **Response Handling**: DocuMind immediately parses the vector store and extracts the context, generating a JSON response identical to the following structure behind the scenes:

```json
{
  "answer": "Based on the knowledge base documents, here is the relevant information: \n\n\"Company Refund Policy\nWe accept full refunds within 30 days of purchase. Just ask the support team via email....\"\n\n*(This is an extractive answer computed strictly in Python. Plug in an LLM call here to synthesize text natively!)*",
  "citations": [
    {
      "document_id": "18700992_company_refund_policy.pdf",
      "page": 1,
      "snippet": "Company Refund Policy\nWe accept full refunds within 30 days of purchase. Just ask the support team via email...."
    }
  ],
  "status": "success",
  "message": null
}
```

## Extensibility & LLM Integrations

This system is built from the ground up by an AI/ML Engineer anticipating heavy-duty synthesis models:
- **Embeddings**: In `app/core/embedding.py`, replace the `get_query_embedding()` logic and its hashed cache stubs with raw calls to `openai.embeddings.create(...)` or Vertex AI.
- **Synthesis Generation**: Inside `app/core/pipeline.py` (`run_query`), the extractive Python answer generation step can directly be swapped for `client.chat.completions` (OpenAI/Anthropic) calls utilizing the properly structured local chunks as strict System Prompts.
