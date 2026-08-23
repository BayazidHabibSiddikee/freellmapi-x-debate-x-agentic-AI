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


# ── Project-document reading (non-coders understand the repo) ─────────────────

READABLE_EXTENSIONS = {".md", ".markdown", ".txt", ".rst", ".json", ".yaml", ".yml", ".cfg", ".ini", ".toml"}
MAX_READ_BYTES = 60_000


def _safe_under_home(path: str) -> Path:
    home = Path.home().resolve()
    p = Path(os.path.expanduser(path)).resolve()
    if p != home and home not in p.parents:
        raise PermissionError(f"path must be under {home}")
    return p


def read_project_docs(path: str = ".", glob: str = "**/*.md",
                      max_chars: int = 6000) -> Dict[str, Any]:
    """List/read documentation files (README, *.md, *.txt…) in a project folder."""
    root = _safe_under_home(path)
    hits: List[Dict[str, Any]] = []
    budget = max(1000, min(max_chars, 20_000))
    for f in sorted(root.glob(glob)):
        if not f.is_file() or f.suffix.lower() not in READABLE_EXTENSIONS:
            continue
        rel = str(f.relative_to(root))
        try:
            text = f.read_text(encoding="utf-8", errors="ignore")[:MAX_READ_BYTES]
        except Exception as e:  # noqa: BLE001
            hits.append({"file": rel, "error": str(e)[:120]})
            continue
        excerpt = text[:budget]
        budget -= len(excerpt)
        hits.append({"file": rel, "chars": len(text), "excerpt": excerpt})
        if budget <= 0:
            break
        if len(hits) >= 10:
            break
    return {"root": str(root), "files": hits}


def read_pdf(path: str, pages: str = "") -> Dict[str, Any]:
    """Extract text from a specific PDF under ~/ (e.g. an ingested book)."""
    p = _safe_under_home(path)
    if p.suffix.lower() != ".pdf":
        raise ValueError("not a pdf")
    try:
        import pypdf
    except ImportError:
        raise RuntimeError("pypdf not installed in venv")
    reader = pypdf.PdfReader(str(p))
    total = len(reader.pages)
    if pages:
        start, end = (pages.split("-", 1) + [pages])[:2]
        idx = range(int(start) - 1, min(int(end), total))
    else:
        idx = range(min(total, 8))
    text = "\n\n".join(
        f"[page {i+1}] {reader.pages[i].extract_text() or ''}" for i in idx
    )
    return {"file": str(p), "total_pages": total, "text": text[:8000]}


# ── Coding via headless CLI (Engineer-only) ───────────────────────────────────

def code_task(prompt: str, cwd: str = ".", agent: Optional[str] = None,
              timeout_seconds: int = 900) -> Dict[str, Any]:
    """Hand a coding subtask to a headless coding agent inside the project folder.

    Uses the same validated pipeline as judge-dispatch: path must stay under ~,
    output is captured and returned for review.
    """
    from dispatcher import resolve_workspace, _load_business_settings, _cli_for

    resolved = resolve_workspace(cwd)
    chosen = agent or _load_business_settings().get("dispatch_agent_default", "claude")
    argv = _cli_for(chosen)
    if argv is None:
        raise RuntimeError(f"'{chosen}' CLI not found on PATH")

    import subprocess
    proc = subprocess.run(
        [*argv, prompt], cwd=resolved, capture_output=True, text=True,
        timeout=max(30, min(timeout_seconds, 3600)),
    )
    return {
        "agent": chosen,
        "cwd": resolved,
        "exit_code": proc.returncode,
        "output": (proc.stdout or "")[-4000:],
        "error": (proc.stderr or "")[-1000:] if proc.returncode else "",
    }


