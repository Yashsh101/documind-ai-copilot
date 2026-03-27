from langchain.chains import RetrievalQA
from langchain.llms import OpenAI
from app.main import vector_store  # make sure vector_store is loaded on startup

llm = OpenAI(temperature=0, openai_api_key="YOUR_OPENAI_KEY")  # or load from .env

qa = RetrievalQA.from_chain_type(
    llm=llm,
    chain_type="stuff",
    retriever=vector_store.as_retriever(search_kwargs={"k":5}),
    return_source_documents=True
)

def chat_with_docs(query: str):
    result = qa({"query": query})
    answer = result["result"]
    sources = [doc.metadata.get("source", "unknown") for doc in result["source_documents"]]
    return answer, sources