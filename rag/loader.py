# rag/loader.py — one loader, both AI engines import from here

import os, json, hashlib
from langchain_community.vectorstores import FAISS
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings

DOC_DIR   = "doc"
FAISS_DIR = "storage/faiss_db"
MANIFEST  = os.path.join(FAISS_DIR, "manifest.json")

embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

def _hash(path):
    return hashlib.md5(open(path,"rb").read()).hexdigest()

def load_or_build() -> FAISS:
    os.makedirs(FAISS_DIR, exist_ok=True)
    manifest = json.load(open(MANIFEST)) if os.path.exists(MANIFEST) else {}

    pdfs = [f for f in os.listdir(DOC_DIR) if f.endswith(".pdf")] if os.path.exists(DOC_DIR) else []
    new_docs, updated = [], False

    for pdf in pdfs:
        path = os.path.join(DOC_DIR, pdf)
        h = _hash(path)
        if manifest.get(pdf) == h:
            continue                        # already indexed
        try:
            pages = PyPDFLoader(path).load()
            chunks = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50).split_documents(pages)
            new_docs.extend(chunks)
            manifest[pdf] = h
            updated = True
            print(f"[RAG] Indexed: {pdf}")
        except Exception as e:
            print(f"[RAG] Skipped {pdf}: {e}")

    # Load or create the vector store
    if os.path.exists(os.path.join(FAISS_DIR, "index.faiss")):
        db = FAISS.load_local(FAISS_DIR, embeddings, allow_dangerous_deserialization=True)
        if new_docs:
            db.add_documents(new_docs)
    else:
        if not new_docs:
            return None
        db = FAISS.from_documents(new_docs, embeddings)

    if updated:
        db.save_local(FAISS_DIR)
        json.dump(manifest, open(MANIFEST, "w"), indent=2)

    return db

# Singleton — loaded once, shared by both Marin and Bayazid
rag_db = load_or_build()