# rag_server.py — Shared RAG server (port 5080)
#
# Supports two knowledge bases:
#   doc/   → books, documents  (PDF, DOCX, TXT, MD)
#   code/  → your source files (PY, C, CPP, H, MD)
#
# Both indexed into ONE FAISS index — source_type metadata lets you filter.
# File upload endpoints let Marin/Bayazid frontends accept files directly.
#
# pip install docx2txt   (for .docx support)

import asyncio
import gc
import os
import json
import shutil
import time
import pickle
import ctypes
import hashlib
import struct
from pathlib import Path
from typing import Dict, Any, List, Optional

from fastapi import FastAPI, UploadFile, File, HTTPException
from pydantic import BaseModel

try:
    import faiss
    from langchain_huggingface import HuggingFaceEmbeddings
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    from langchain_community.document_loaders import PyPDFLoader
    from langchain_core.documents import Document
    FAISS_AVAILABLE = True
except ImportError:
    FAISS_AVAILABLE = False
    print("⚠️ RAG dependencies not available")

try:
    from rank_bm25 import BM25Okapi
    BM25_AVAILABLE = True
except ImportError:
    BM25_AVAILABLE = False
    print("⚠️ rank_bm25 not installed — hybrid search disabled. Run: pip install rank-bm25")

try:
    import docx2txt
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False
    print("⚠️ docx2txt not installed — .docx skipped. Run: pip install docx2txt")


# ═══════════════════════════════════════════════════════════════════════════════
# PATHS
# ═══════════════════════════════════════════════════════════════════════════════
BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
DOC_DIR   = Path(BASE_DIR) / "doc"
CODE_DIR  = Path(BASE_DIR) / "code"
FAISS_DIR = Path(BASE_DIR) / "storage" / "faiss_db"

DOC_DIR.mkdir(parents=True, exist_ok=True)
CODE_DIR.mkdir(parents=True, exist_ok=True)
FAISS_DIR.mkdir(parents=True, exist_ok=True)

BM25_PATH = FAISS_DIR / "bm25.pkl"

# Reciprocal Rank Fusion constant (standard k=60)
RRF_K = 60


def _tokenize(text: str) -> List[str]:
    """Simple lowercase alphanumeric tokenizer for BM25."""
    import re
    return re.findall(r"[a-z0-9]+", text.lower())

DOC_EXTENSIONS  = {".pdf", ".docx", ".txt", ".md"}
CODE_EXTENSIONS = {".py", ".c", ".cpp", ".h", ".md"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}


# ═══════════════════════════════════════════════════════════════════════════════
# KNOWLEDGE BASE  —  low-memory: FAISS mmap + lazy embedding model
# ═══════════════════════════════════════════════════════════════════════════════
_LIBC = None
def _malloc_trim():
    """Release free memory from Python's allocator back to the OS."""
    global _LIBC
    if _LIBC is None:
        try:
            _LIBC = ctypes.CDLL("libc.so.6")
        except Exception:
            return
    try:
        _LIBC.malloc_trim(0)
    except Exception:
        pass


def _compact(force=False):
    """gc.collect + malloc_trim to return memory to OS."""
    if force:
        gc.collect(2)
    else:
        gc.collect()
    _malloc_trim()


# Thread-count environment vars — limits PyTorch/NumPy thread pool overhead
os.environ.setdefault("OMP_NUM_THREADS",    "1")
os.environ.setdefault("MKL_NUM_THREADS",    "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")


from config import EMBEDDING_MODEL

def _lazy_embeddings():
    """Create embedding model — called on first search, not at boot."""
    model = HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL,
        model_kwargs={"device": "cpu"},
        encode_kwargs={"batch_size": 32},
    )
    return model


