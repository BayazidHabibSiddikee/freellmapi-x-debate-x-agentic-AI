"""
services/agent/tools_registry.py — team tool access for the Business section.

Marin-style pattern, adapted to the monorepo:
  - each tool is a plain function with a schema + allowed roles
  - the executor validates (tool exists, role allowed, args present) BEFORE running
  - the Researcher workflow chains download → ingest into hybrid RAG

Import path: tools live at <monorepo>/tools. We insert the repo root into
sys.path so `from tools import pdf_downloader` works regardless of cwd.
"""

import os
import sys
import shutil
import tempfile
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

MONOREPO_ROOT = Path(__file__).resolve().parents[2]
for _p in (str(MONOREPO_ROOT), str(MONOREPO_ROOT / "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

RAG_URL = os.environ.get("RAG_SERVER_URL", "http://localhost:5080")

TOOL_ERRORS: List[str] = []  # non-fatal import problems, surfaced via /report


def _try(name: str):
    """Import a tool module; record failures without crashing the registry."""
    try:
        return __import__(name, fromlist=["*"])
    except Exception as e:  # noqa: BLE001 — any import failure is non-fatal
        TOOL_ERRORS.append(f"{name}: {e}")
        return None


pdf_downloader = _try("tools.pdf_downloader")
youtube_transcript = _try("tools.youtube_transcript")
stealth_browser = _try("tools.stealth_browser")


# ── Tool implementations ─────────────────────────────────────────────────────

def download_books(queries: List[str], study: bool = True) -> Dict[str, Any]:
    """Researcher flow: search the web for PDFs, download, ingest into RAG.

    pdf_downloader.download_books returns {query: filepath_or_empty}.
    """
    if pdf_downloader is None:
        raise RuntimeError("tools/pdf_downloader.py could not be imported")

    raw = pdf_downloader.download_books(list(queries))
    downloaded: List[Dict[str, Any]] = []
    for query, path in raw.items():
        downloaded.append({"query": query, "path": path or None,
                           "ok": bool(path)})
    ingested = []

    if study:
        import requests

        for entry in downloaded:
            if not entry["path"]:
                continue
            path = Path(entry["path"])
            if not path.exists():
                continue
            try:
                with open(path, "rb") as f:
                    res = requests.post(
                        f"{RAG_URL}/upload/doc",
                        files={"file": (path.name, f, "application/pdf")},
                        timeout=300,
                    )
                if res.ok:
                    ingested.append({"file": path.name, **res.json()})
                else:
                    ingested.append({"file": path.name, "ok": False,
                                     "error": res.text[:200]})
            except Exception as e:  # noqa: BLE001
                ingested.append({"file": path.name, "ok": False, "error": str(e)})

    return {"downloaded": downloaded, "rag_ingest": ingested}


def study(query: str, k: int = 6, source_type: Optional[str] = None) -> Dict[str, Any]:
    """Query the hybrid knowledge base (BM25 + embeddings)."""
    import requests

    payload: Dict[str, Any] = {"query": query, "k": k}
    if source_type:
        payload["source_type"] = source_type
    res = requests.post(f"{RAG_URL}/search", json=payload, timeout=60)
    res.raise_for_status()
    data = res.json()
    return {
        "results": [
            {"source": r["source"], "page": r.get("page", 0), "excerpt": r["content"][:500]}
            for r in data.get("results", [])
        ]
    }


def youtube_transcript_tool(url_or_text: str) -> Dict[str, Any]:
    """Fetch a YouTube transcript (auto-translated to English)."""
    if youtube_transcript is None:
        raise RuntimeError("tools/youtube_transcript.py could not be imported")
    url = url_or_text
    extracted = youtube_transcript.extract_youtube_url(url_or_text)
    if extracted:
        url = extracted if isinstance(extracted, str) else extracted[0]
    text = youtube_transcript.get_youtube_transcript(url)
    return {"url": url, "chars": len(text), "transcript_excerpt": text[:2000]}


def web_search(query: str) -> Dict[str, Any]:
    """Anti-detect web search via stealth_browser (Camoufox on :9377)."""
    if stealth_browser is None:
        raise RuntimeError("tools/stealth_browser.py could not be imported")
    markdown = stealth_browser.stealth_search(query)
    return {"query": query, "results_excerpt": markdown[:3000]}


# ── Registry ──────────────────────────────────────────────────────────────────

ToolFunc = Callable[..., Dict[str, Any]]

TOOLS: Dict[str, Dict[str, Any]] = {
    "download_books": {
        "description": (
            "Search the web for book/document PDFs, download them, and ingest "
            "them into the hybrid RAG knowledge base for future study."
        ),
        "args": {
            "queries": {"type": "array", "items": "string", "required": True,
                         "desc": "Book/document titles to find"},
            "study": {"type": "boolean", "required": False, "default": True,
                       "desc": "Ingest downloads into RAG"},
        },
        "roles": {"Researcher", "CTO", "Engineer"},
        "func": download_books,
    },
    "study": {
        "description": "Study from the knowledge base: hybrid BM25+embeddings search.",
        "args": {
            "query": {"type": "string", "required": True, "desc": "What to look up"},
            "k": {"type": "integer", "required": False, "default": 6},
            "source_type": {"type": "string", "required": False, "default": None},
        },
        "roles": {"Researcher", "CTO", "PM", "Judge", "Engineer", "Analyst"},
        "func": study,
    },
    "youtube_transcript": {
        "description": "Fetch the transcript of a YouTube video for study.",
        "args": {
            "url_or_text": {"type": "string", "required": True,
                             "desc": "YouTube URL or text containing one"},
        },
        "roles": {"Researcher", "CTO", "Engineer"},
        "func": youtube_transcript_tool,
    },
    "web_search": {
        "description": "Web search via the anti-detect stealth browser.",
        "args": {
            "query": {"type": "string", "required": True},
        },
        "roles": {"Researcher", "PM", "CTO"},
        "func": web_search,
    },
}


# ── Validation / execution ────────────────────────────────────────────────────

class ToolError(Exception):
    pass


def list_tools(role: Optional[str] = None) -> Dict[str, Any]:
    out = {}
    for name, spec in TOOLS.items():
        if role and role not in spec["roles"]:
            continue
        out[name] = {
            "description": spec["description"],
            "args": spec["args"],
            "roles": sorted(spec["roles"]),
        }
    return out


def execute(tool_name: str, args: Dict[str, Any], role: Optional[str]) -> Dict[str, Any]:
    spec = TOOLS.get(tool_name)
    if spec is None:
        raise ToolError(f"unknown tool '{tool_name}'. Available: {sorted(TOOLS)}")
    if role and role not in spec["roles"]:
        raise ToolError(
            f"role '{role}' is not permitted to use '{tool_name}' "
            f"(allowed: {sorted(spec['roles'])})"
        )

    # Auditor-lite: validate required args before execution
    clean_args: Dict[str, Any] = {}
    for arg_name, schema in spec["args"].items():
        value = args.get(arg_name, schema.get("default"))
        if value is None and schema.get("required"):
            raise ToolError(f"missing required argument '{arg_name}' for '{tool_name}'")
        if value is not None:
            clean_args[arg_name] = value

    return spec["func"](**clean_args)


def report() -> Dict[str, Any]:
    return {
        "tools": sorted(TOOLS),
        "import_errors": TOOL_ERRORS,
        "downloads_dir": str(MONOREPO_ROOT / "tools" / "downloads"),
    }
