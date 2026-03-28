from app.utils.citations import clean_answer, extract_citations
from app.utils.evaluator import evaluate
from app.services.ingestion import chunk_text, extract_text

CHUNKS = [
    {"chunk_id":0,"text":"The refund policy allows 30 days.","score":0.91},
    {"chunk_id":1,"text":"Contact support at help@example.com.","score":0.85},
    {"chunk_id":2,"text":"Premium members get priority support.","score":0.72},
]

def test_chunk_produces_multiple():
    assert len(chunk_text("Sentence. " * 80, source="t.pdf")) >= 2

def test_chunk_ids_start_from_offset():
    chunks = chunk_text("Word " * 200, source="t.pdf", start_id=10)
    assert chunks[0].chunk_id == 10

def test_chunk_skips_short():
    chunks = chunk_text("Hi\n\n" + ("Real content sentence here. " * 30))
    assert all(len(c.text) >= 30 for c in chunks)

def test_citations_found():
    cits = extract_citations("Answer [chunk_0] and [chunk_1].", CHUNKS)
    assert {c.chunk_id for c in cits} == {0, 1}

def test_citations_unreferenced_excluded():
    cits = extract_citations("Answer [chunk_0].", CHUNKS)
    assert all(c.chunk_id != 2 for c in cits)

def test_clean_answer_removes_tags():
    assert "[chunk_" not in clean_answer("Answer [chunk_0] here.")

def test_eval_full_recall():
    assert evaluate("[chunk_0][chunk_1][chunk_2]", CHUNKS).context_recall == 1.0

def test_eval_partial_recall():
    assert evaluate("[chunk_0]", CHUNKS).context_recall < 1.0

def test_eval_faithfulness_nonzero():
    assert evaluate("refund policy support contact", CHUNKS).answer_faithfulness > 0

def test_eval_empty():
    r = evaluate("answer", [])
    assert r.context_recall == 0.0

def test_chunk_source_set():
    chunks = chunk_text("Content " * 100, source="doc.pdf")
    assert all(c.source == "doc.pdf" for c in chunks)

def test_chunk_text_no_empties():
    chunks = chunk_text("  \n\n  " + "Real sentence content here. " * 20)
    assert all(c.text.strip() for c in chunks)