class KnowledgeBase:
    """
    Unified FAISS index over doc/ and code/.
    Uses raw FAISS with mmap + lazy embedding loading to keep RAM low.
    """

    MANIFEST_PATH   = FAISS_DIR / "manifest.json"
    DOC_CHUNK_SIZE  = 450
    DOC_OVERLAP     = 30   # reduced overlap = fewer vectors
    CODE_CHUNK_SIZE = 300
    CODE_OVERLAP    = 40

    def __init__(self):
        self._raw_index = None      # raw faiss.Index (mmap'd)
        self._docstore  = None      # dict: docstore_id → Document
        self._id_map    = None      # dict: seq_id → docstore_id
        self.manifest: Dict[str, Any] = {"indexed": [], "failed": []}
        self._lc_vectorstore = None  # LangChain FAISS wrapper (used only during indexing)
        self._embeddings = None
        # Hybrid (BM25) state
        self._bm25 = None            # BM25Okapi instance
        self._bm25_corpus: List[Dict[str, Any]] = []   # [{"tokens", "content", "meta"}]
        self._bm25_pending: List[Dict[str, Any]] = []  # chunks indexed this session
        self._boot()

    # ── Startup ───────────────────────────────────────────────────────────────
    def _boot(self):
        if not FAISS_AVAILABLE:
            print("⚠️ FAISS not available — RAG disabled")
            return

        self._load_manifest()
        index_file = FAISS_DIR / "index.faiss"
        pkl_file   = FAISS_DIR / "index.pkl"

        if index_file.exists() and pkl_file.exists():
            try:
                # Memory-map the FAISS index — stays on disk, OS pages in on access
                self._raw_index = faiss.read_index(
                    str(index_file), faiss.IO_FLAG_MMAP
                )
                # Load docstore from pickle
                with open(pkl_file, "rb") as f:
                    self._docstore, self._id_map = pickle.load(f)
                n = len(self.manifest["indexed"])
                print(f"✅ KB loaded (mmap): {n} files, {self._raw_index.ntotal} vectors")
            except Exception as e:
                print(f"⚠️ mmap load failed ({e}) — falling back to index rebuild")
                self._raw_index = None
                self._docstore  = None
                self._id_map    = None
        else:
            # First boot — will build from scratch
            self._create_embeddings()
            self._index_new_files()
            self._unload_embeddings()
            return

        self._load_bm25()
        self._create_embeddings()
        self._index_new_files()
        self._unload_embeddings()
        _compact(force=True)

    def _create_embeddings(self):
        if self._embeddings is None:
            self._embeddings = _lazy_embeddings()

    def _unload_embeddings(self):
        """Release the embedding model to free PyTorch RAM."""
        if self._embeddings is not None:
            try:
                del self._embeddings
            except Exception:
                pass
            self._embeddings = None
        _compact(force=True)

    # ── Manifest ──────────────────────────────────────────────────────────────
    def _load_manifest(self):
        if self.MANIFEST_PATH.exists():
            try:
                with open(self.MANIFEST_PATH) as f:
                    self.manifest = json.load(f)
                self.manifest.setdefault("indexed", [])
                self.manifest.setdefault("failed",  [])
            except Exception:
                self.manifest = {"indexed": [], "failed": []}

    def _save_manifest(self):
        with open(self.MANIFEST_PATH, "w") as f:
            json.dump(self.manifest, f, indent=2)

    # ── File discovery ────────────────────────────────────────────────────────
    def _all_files(self) -> List[Path]:
        files = []
        for ext in DOC_EXTENSIONS:
            files.extend(DOC_DIR.glob(f"*{ext}"))
        for ext in CODE_EXTENSIONS:
            files.extend(CODE_DIR.glob(f"*{ext}"))
        return sorted(set(files))

    def _index_new_files(self):
        already_indexed = set(self.manifest["indexed"])
        already_failed  = {e["file"] for e in self.manifest["failed"]}
        new_files = [
            f for f in self._all_files()
            if f.name not in already_indexed and f.name not in already_failed
        ]
        if not new_files:
            return
        print(f"📚 Indexing {len(new_files)} new file(s)...")
        self._create_embeddings()
        for path in new_files:
            self._index_single_file(path)
        self._save_faiss()
        self._save_manifest()
        _compact()
        print(f"✅ Done: {len(self.manifest['indexed'])} total indexed")

    def _save_faiss(self):
        """Save the raw FAISS index + docstore to disk, then reload mmap."""
        if self._lc_vectorstore is None:
            return
        self._save_bm25()
        self._lc_vectorstore.save_local(str(FAISS_DIR))
        # Sync raw pointers from LC wrapper before mmap reload
        self._raw_index = self._lc_vectorstore.index
        self._docstore  = self._lc_vectorstore.docstore
        self._id_map    = self._lc_vectorstore.index_to_docstore_id
        # Reload raw index with mmap (discards LC wrapper's in-RAM copy)
        index_file = FAISS_DIR / "index.faiss"
        pkl_file   = FAISS_DIR / "index.pkl"
        if index_file.exists() and pkl_file.exists():
            try:
                self._raw_index = faiss.read_index(str(index_file), faiss.IO_FLAG_MMAP)
                with open(pkl_file, "rb") as f:
                    self._docstore, self._id_map = pickle.load(f)
            except Exception as e:
                print(f"⚠️ mmap reload failed: {e}")

    # ── Build index using LangChain wrapper (easiest path for chunk→embed) ───
    def _ensure_lc_store(self):
        if self._lc_vectorstore is not None:
            return
        if self._raw_index is not None and self._docstore is not None and self._id_map is not None:
            from langchain_community.vectorstores import FAISS as LC_FAISS
            self._lc_vectorstore = LC_FAISS(
                self._raw_index,
                self._docstore,
                self._id_map,
                self._embeddings,
            )
        else:
            self._lc_vectorstore = None

    # ── BM25 (hybrid sparse index) ────────────────────────────────────────────
    def _load_bm25(self):
        """Load persisted BM25 corpus; rebuild from docstore if missing."""
        if not BM25_AVAILABLE:
            return
        if BM25_PATH.exists():
            try:
                with open(BM25_PATH, "rb") as f:
                    payload = pickle.load(f)
                self._bm25_corpus = payload["corpus"]
                self._rebuild_bm25_index()
                print(f"✅ BM25 loaded: {len(self._bm25_corpus)} chunks")
                return
            except Exception as e:
                print(f"⚠️ BM25 load failed ({e}) — rebuilding")
        self._rebuild_bm25_from_docstore()

    def _rebuild_bm25_from_docstore(self):
        """Rebuild the BM25 corpus from every chunk currently in the docstore."""
        if not BM25_AVAILABLE or self._docstore is None:
            return
        try:
            self._bm25_corpus = []
            for doc_id in set(self._id_map.values()) if self._id_map else []:
                doc = self._docstore.search(doc_id)
                if doc is None:
                    continue
                meta = doc.metadata
                self._bm25_corpus.append({
                    "tokens":  _tokenize(doc.page_content),
                    "content": doc.page_content,
                    "meta": {
                        "source":      meta.get("source_file") or meta.get("source", "Unknown"),
                        "source_type": meta.get("source_type", "doc"),
                        "language":    meta.get("language", "text"),
                        "page":        meta.get("page", 0),
                    },
                })
            self._rebuild_bm25_index()
            self._save_bm25()
            print(f"✅ BM25 rebuilt from docstore: {len(self._bm25_corpus)} chunks")
        except Exception as e:
            print(f"⚠️ BM25 rebuild failed: {e}")

    def _rebuild_bm25_index(self):
        if not BM25_AVAILABLE:
            return
        if self._bm25_corpus:
            self._bm25 = BM25Okapi([c["tokens"] for c in self._bm25_corpus])
        else:
            self._bm25 = None

    def _save_bm25(self):
        """Merge pending chunks into the corpus, persist, and re-index."""
        if not BM25_AVAILABLE:
            return
        if self._bm25_pending:
            self._bm25_corpus.extend(self._bm25_pending)
            self._bm25_pending = []
            self._rebuild_bm25_index()
        try:
            with open(BM25_PATH, "wb") as f:
                pickle.dump({"corpus": self._bm25_corpus}, f, protocol=pickle.HIGHEST_PROTOCOL)
        except Exception as e:
            print(f"⚠️ BM25 save failed: {e}")

    def _bm25_search(self, query: str, k: int,
                     source_type: str = None) -> List[Dict[str, Any]]:
        if self._bm25 is None:
            return []
        tokens = _tokenize(query)
        if not tokens:
            return []
        scores = self._bm25.get_scores(tokens)
        ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
        results = []
        for idx in ranked[: k * 3]:
            entry = self._bm25_corpus[idx]
            if source_type and entry["meta"].get("source_type") != source_type:
                continue
            results.append({"content": entry["content"], **entry["meta"]})
            if len(results) >= k:
                break
        return results

    # ── Loaders ───────────────────────────────────────────────────────────────
    def _load_file(self, path: Path) -> List[Document]:
        ext         = path.suffix.lower()
        name        = path.name
        source_type = "code" if path.parent.resolve() == CODE_DIR.resolve() else "doc"

        if ext == ".pdf":
            docs = PyPDFLoader(str(path)).load()
            for d in docs:
                d.metadata.update({"source_file": name, "source_type": "doc", "language": "text"})
            return docs

        if ext == ".docx":
            if not DOCX_AVAILABLE:
                raise ImportError("docx2txt not installed — run: pip install docx2txt")
            text = docx2txt.process(str(path))
            return [Document(page_content=text,
                             metadata={"source_file": name, "source_type": "doc",
                                       "language": "text", "page": 0})]

        if ext == ".txt":
            text = path.read_text(encoding="utf-8", errors="ignore")
            return [Document(page_content=text,
                             metadata={"source_file": name, "source_type": source_type,
                                       "language": "text", "page": 0})]

        if ext == ".md":
            text = path.read_text(encoding="utf-8", errors="ignore")
            return [Document(page_content=text,
                             metadata={"source_file": name, "source_type": source_type,
                                       "language": "markdown", "page": 0})]

        if ext == ".py":
            text = path.read_text(encoding="utf-8", errors="ignore")
            return [Document(page_content=text,
                             metadata={"source_file": name, "source_type": "code",
                                       "language": "python", "page": 0})]

        if ext in {".c", ".cpp", ".h"}:
            text = path.read_text(encoding="utf-8", errors="ignore")
            lang = {"c": "c", ".cpp": "cpp", ".h": "c"}.get(ext, "c")
            return [Document(page_content=text,
                             metadata={"source_file": name, "source_type": "code",
                                       "language": lang, "page": 0})]

        raise ValueError(f"Unsupported extension: {ext}")

    def _get_splitter(self, path: Path) -> RecursiveCharacterTextSplitter:
        if path.suffix.lower() in {".py", ".c", ".cpp", ".h"}:
            return RecursiveCharacterTextSplitter(
                chunk_size=self.CODE_CHUNK_SIZE,
                chunk_overlap=self.CODE_OVERLAP,
                separators=["\n\nclass ", "\n\ndef ", "\n\n", "\n", " ", ""],
            )
        return RecursiveCharacterTextSplitter(
            chunk_size=self.DOC_CHUNK_SIZE,
            chunk_overlap=self.DOC_OVERLAP,
            separators=["\n\n", "\n", ". ", " ", ""],
        )

    # ── Core indexer ──────────────────────────────────────────────────────────
    def _index_single_file(self, path: Path):
        name = path.name
        try:
            documents = self._load_file(path)
            if not documents:
                raise ValueError("File produced zero content")

            splitter = self._get_splitter(path)
            chunks   = splitter.split_documents(documents)

            valid = []
            for c in chunks:
                if not isinstance(c.page_content, str):
                    continue
                clean = c.page_content.strip()
                if len(clean) > 10 and any(ch.isalnum() for ch in clean):
                    c.page_content = clean
                    valid.append(c)

            if not valid:
                raise ValueError("No valid chunks after filtering")

            if self._lc_vectorstore is None:
                from langchain_community.vectorstores import FAISS as LC_FAISS
                self._lc_vectorstore = LC_FAISS.from_documents(valid, self._embeddings)
            else:
                try:
                    self._lc_vectorstore.add_documents(valid)
                except Exception as e:
                    print(f"  [!] Partial embed error for {name}: {e}")

            if BM25_AVAILABLE:
                for c in valid:
                    meta = c.metadata
                    self._bm25_pending.append({
                        "tokens":  _tokenize(c.page_content),
                        "content": c.page_content,
                        "meta": {
                            "source":      meta.get("source_file") or meta.get("source", "Unknown"),
                            "source_type": meta.get("source_type", "doc"),
                            "language":    meta.get("language", "text"),
                            "page":        meta.get("page", 0),
                        },
                    })

            self.manifest["indexed"].append(name)
            src = path.parent.name
            print(f"  ✓ [{src}] {name}: {len(valid)} chunks")

        except Exception as e:
            self.manifest["failed"].append({"file": name, "reason": str(e)})
            print(f"  ✗ {name}: SKIPPED — {e}")

        finally:
            try:
                del documents, chunks, valid
            except Exception:
                pass
            _compact()

    # ── Public API ────────────────────────────────────────────────────────────
    def _dense_search(self, query: str, k: int,
                      source_type: str = None) -> List[Dict[str, Any]]:
        if self._raw_index is None:
            return []
        try:
            self._create_embeddings()
            # Embed the query
            q_vec = self._embeddings.embed_query(query)
            import numpy as np
            q_np = np.array([q_vec], dtype=np.float32)
            # Search using raw FAISS index (mmap'd, no RAM load)
            scores, idxs = self._raw_index.search(q_np, k * 3 if source_type else k)
            results = []
            for score, idx in zip(scores[0], idxs[0]):
                if idx < 0:
                    continue
                doc_id  = self._id_map.get(int(idx))
                if doc_id is None:
                    continue
                doc = self._docstore.search(doc_id)
                if doc is None:
                    continue
                meta = doc.metadata
                if source_type and meta.get("source_type") != source_type:
                    continue
                results.append({
                    "content":     doc.page_content,
                    "source":      meta.get("source_file") or meta.get("source", "Unknown"),
                    "source_type": meta.get("source_type", "doc"),
                    "language":    meta.get("language",    "text"),
                    "page":        meta.get("page",        0),
                })
                if len(results) >= k:
                    break
            return results
        except Exception as e:
            print(f"⚠️ Dense search error: {e}")
            return []

    def _hybrid_search(self, query: str, k: int,
                       source_type: str = None) -> List[Dict[str, Any]]:
        """Fuse dense (FAISS) + sparse (BM25) rankings via Reciprocal Rank Fusion."""
        dense = self._dense_search(query, k, source_type)
        sparse = self._bm25_search(query, k, source_type) if BM25_AVAILABLE else []

        if not sparse:
            return dense

        def key(r: Dict[str, Any]) -> str:
            return hashlib.md5(r["content"].encode("utf-8")).hexdigest()

        fused: Dict[str, Dict[str, Any]] = {}
        scores: Dict[str, float] = {}
        for ranked in (dense, sparse):
            for rank, r in enumerate(ranked):
                kk = key(r)
                fused.setdefault(kk, r)
                scores[kk] = scores.get(kk, 0.0) + 1.0 / (RRF_K + rank + 1)

        ordered = sorted(fused.items(), key=lambda kv: scores[kv[0]], reverse=True)
        return [r for _, r in ordered[:k]]

    def search(self, query: str, k: int = 10,
               source_type: str = None,
               mode: str = "hybrid") -> List[Dict[str, Any]]:
        if mode == "dense":
            return self._dense_search(query, k, source_type)
        return self._hybrid_search(query, k, source_type)

    def get_context(self, query: str, k: int = 10,
                    source_type: str = None) -> str:
        results = self.search(query, k=k, source_type=source_type)
        if not results:
            return ""

        by_source: Dict[str, List[Dict]] = {}
        for r in results:
            by_source.setdefault(r["source"], []).append(r)

        parts = ["[KNOWLEDGE FROM YOUR BOOKS & CODE]\n"]
        for source, chunks in list(by_source.items())[:5]:
            stype = chunks[0]["source_type"]
            lang  = chunks[0]["language"]
            icon  = "💻" if stype == "code" else "📖"
            parts.append(f"\n{icon} From {source}:")
            for chunk in chunks[:3]:
                if stype == "code":
                    parts.append(f"```{lang}\n{chunk['content'][:600]}\n```")
                else:
                    parts.append(chunk["content"][:600])
        return "\n".join(parts)

    def add_file(self, path: Path) -> Dict[str, Any]:
        name = path.name
        if name in self.manifest["indexed"]:
            self.manifest["indexed"].remove(name)
        self.manifest["failed"] = [e for e in self.manifest["failed"] if e["file"] != name]

        # Purge stale BM25 chunks for this file so re-indexing doesn't duplicate
        self._bm25_corpus = [c for c in self._bm25_corpus if c["meta"]["source"] != name]
        self._bm25_pending = [c for c in self._bm25_pending if c["meta"]["source"] != name]
        self._rebuild_bm25_index()

        self._create_embeddings()
        self._ensure_lc_store()
        self._index_single_file(path)
        self._save_faiss()
        self._save_manifest()
        self._unload_embeddings()

        success = name in self.manifest["indexed"]
        return {
            "ok":      success,
            "message": f"Indexed {name}" if success else f"Failed: see /report",
        }

    def get_report(self) -> Dict[str, Any]:
        return {
            "total":   len(self.manifest["indexed"]),
            "indexed": self.manifest["indexed"],
            "failed":  self.manifest["failed"],
        }