def verify_output(path: str = ".", checks: Optional[List[str]] = None) -> Dict[str, Any]:
    """Verify output artifacts exist and are non-empty after a coding task.

    Walks the workspace for expected files (README.md, dist/, build/, coverage/ etc.)
    and returns a pass/fail summary. Useful for post-dispatch quality gates.
    """
    root = _safe_under_home(path)
    default_checks = [
        "**/*.md", "*.json", "package.json", "pyproject.toml",
        "dist/**", "build/**", "coverage/**", ".github/**",
        "tests/**/*.py", "test/**/*.ts", "src/**/*.js",
    ]
    patterns = checks or default_checks
    found: List[Dict[str, Any]] = []
    total_files = 0
    for pat in patterns:
        for f in sorted(root.glob(pat)):
            if not f.is_file():
                continue
            total_files += 1
            try:
                sz = f.stat().st_size
                found.append({"file": str(f.relative_to(root)), "size_bytes": sz})
            except OSError:
                found.append({"file": str(f.relative_to(root)), "size_bytes": 0, "error": "read-failed"})
    return {
        "root": str(root),
        "total_files_found": total_files,
        "patterns_matched": len(patterns),
        "samples": found[:30],
    }


def run_tests(
    cwd: str = ".",
    framework: Optional[str] = None,
    args: Optional[List[str]] = None,
    timeout_seconds: int = 120,
) -> Dict[str, Any]:
    """Run a test suite in the given project folder and return results.

    Auto-detects framework from project files when `framework` is omitted:
      - package.json with jest/mocha/vitest → npm test or npx <runner>
      - pyproject.toml / setup.cfg / tox.ini → pytest
      - Makefile with test target → make test
      - fall back to a simple glob for *test*.* files
    """
    root = Path(_safe_under_home(cwd))
    detected = framework or _detect_framework(root)
    commands = _test_commands(detected, args or [])

    results: List[Dict[str, Any]] = []
    for cmd in commands:
        try:
            proc = subprocess.run(
                cmd, cwd=str(root), capture_output=True, text=True,
                timeout=max(15, min(timeout_seconds, 600)),
            )
            results.append({
                "command": " ".join(cmd),
                "exit_code": proc.returncode,
                "stdout": (proc.stdout or "")[-2000:],
                "stderr": (proc.stderr or "")[-1000:] if proc.returncode else "",
                "ok": proc.returncode == 0,
            })
        except subprocess.TimeoutExpired:
            results.append({"command": " ".join(cmd), "ok": False,
                             "error": f"timeout after {timeout_seconds}s"})
        except Exception as e:  # noqa: BLE001
            results.append({"command": " ".join(cmd), "ok": False,
                             "error": str(e)[:300]})

    all_ok = all(r.get("ok") for r in results) if results else False
    return {
        "cwd": str(root),
        "framework_detected": detected,
        "runs": results,
        "all_passed": all_ok,
    }


def _detect_framework(root: Path) -> str:
    has_py = any(root.glob("**/*.py"))
    has_js = any(root.glob("**/*.{js,ts,jsx,tsx}"))
    pkg = root / "package.json"
    pyproj = root / "pyproject.toml"
    tox = root / "tox.ini"
    setup = root / "setup.cfg"
    makefile = root / "Makefile"
    if (pkg.exists() and pkg.read_text()[:5000].find("jest") != -1):
        return "jest"
    if (pkg.exists() and pkg.read_text()[:5000].find("vitest") != -1):
        return "vitest"
    if (pkg.exists() and pkg.read_text()[:5000].find("mocha") != -1):
        return "mocha"
    if has_py and (pyproj.exists() or tox.exists() or setup.exists()):
        return "pytest"
    if makefile.exists():
        return "make"
    if has_py:
        return "pytest"
    if has_js:
        return "npm-test"
    return "none"


