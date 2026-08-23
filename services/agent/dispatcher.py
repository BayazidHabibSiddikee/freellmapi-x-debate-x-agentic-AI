"""
services/agent/dispatcher.py — debate verdict → structured spec → coding-agent dispatch.

Flow:
  1. The team debates in the Business session (console /business).
  2. `judge_spec()` asks the Judge character to distill the transcript into a
     JSON task spec: goal + subtasks, each tagged with a target agent
     ("claude" | "opencode") and working directory.
  3. `dispatch_spec()` runs each subtask through the headless coding-agent CLI
     (`claude -p` / `opencode run`) in its target repo path and captures output.

Env:
  FREELLM_API_BASE  default http://localhost:3001/v1 (local FreeLLM proxy)
  FREELLM_MODEL     default auto
  JUDGE_MODEL       optional override for the judge call
  DISPATCH_TIMEOUT  per-subtask timeout seconds (default 900)
  CLAUDE_FLAGS      extra flags for `claude -p`   (e.g. --dangerously-skip-permissions)
  OPENCODE_FLAGS    extra flags for `opencode run`
"""

import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from activity import log_event

HOME = Path.home()

FREELLM_BASE = os.environ.get("FREELLM_API_BASE", "http://localhost:3001/v1")
JUDGE_MODEL = os.environ.get("JUDGE_MODEL", os.environ.get("FREELLM_MODEL", "gemini-3.5-flash"))
DISPATCH_TIMEOUT = int(os.environ.get("DISPATCH_TIMEOUT", "900"))
CLAUDE_FLAGS = os.environ.get("CLAUDE_FLAGS", "").split()
OPENCODE_FLAGS = os.environ.get("OPENCODE_FLAGS", "").split()


def _freellm_key() -> str:
    """Env override, else read the local proxy's unified key from its SQLite DB."""
    if os.environ.get("FREELLM_API_KEY"):
        return os.environ["FREELLM_API_KEY"]
    try:
        import sqlite3
        db_path = Path(__file__).resolve().parents[2] / "server" / "data" / "freeapi.db"
        con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        row = con.execute(
            "SELECT value FROM settings WHERE key = 'unified_api_key'"
        ).fetchone()
        con.close()
        if row and row[0]:
            return row[0]
    except Exception:  # noqa: BLE001 — fall through to default
        pass
    return "not-needed"

JUDGE_SYSTEM = """You are the impartial technical Judge of an AI team. You receive a
debate transcript about a work topic and must produce a structured task spec for
coding agents to execute.

Respond with ONLY a JSON object (no markdown fences, no commentary) shaped exactly:

{
  "goal": "one-sentence statement of what must be accomplished",
  "decisions": ["key decisions made in the debate"],
  "subtasks": [
    {
      "id": "t1",
      "title": "short title",
      "prompt": "precise self-contained instruction for the coding agent",
      "agent": "claude",
      "cwd": "/absolute/path/to/repo"
    }
  ]
}

Rules:
- 1-6 subtasks. Each prompt must be fully self-contained (the agent sees nothing else).
- "agent" is either "claude" or "opencode".
- "cwd" MUST be an existing absolute directory path mentioned in or obvious from the debate.
"""


# ── LLM ───────────────────────────────────────────────────────────────────────

def _llm(messages: List[Dict[str, str]], model: str,
         timeout: int = 180) -> str:
    import requests

    res = requests.post(
        f"{FREELLM_BASE}/chat/completions",
        headers={"Authorization": f"Bearer {_freellm_key()}",
                 "Content-Type": "application/json"},
        json={"model": model, "messages": messages,
              "temperature": 0.2, "max_tokens": 1500},
        timeout=timeout,
    )
    res.raise_for_status()
    return res.json()["choices"][0]["message"]["content"]


def _parse_json(text: str) -> Dict[str, Any]:
    """Tolerant JSON extraction (handles ```json fences / leading prose)."""
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.DOTALL)
    if fence:
        text = fence.group(1)
    else:
        brace = re.search(r"\{.*\}", text, re.DOTALL)
        if brace:
            text = brace.group(0)
    return json.loads(text)


# ── Judge ─────────────────────────────────────────────────────────────────────