# Global instance
kb = KnowledgeBase()


# ═══════════════════════════════════════════════════════════════════════════════
# FASTAPI
# ═══════════════════════════════════════════════════════════════════════════════
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="RAG Server", version="2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class SearchRequest(BaseModel):
    query:       str
    k:           int = 10
    source_type: str = None  # "doc" | "code" | None = search everything
    mode:        str = "hybrid"  # "hybrid" (BM25+embeddings RRF) | "dense"


# ── Search ────────────────────────────────────────────────────────────────────

@app.post("/search")
async def search(req: SearchRequest):
    results = await asyncio.to_thread(
        kb.search, req.query, min(req.k, 20), req.source_type, req.mode
    )
    return {"results": results, "count": len(results), "mode": req.mode}


@app.post("/context")
async def context(req: SearchRequest):
    ctx = await asyncio.to_thread(kb.get_context, req.query, min(req.k, 20), req.source_type)
    return {"context": ctx}


# ── Upload ────────────────────────────────────────────────────────────────────

@app.post("/upload/doc")
async def upload_doc(file: UploadFile = File(...)):
    """Upload PDF, DOCX, TXT, or MD into doc/ and index immediately."""
    ext = Path(file.filename).suffix.lower()
    if ext not in DOC_EXTENSIONS:
        raise HTTPException(400, f"Unsupported type '{ext}'. Allowed: {DOC_EXTENSIONS}")
    dest = DOC_DIR / file.filename
    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)
    result = await asyncio.to_thread(kb.add_file, dest)
    return {"filename": file.filename, **result}


