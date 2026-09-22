import os
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FAISS_INDEX_PATH = str(PROJECT_ROOT / "faiss_index")
EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
TOP_K = 3
GROQ_MODEL = "qwen/qwen3.8-27b"

DISCLAIMER = "\n\n---\n*For educational purposes only — not investment advice.*"
SYSTEM_PROMPT = """You are a financial education assistant focused on Indian mutual funds and wealth management.

Answer the user's question using ONLY what's in the CONTEXT below. Don't add anything from outside.
If the context doesn't cover it, just say: "I don't have information on that."
Keep it simple and don't say things like "based on the context..." — just answer."""


def ask_concept_question(query: str) -> str:
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise EnvironmentError("GROQ_API_KEY missing — check your .env file.")

    if not Path(FAISS_INDEX_PATH).exists():
        raise FileNotFoundError(f"No FAISS index at {FAISS_INDEX_PATH}. Run the ingestion script first.")

    embeddings = HuggingFaceEmbeddings(model_name=EMBED_MODEL)
    db = FAISS.load_local(FAISS_INDEX_PATH, embeddings, allow_dangerous_deserialization=True)
    docs = db.similarity_search(query, k=TOP_K)

    if not docs:
        context_text = "(nothing found)"
    else:
        context_text = "\n\n---\n\n".join(
            f"[{i+1}] {doc.page_content.strip()}" for i, doc in enumerate(docs)
        )

    prompt = f"CONTEXT:\n{context_text}\n\nQUESTION: {query}"

    llm = ChatGroq(model=GROQ_MODEL, temperature=0, api_key=api_key)
    resp = llm.invoke([SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=prompt)])

    return resp.content.strip() + DISCLAIMER


if __name__ == "__main__":
    questions = [
        "What is NAV in mutual funds?",
        "What is expense ratio and how does it affect my returns?",
        "How do I file my income tax return in India?",  # should say "I don't have info"
    ]

    for i, q in enumerate(questions, 1):
        print(f"\nQ{i}: {q}")
        print("-" * 60)
        try:
            print(ask_concept_question(q))
        except Exception as e:
            print(f"Error: {e}")