def judge_spec(topic: str, history: List[Dict[str, str]],
               workspaces: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    transcript = "\n".join(f"{t['speaker']}: {t['text']}" for t in history[-20:])
    ws_hint = ""
    if workspaces:
        ws_hint = (
            "\n\nKnown team workspace directories (prefer these for subtask \"cwd\"):\n"
            + "\n".join(f"- {k}: {v}" for k, v in workspaces.items() if v)
        )
    raw = _llm(
        [
            {"role": "system", "content": JUDGE_SYSTEM + ws_hint},
            {"role": "user",
             "content": f"Topic: {topic}\n\nDebate transcript:\n{transcript}"},
        ],
        JUDGE_MODEL,
    )
    spec = _parse_json(raw)

    # Validate / normalize
    if not isinstance(spec.get("goal"), str) or not spec["goal"]:
        raise ValueError("judge returned no goal")
    tasks = []
    for i, t in enumerate(spec.get("subtasks", []), 1):
        agent = str(t.get("agent", "claude")).lower()
        if agent not in {"claude", "opencode"}:
            agent = "claude"
        tasks.append({
            "id": str(t.get("id", f"t{i}")),
            "title": str(t.get("title", f"Subtask {i}")),
            "prompt": str(t.get("prompt", "")).strip(),
            "agent": agent,
            "cwd": str(t.get("cwd", "")).strip(),
            "status": "pending",
        })
    if not tasks:
        raise ValueError("judge returned no subtasks")
    spec["subtasks"] = tasks
    return spec


# ── Dispatch ──────────────────────────────────────────────────────────────────

def _cli_for(agent: str) -> Optional[List[str]]:
    import shutil

    if agent == "claude":
        exe = shutil.which("claude")
        return [exe, "-p", *CLAUDE_FLAGS] if exe else None
    if agent == "opencode":
        exe = shutil.which("opencode")
        return [exe, "run", *OPENCODE_FLAGS] if exe else None
    return None


def _load_business_settings() -> Dict[str, Any]:
    """Read config/business/settings.json (written by the console)."""
    path = Path(__file__).resolve().parents[2] / "config" / "business" / "settings.json"
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:  # noqa: BLE001
        return {}


def resolve_workspace(path: str) -> str:
    """Expand ~ and enforce the path stays under $HOME."""
    expanded = Path(os.path.expanduser(path)).resolve()
    if expanded != HOME and HOME not in expanded.parents:
        raise ValueError(f"workspace must be under {HOME}")
    return str(expanded)


def dispatch_subtask(task: Dict[str, Any]) -> Dict[str, Any]:
    agent = task.get("agent") or _load_business_settings().get(
        "dispatch_agent_default", "claude"
    )
    argv = _cli_for(agent)
    if argv is None:
        return {**task, "status": "failed",
                "error": f"'{agent}' CLI not found on PATH"}

    try:
        raw_cwd = task.get("cwd") or "."
        cwd = resolve_workspace(raw_cwd)
    except ValueError as e:
        return {**task, "status": "failed", "error": str(e)}
    if not Path(cwd).is_dir():
        return {**task, "status": "failed", "error": f"cwd does not exist: {cwd}"}

    timeout = int(_load_business_settings().get("dispatch_timeout_seconds", DISPATCH_TIMEOUT))
    log_event("dispatch_task", id=task.get("id"), agent=agent, cwd=cwd)
    try:
        proc = subprocess.run(
            [*argv, task["prompt"]],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        ok = proc.returncode == 0
        result = {
            **task,
            "status": "done" if ok else "failed",
            "exit_code": proc.returncode,
            "output": (proc.stdout or "")[-4000:],
            "error": (proc.stderr or "")[-1000:] if not ok else "",
        }
        log_event("dispatch_task", id=task.get("id"), status=result["status"])
        return result
    except subprocess.TimeoutExpired:
        log_event("dispatch_task", id=task.get("id"), status="timeout")
        return {**task, "status": "timeout",
                "error": f"exceeded {timeout}s"}
    except Exception as e:  # noqa: BLE001
        log_event("dispatch_task", id=task.get("id"), status="failed", error=str(e)[:300])
        return {**task, "status": "failed", "error": str(e)[:500]}


def dispatch_spec(spec: Dict[str, Any],
                  only: Optional[List[str]] = None) -> Dict[str, Any]:
    """Dispatch all (or selected) subtasks sequentially."""
    results = []
    for task in spec.get("subtasks", []):
        if only and task["id"] not in only:
            continue
        results.append(dispatch_subtask(task))
    return {
        "goal": spec.get("goal"),
        "results": results,
        "summary": {
            "total": len(results),
            "done": sum(1 for r in results if r["status"] == "done"),
            "failed": sum(1 for r in results if r["status"] in {"failed", "timeout"}),
        },
    }
