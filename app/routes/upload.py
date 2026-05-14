import os
from typing import List
from fastapi import APIRouter, UploadFile, File
from fastapi.responses import JSONResponse
from app.config import get_settings, logger
from app.services.rag import ingest_pdf, get_indexed_document_count

router = APIRouter(prefix="/api/v1", tags=["documents"])
s = get_settings()

MAX_UPLOAD_SIZE = 50 * 1024 * 1024


@router.post("/upload")
@router.post("/upload-documents")
async def upload_documents(files: List[UploadFile] = File(...)):
    doc_ids = []
    total_chunks = 0
    errors = []

    for f in files:
        if not f.filename.lower().endswith(".pdf"):
            errors.append(f"Skipped {f.filename}: not a PDF")
            continue

        try:
            content = await f.read()
            if len(content) > MAX_UPLOAD_SIZE:
                errors.append(f"{f.filename}: exceeds 50MB limit")
                continue
            doc_id, chunk_count = ingest_pdf(content, f.filename)
            doc_ids.append(doc_id)
            total_chunks += chunk_count
            logger.info(f"Ingested {f.filename} -> {doc_id} ({chunk_count} chunks)")
        except ValueError as e:
            errors.append(f"{f.filename}: {str(e)}")
            logger.error(f"Ingestion failed for {f.filename}: {e}")
        except Exception as e:
            errors.append(f"{f.filename}: Processing error")
            logger.error(f"Unexpected error processing {f.filename}: {e}")

    if not doc_ids and errors:
        return JSONResponse(status_code=422, content={
            "status": "error",
            "message": "; ".join(errors),
            "document_ids": [],
            "chunk_count": 0,
        })

    return {
        "status": "success",
        "document_ids": doc_ids,
        "chunk_count": total_chunks,
        "message": f"Indexed {len(doc_ids)} document(s), {total_chunks} chunks created.",
        "warnings": errors if errors else None,
    }


@router.get("/documents")
async def list_documents():
    docs = []
    if os.path.exists(s.data_dir):
        for fname in os.listdir(s.data_dir):
            if fname.endswith(".json") and not os.path.isdir(os.path.join(s.data_dir, fname)):
                doc_id = fname.replace(".json", "")
                filepath = os.path.join(s.data_dir, fname)
                size_kb = round(os.path.getsize(filepath) / 1024, 1)
                docs.append({
                    "document_id": doc_id,
                    "size_kb": size_kb,
                })
    return {"status": "ok", "documents": docs, "count": len(docs)}


@router.delete("/documents/{doc_id}")
async def delete_document(doc_id: str):
    filepath = os.path.join(s.data_dir, f"{doc_id}.json")
    if os.path.exists(filepath):
        os.remove(filepath)
        logger.info(f"Deleted document {doc_id}")
        return {"status": "ok", "message": f"Document {doc_id} removed."}
    return JSONResponse(status_code=404, content={
        "status": "error", "message": "Document not found."
    })
