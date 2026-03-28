from app.utils.helpers import clean_answer, extract_citations, evaluate, score_confidence
from app.core.ingestion import chunk_text
from app.core.pipeline import compress_chunks

CHUNKS = [
    {"chunk_id":0,"text":"The refund policy allows 30 days from purchase.","score":0.91},
    {"chunk_id":1,"text":"Contact support at help@example.com for assistance.","score":0.85},
    {"chunk_id":2,"text":"Premium members receive priority 24/7 support.","score":0.72},
]

def test_chunk_produces_multiple():
    assert len(chunk_text("Sentence. "*80, source="t.pdf")) >= 2

def test_chunk_ids_start_from_offset():
    chunks = chunk_text("Word "*200, source="t.pdf", start_id=10)
    assert chunks[0].chunk_id == 10

def test_chunk_skips_short():
    chunks = chunk_text("Hi\n\n" + "Real content here. "*30)
    assert all(len(c.text)>=30 for c in chunks)

def test_citations_found():
    cits = extract_citations("Answer [chunk_0] and [chunk_1].", CHUNKS)
    assert {c.chunk_id for c in cits} == {0,1}

def test_citations_unreferenced_excluded():
    cits = extract_citations("Answer [chunk_0].", CHUNKS)
    assert all(c.chunk_id!=2 for c in cits)

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

def test_confidence_high():
    r = score_confidence(0.9, 1.0, 0.9, 3, 5)
    assert r.label == "high"
    assert not r.should_escalate

def test_confidence_low_escalates():
    r = score_confidence(0.1, 0.1, 0.1, 0, 0)
    assert r.should_escalate
