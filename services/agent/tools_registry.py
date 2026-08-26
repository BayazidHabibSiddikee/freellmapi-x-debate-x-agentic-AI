"""
services/agent/tools_registry.py — team tool access for the Business section.

Marin-style pattern, adapted to the monorepo:
  - each tool is a plain function with a schema + allowed roles
  - the executor validates (tool exists, role allowed, args present) BEFORE running
  - the Researcher workflow chains download → ingest into hybrid RAG

Import path: tools live at <monorepo>/tools. We insert the repo root into
sys.path so `from tools import pdf_downloader` works regardless of cwd.
"""

import json
import os
import sys
import shutil
import tempfile
import urllib.request
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

MONOREPO_ROOT = Path(__file__).resolve().parents[2]
for _p in (str(MONOREPO_ROOT), str(MONOREPO_ROOT / "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

RAG_URL = os.environ.get("RAG_SERVER_URL", "http://127.0.0.1:5080")

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
raspberry_pi_imager = _try("tools.raspberry_pi_imager")


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


def install_raspberry_pi_imager(platform_key: str = "auto",
                                output_dir: str = None,
                                overwrite: bool = False) -> Dict[str, Any]:
    """Download the latest Raspberry Pi Imager installer.

    Auto-detects the current platform by default, then matches the right asset
    from the latest GitHub release (raspberrypi/rpi-imager). Skips re-download
    when the file already exists with matching size.

    Returns a dict with keys: ok, version, platform, filepath, url, size_bytes,
    asset_name.
    """
    if raspberry_pi_imager is None:
        raise RuntimeError("tools/raspberry_pi_imager.py could not be imported")
    return raspberry_pi_imager.download_imager(
        platform_key=platform_key,
        output_dir=output_dir,
        overwrite=overwrite,
    )


def list_raspberry_pi_imager_assets() -> Dict[str, Any]:
    """List the assets in the latest Raspberry Pi Imager release."""
    if raspberry_pi_imager is None:
        raise RuntimeError("tools/raspberry_pi_imager.py could not be imported")
    assets = raspberry_pi_imager.list_available_assets()
    return {
        "count": len(assets),
        "assets": [
            {"name": a["name"], "size": a["size"], "url": a["browser_download_url"]}
            for a in assets
        ],
    }


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


# ── Phase 3: cross-team knowledge marketplace ──────────────────────────────────

def _publish_insight_wrapper(topic: str, insight: str, team: str = "",
                             author: str = "") -> Dict[str, Any]:
    """Publish a lesson to the shared marketplace. Team/author default to the
    dispatching agent's identity (AGENT_TEAM / AGENT_NAME env) so callers don't
    have to repeat them."""
    import industry
    return industry.publish(
        team=team or os.environ.get("AGENT_TEAM", "main"),
        author=author or os.environ.get("AGENT_NAME", "unknown"),
        topic=topic, insight=insight,
    )


def _cross_team_search_wrapper(query: str, exclude_team: Optional[str] = None,
                               limit: int = 6) -> Dict[str, Any]:
    import industry
    results = industry.search(
        query,
        exclude_team=exclude_team or os.environ.get("AGENT_TEAM") or None,
        limit=limit,
    )
    return {"query": query, "count": len(results),
            "results": results,
            "note": "insights are from teams OTHER than yours by default"}


def _urgent_alert_wrapper(message: str, receiver_emails: Optional[List[str]] = None,
                          team: str = "", urgency: str = "normal") -> Dict[str, Any]:
    """Send an urgent paged alert via the configured Telegram bot(s) to owners.

    Looks up config/business/settings.json → telegram_bots[].owner_email / gmails.
    Sends to each matching bot's configured owner email (via the console's
    /api/business/telegram/send POST endpoint), so the message lands in the
    owner's Telegram group where the bot is running.

    The `receiver_emails` arg is an explicit override when called mid-debate
    and the caller wants to page a specific person rather than every owner.
    """
    import urllib.request

    settings_file = Path(__file__).resolve().parents[2] / "config" / "business" / "settings.json"
    try:
        settings = json.loads(settings_file.read_text()) if settings_file.exists() else {}
    except Exception:  # noqa: BLE001
        settings = {}

    bots = settings.get("telegram_bots") or []
    targets: List[Dict[str, str]] = []
    seen: set = set()
    for b in bots:
        if not b.get("active", True):
            continue
        owner = (b.get("owner_email") or "").strip()
        gmails = [g.strip() for g in (b.get("gmails") or []) if g.strip()]
        for email in ([owner] + gmails):
            if email and email not in seen:
                seen.add(email)
                targets.append({"email": email, "bot": b.get("id", "default")})

    if not targets:
        return {"sent": False, "reason": "no telegram bots configured",
                "targets": []}

    # Route through the local console endpoint (Bearer-authed, same token flow)
    token_file = Path.home() / ".hermes" / "agentic-os" / "token"
    token = token_file.read_text().strip() if token_file.exists() else ""
    console_url = os.environ.get(
        "CONSOLE_PUBLIC_URL",
        os.environ.get("CONSOLE_URL", "http://localhost:18443"),
    )
    payload = json.dumps({
        "message": message[:2000],
        "urgency": urgency,
        "team": team or os.environ.get("AGENT_TEAM", ""),
        "targets": targets,
    }).encode()

    sent, errors = [], []
    for t in targets:
        try:
            req = urllib.request.Request(
                f"{console_url}/api/business/telegram/send",
                data=payload,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {token}",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                result = json.loads(resp.read())
            sent.append({"target": t["email"], "ok": resp.status == 200})
        except Exception as e:  # noqa: BLE001
            errors.append({"target": t["email"], "err": str(e)[:200]})

    return {"sent": bool(sent and all(s["ok"] for s in sent)),
            "delivered": len([s for s in sent if s["ok"]]),
            "failed": len(errors), "details": sent + errors}


# ── Coding via headless CLI (Engineer-only) ───────────────────────────────────

def code_task(prompt: str, cwd: str = ".", agent: Optional[str] = None,
              timeout_seconds: int = 900) -> Dict[str, Any]:
    """Hand a coding subtask to a headless coding agent inside the project folder.

    Uses the same validated pipeline as judge-dispatch: path must stay under ~,
    output is captured and returned for review.

    Sandbox mode: when AGENT_SANDBOX=docker, the task runs inside the
    `sword-agent` container (see docker-compose.agent.yml) instead of on the
    host — the agent works as root in its own machine with no permission
    prompts; only ./agent-workspace is visible from the host.
    """
    from dispatcher import resolve_workspace, _load_business_settings, _cli_for

    resolved = resolve_workspace(cwd)
    chosen = agent or _load_business_settings().get("dispatch_agent_default", "claude")
    argv = _cli_for(chosen)
    if argv is None:
        raise RuntimeError(f"'{chosen}' CLI not found on PATH")

    import subprocess
    import shlex

    sandbox_mode = os.environ.get("AGENT_SANDBOX", "").strip().lower() == "docker"
    effective_timeout = max(30, min(timeout_seconds, 3600))
    if sandbox_mode:
        inner_cmd = shlex.join([*argv, prompt])
        proc = subprocess.run(
            ["docker", "exec", "-w", "/workspace", "sword-agent",
             "bash", "-lc", inner_cmd],
            capture_output=True, text=True, timeout=effective_timeout,
        )
        return {
            "agent": chosen,
            "cwd": "/workspace (docker sandbox: sword-agent)",
            "exit_code": proc.returncode,
            "output": (proc.stdout or "")[-4000:],
            "error": (proc.stderr or "")[-1000:] if proc.returncode else "",
        }

    proc = subprocess.run(
        [*argv, prompt], cwd=resolved, capture_output=True, text=True,
        timeout=effective_timeout,
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
        return [["make", "test"] + extra_args]
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
    # ── Phase 3: cross-team knowledge marketplace ──────────────────────────────
    "publish_insight": {
        "description": (
            "Publish a reusable lesson to the cross-team knowledge marketplace "
            "(office.industry_insights) so OTHER teams can find it. Use after a "
            "notable win, failure post-mortem, or decision with general value. "
            "Knowledge-broker roles only."
        ),
        "args": {
            "topic": {"type": "string", "required": True,
                       "desc": "Short searchable label, e.g. 'postgres migrations'"},
            "insight": {"type": "string", "required": True,
                         "desc": "The lesson itself — concrete, actionable, <= 2000 chars"},
            "team": {"type": "string", "required": False, "default": "main",
                      "desc": "Publishing team id"},
            "author": {"type": "string", "required": False, "default": "",
                        "desc": "Persona/character publishing the insight"},
        },
        # Brokers of institutional knowledge — not a coder's or writer's job.
        "roles": {"CTO", "PM", "Judge", "Analyst", "Researcher"},
        "func": _publish_insight_wrapper,
    },
    "cross_team_search": {
        "description": (
            "Search lessons published by OTHER teams (your own team's entries are "
            "excluded by default). Use before starting work that another team may "
            "have already solved or failed at."
        ),
        "args": {
            "query": {"type": "string", "required": True,
                       "desc": "Keywords, e.g. 'docker pgvector migration rollback'"},
            "exclude_team": {"type": "string", "required": False, "default": None,
                              "desc": "Team id to exclude (defaults to your own)"},
            "limit": {"type": "integer", "required": False, "default": 6},
        },
        # Reading the marketplace is cheap and universally valuable.
        "roles": {"CTO", "PM", "Judge", "Researcher", "Analyst", "Engineer",
                   "Reviewer", "DevOps", "Security", "Writer"},
        "func": _cross_team_search_wrapper,
    },
    "urgent_alert": {
        "description": (
            "Page an owner immediately via their configured Telegram bot. "
            "Send when you need a human decision before proceeding (blocked spec, "
            "conflicting evidence, safety gate). The message goes to all bot owners "
            "and CC'd gmails from config/business/settings.json. Non-coders may use "
            "this; it's a communication tool, not a code tool."
        ),
        "args": {
            "message": {"type": "string", "required": True,
                         "desc": "What to alert about — be specific, under 2000 chars"},
            "receiver_emails": {"type": "array", "items": "string", "required": False,
                                "default": None,
                                "desc": "Override: page only these emails instead of all owners"},
            "team": {"type": "string", "required": False, "default": "",
                      "desc": "Team id being paged (defaults to AGENT_TEAM env)"},
            "urgency": {"type": "string", "required": False, "default": "normal",
                         "desc": "'normal' | 'high' — high priority gets ⚠️ prefix"},
        },
        "roles": {"CTO", "PM", "Judge", "Analyst", "Researcher", "Engineer",
                   "Reviewer", "DevOps", "Security", "Writer"},
        "func": _urgent_alert_wrapper,
    },
    # ── Device / system tooling ─────────────────────────────────────────────────
    "install_raspberry_pi_imager": {
        "description": (
            "Download the latest Raspberry Pi Imager installer for the current "
            "or specified platform. Auto-detects Windows/macOS/Linux and "
            "architecture, picks the right .exe/.dmg/.deb from the official "
            "raspberrypi/rpi-imager GitHub release, and saves it under "
            "~/downloads/ (or the directory you choose). Skips re-download "
            "when the file already exists with matching size."
        ),
        "args": {
            "platform_key": {"type": "string", "required": False, "default": "auto",
                             "desc": "'auto' | 'windows' | 'macos' | 'linux-amd64' "
                                      "| 'linux-arm64' | 'linux-armhf'"},
            "output_dir": {"type": "string", "required": False, "default": None,
                           "desc": "Output directory under ~ (default: tools/downloads/)"},
            "overwrite": {"type": "boolean", "required": False, "default": False,
                          "desc": "Re-download even when the file already exists"},
        },
        # DevOps + Engineer for system installer work, plus CTO and Researcher
        # who sometimes need to flash images for edge devices.
        "roles": {"CTO", "DevOps", "Engineer", "Researcher"},
        "func": install_raspberry_pi_imager,
    },
    "list_raspberry_pi_imager_assets": {
        "description": (
            "List all assets (Windows .exe, macOS .dmg, Linux .deb for each "
            "arch, source tarballs) in the latest Raspberry Pi Imager release. "
            "Use this when you need to know which file to download manually "
            "or check whether a CLI-only build is available."
        ),
        "args": {},
        "roles": {"CTO", "DevOps", "Engineer", "Researcher"},
        "func": list_raspberry_pi_imager_assets,
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