def _test_commands(framework: str, extra_args: List[str]) -> List[List[str]]:
    if framework == "pytest":
        cmds = [["python", "-m", "pytest", *extra_args]]
        if shutil.which("uv"):
            cmds.append(["uv", "run", "pytest", *extra_args])
        return cmds
    if framework == "jest":
        return [["npx", "jest", *extra_args]]
    if framework == "vitest":
        return [["npx", "vitest", "run", *extra_args]]
    if framework == "mocha":
        return [["npx", "mocha", *extra_args]]
    if framework == "make":
        return [["make", "test", *(f"EXTRA={a}" for a in extra_args)]]
    if framework == "npm-test":
        return [["npm", "test", "--", *extra_args]] if extra_args else [["npm", "test"]]
    return []

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
        "roles": {"Researcher", "CTO", "PM", "Judge", "Engineer", "Analyst", "Reviewer", "DevOps", "Security", "Writer"},
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
        "roles": {"Researcher", "PM", "CTO", "Security", "DevOps"},
        "func": web_search,
    },
    "read_project_docs": {
        "description": (
            "Read documentation (README, *.md, *.txt, configs) inside a project "
            "folder — for non-coders to understand the codebase."
        ),
        "args": {
            "path": {"type": "string", "required": False, "default": ".",
                      "desc": "Project folder under ~"},
            "glob": {"type": "string", "required": False,
                      "default": "**/*.md", "desc": "Glob of files to read"},
            "max_chars": {"type": "integer", "required": False, "default": 6000},
        },
        # everyone may read; coders rarely need it but no reason to block
        "roles": {"CTO", "PM", "Judge", "Researcher", "Analyst", "Engineer", "Reviewer", "DevOps", "Security", "Writer"},
        "func": read_project_docs,
    },
    "read_pdf": {
        "description": "Extract text from a PDF anywhere under ~ (books, papers).",
        "args": {
            "path": {"type": "string", "required": True,
                      "desc": "Path to the .pdf file"},
            "pages": {"type": "string", "required": False, "default": "",
                       "desc": "e.g. '5' or '10-20'; default first 8 pages"},
        },
        "roles": {"Researcher", "PM", "Judge", "Analyst", "CTO", "Security", "Reviewer", "Writer"},
        "func": read_pdf,
    },
    "run_tests": {
        "description": (
            "Run the project's test suite and return pass/fail results. "
            "Auto-detects pytest / jest / vitest / mocha / make. DevOps and Engineers only."
        ),
        "args": {
            "cwd": {"type": "string", "required": False, "default": ".",
                     "desc": "Project folder under ~"},
            "framework": {"type": "string", "required": False, "default": None,
                           "desc": "'pytest' | 'jest' | 'vitest' | 'mocha' | 'make' | auto-detect"},
            "args": {"type": "array", "items": "string", "required": False, "default": [],
                      "desc": "Extra args forwarded to the test runner (e.g. ['-k', 'test_auth'])"},
            "timeout_seconds": {"type": "integer", "required": False, "default": 120},
        },
        "roles": {"Engineer", "DevOps", "Reviewer"},
        "func": run_tests,
    },
    "verify_output": {
        "description": (
            "Post-task verification: scan the project for expected output artifacts "
            "(docs, dist/, tests/, configs) and report what exists. QA gate after dispatch."
        ),
        "args": {
            "path": {"type": "string", "required": False, "default": ".",
                      "desc": "Project folder under ~"},
            "checks": {"type": "array", "items": "string", "required": False, "default": None,
                        "desc": "Glob patterns to look for (e.g. ['README.md', 'dist/**', 'tests/**/*.py'])"},
        },
        "roles": {"Engineer", "Reviewer", "DevOps", "Analyst"},
        "func": verify_output,
    },
    "code_task": {
        "description": (
            "Run a coding subtask through a headless coding agent "
            "(claude/opencode) inside a project folder. Engineers only."
        ),
        "args": {
            "prompt": {"type": "string", "required": True,
                        "desc": "Self-contained instruction for the coding agent"},
            "cwd": {"type": "string", "required": False, "default": ".",
                     "desc": "Project folder under ~"},
            "agent": {"type": "string", "required": False, "default": None,
                       "desc": "'claude' | 'opencode' (default from settings)"},
            "timeout_seconds": {"type": "integer", "required": False,
                                 "default": 900},
        },
        # Only people whose job is producing files: Engineers (product code)
        # and DevOps (infra/pipelines). Everyone else reads docs / dispatches via judge.
        "roles": {"Engineer", "DevOps"},
        "func": code_task,
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


def execute(tool_name: str, args: Dict[str, Any], role: Optional[str],
            allowed: Optional[List[str]] = None) -> Dict[str, Any]:
    """Execute with role gates PLUS per-person grants from their persona file."""
    spec = TOOLS.get(tool_name)
    if spec is None:
        raise ToolError(f"unknown tool '{tool_name}'. Available: {sorted(TOOLS)}")
    grants = set(allowed or [])
    if role and role not in spec["roles"] and tool_name not in grants:
        raise ToolError(
            f"'{role}' may not use '{tool_name}' "
            f"(role-allowed: {sorted(spec['roles'])}; persona-granted: {sorted(grants)})"
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
