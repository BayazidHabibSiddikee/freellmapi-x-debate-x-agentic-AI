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
  FREELLM_API_BASE  default http://127.0.0.1:3001/v1 (local FreeLLM proxy)
  FREELLM_MODEL     default auto
  JUDGE_MODEL       optional override for the judge call
  DISPATCH_TIMEOUT  per-subtask timeout seconds (default 900)
  CLAUDE_FLAGS      extra flags for `claude -p`   (e.g. --dangerously-skip-permissions)
  OPENCODE_FLAGS    extra flags for `opencode run`
  JUDGE_MAX_RETRIES max retries for malformed judge output (default 2)
"""

import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from activity import log_event

HOME = Path.home()

FREELLM_BASE = os.environ.get("FREELLM_API_BASE", "http://127.0.0.1:3001/v1")
JUDGE_MODEL = os.environ.get("JUDGE_MODEL", os.environ.get("FREELLM_MODEL", "auto"))
DISPATCH_TIMEOUT = int(os.environ.get("DISPATCH_TIMEOUT", "900"))
JUDGE_MAX_RETRIES = int(os.environ.get("JUDGE_MAX_RETRIES", "2"))
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
- Output ONLY valid JSON — no prose before or after.
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
    """Tolerant JSON extraction (handles ```json fences / leading prose / trailing text)."""
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.DOTALL)
    if fence:
        text = fence.group(1)
    else:
        brace = re.search(r"\{.*\}", text, re.DOTALL)
        if brace:
            text = brace.group(0)
    return json.loads(text)


def _salvage_json(raw: str) -> Dict[str, Any]:
    """Attempt to fix common LLM JSON issues: truncated arrays, missing commas, trailing prose.

    Returns parsed dict or raises on unrecoverable input.
    """
    import json as _json

    # Strip any trailing prose after closing brace (greedy find last })
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if m:
        raw = m.group(0)

    # Try direct parse first
    try:
        return _json.loads(raw)
    except _json.JSONDecodeError:
        pass

    # Fix common issues: missing comma before ] or }, trailing comma
    fixed = re.sub(r",\s*([}\]])", r"\1", raw)  # trailing commas
    fixed = re.sub(r'("\s*):\s*("[^"]*?")\s*,\s*', r'\1\n      \2, ', fixed)  # newline args
    try:
        return _json.loads(fixed)
    except _json.JSONDecodeError:
        pass

    # Last resort: extract just the outermost object via brace counting
    depth = 0
    start = end = 0
    for i, ch in enumerate(raw):
        if ch == '{':
            if depth == 0:
                start = i
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    if start and end > start:
        chunk = raw[start:end]
        try:
            return _json.loads(chunk)
        except _json.JSONDecodeError:
            pass

    raise ValueError(f"unrecoverable JSON (len={len(raw)})")


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

    system = JUDGE_SYSTEM + ws_hint
    user_msg = f"Topic: {topic}\n\nDebate transcript:\n{transcript}"
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user_msg},
    ]

    # Retry loop: up to JUDGE_MAX_RETRIES attempts with salvage on parse failure
    last_error = None
    for attempt in range(1, JUDGE_MAX_RETRIES + 2):  # +1 for initial try
        try:
            raw = _llm(messages, JUDGE_MODEL)
            spec = _parse_json(raw)
            spec = _validate_spec(spec, attempt)
            return spec
        except Exception as e:  # noqa: BLE001
            last_error = str(e)
            if attempt > JUDGE_MAX_RETRIES:
                break
            # Salvage attempt
            try:
                spec = _salvage_json(raw)
                spec = _validate_spec(spec, attempt)
                log_event("judge_salvaged", attempt=attempt, error=last_error[:200])
                return spec
            except Exception:  # noqa: BLE001
                pass
            # Re-prompt the judge with error feedback
            messages.append({
                "role": "assistant", "content": raw[:800] if len(raw) > 800 else raw,
            })
            messages.append({
                "role": "user",
                "content": (
                    f"Your previous output was invalid: {last_error[:200]}. "
                    "Please respond with ONLY valid JSON, no prose."
                ),
            })

    raise ValueError(f"judge failed after {JUDGE_MAX_RETRIES + 1} attempts: {last_error}")


def _validate_spec(spec: Dict[str, Any], attempt: int) -> Dict[str, Any]:
    """Validate and normalize judge output. Raises on fatal issues."""
    if not isinstance(spec, dict):
        raise ValueError("judge did not return a JSON object")
    if not isinstance(spec.get("goal"), str) or not spec["goal"].strip():
        raise ValueError("judge returned no goal")

    raw_tasks = spec.get("subtasks", [])
    if not isinstance(raw_tasks, list) or not raw_tasks:
        raise ValueError("judge returned no subtasks")

    tasks = []
    for i, t in enumerate(raw_tasks):
        if not isinstance(t, dict):
            continue
        agent = str(t.get("agent", "claude")).lower()
        if agent not in {"claude", "opencode"}:
            agent = "claude"
        prompt = str(t.get("prompt", "")).strip()
        # Skip subtasks with empty or absurdly short prompts (< 20 chars)
        if len(prompt) < 20:
            log_event("judge_subtask_skipped", id=t.get("id", f"t{i}"),
                       reason="empty-or-too-short-prompt")
            continue
        tasks.append({
            "id": str(t.get("id", f"t{i+1}")),
            "title": str(t.get("title", f"Subtask {i+1}")).strip(),
            "prompt": prompt,
            "agent": agent,
            "cwd": str(t.get("cwd", "")).strip(),
            "status": "pending",
        })

    if not tasks:
        raise ValueError("judge returned no valid subtasks after filtering")
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
    settings = _load_business_settings()
    agent = task.get("agent") or settings.get("dispatch_agent_default", "claude")

    # Respect file-write permission setting
    allow_writes = settings.get("allow_file_writes", False)
    if not allow_writes and agent == "claude":
        # Strip --dangerously-skip-permissions if present and add read-only mode
        safe_flags = [f for f in CLAUDE_FLAGS if "--dangerously-skip-permissions" not in f]
        argv = ["claude", "-p", *safe_flags]
    else:
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

    timeout = int(settings.get("dispatch_timeout_seconds", DISPATCH_TIMEOUT))
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


def verify_results(results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Post-dispatch quality gate: flag subtasks whose output looks suspicious.

    Returns results with an added "_flags" field listing concerns.
    """
    for r in results:
        flags = []
        if r.get("status") == "failed":
            err = (r.get("error") or "").lower()
            if "permission" in err or "denied" in err:
                flags.append("permission-denied: enable allow_file_writes in settings")
            elif "timeout" in err or "exceeded" in err:
                flags.append("timeout: consider breaking into smaller subtasks")
        elif r.get("status") == "done":
            output = (r.get("output") or "").lower()
            if not output.strip():
                flags.append("empty-output: agent produced no visible result")
            if "error:" in output and "Traceback" in output:
                flags.append("runtime-error-in-output: review and possibly re-dispatch")
            if "i cannot" in output or "i'm sorry" in output:
                flags.append("refusal-detected: agent declined the task")
        r["_flags"] = flags
    return results


def dispatch_spec(spec: Dict[str, Any],
                  only: Optional[List[str]] = None) -> Dict[str, Any]:
    """Dispatch all (or selected) subtasks sequentially with retry on failure."""
    results = []
    for task in spec.get("subtasks", []):
        if only and task["id"] not in only:
            continue

        # Execute with one retry on failure
        result = dispatch_subtask(task)
        if result["status"] in {"failed", "timeout"} and result.get("_retried") is not True:
            result = {**result, "_retried": True}
            log_event("dispatch_retry", id=task.get("id"))
            retry_result = dispatch_subtask(result)
            if retry_result["status"] in {"failed", "timeout"}:
                retry_result["_retry_failed"] = True
            result = retry_result

        results.append(result)

    # Post-dispatch verification gate
    results = verify_results(results)

    done = sum(1 for r in results if r["status"] == "done")
    flagged = sum(1 for r in results if r.get("_flags"))
    return {
        "goal": spec.get("goal"),
        "results": results,
        "summary": {
            "total": len(results),
            "done": done,
            "failed": sum(1 for r in results if r["status"] in {"failed", "timeout"}),
            "flagged": flagged,
            "needs_attention": flagged > 0,
        },
    }