@app.post("/upload/code")
async def upload_code(file: UploadFile = File(...)):
    """Upload PY, C, CPP, H, or MD into code/ and index immediately."""
    ext = Path(file.filename).suffix.lower()
    if ext not in CODE_EXTENSIONS:
        raise HTTPException(400, f"Unsupported type '{ext}'. Allowed: {CODE_EXTENSIONS}")
    dest = CODE_DIR / file.filename
    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)
    result = await asyncio.to_thread(kb.add_file, dest)
    return {"filename": file.filename, **result}


@app.post("/upload/image")
async def upload_image(file: UploadFile = File(...)):
    """Upload image into static/uploads/ for vision tasks. Not RAG-indexed."""
    ext = Path(file.filename).suffix.lower()
    if ext not in IMAGE_EXTENSIONS:
        raise HTTPException(400, f"Unsupported type '{ext}'. Allowed: {IMAGE_EXTENSIONS}")
    upload_dir = Path(BASE_DIR) / "static" / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    dest = upload_dir / file.filename
    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)
    return {"ok": True, "filename": file.filename, "url": f"/static/uploads/{file.filename}"}


# ── Info ──────────────────────────────────────────────────────────────────────

@app.get("/report")
async def report():
    return kb.get_report()


@app.get("/health")
async def health():
    return {
        "status":   "operational",
        "port":     5080,
        "total":    len(kb.manifest["indexed"]),
        "ready":    kb._raw_index is not None,
        "hybrid":   BM25_AVAILABLE and kb._bm25 is not None,
        "bm25_chunks": len(kb._bm25_corpus),
        "doc_dir":  str(DOC_DIR),
        "code_dir": str(CODE_DIR),
    }


if __name__ == "__main__":
    import argparse, resource
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=5080)
    parser.add_argument("--max-memory-mb", type=int, default=0,
                        help="Hard RSS limit in MB (0 to disable)")
    args = parser.parse_args()

    if args.max_memory_mb > 0:
        limit = args.max_memory_mb * 1024 * 1024
        try:
            resource.setrlimit(resource.RLIMIT_AS, (limit, limit))
            print(f"🧠 Memory limit set to {args.max_memory_mb} MB (RLIMIT_AS)")
        except Exception as e:
            print(f"⚠️ Could not set memory limit: {e}")

    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=args.port, reload=False)