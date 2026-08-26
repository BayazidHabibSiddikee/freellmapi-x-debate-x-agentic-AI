"""
services/agent/jobs.py — Phase: multi-project, parallel dispatch queue.

Turn a judge spec into a *JOB*. Its subtasks run CONCURRENTLY across any number
of target folders, each through the Phase-4 review loop
(subtask run -> diff capture -> team review -> auto-retry on rejection).

Design:
  - A background ThreadPoolExecutor (DISPATCH_MAX_PARALLEL workers) runs
    subtasks in parallel. Each subtask is persisted to db.jobs/dispatch_runs so
    the console dashboard shows per-repo progress.
  - db.py opens a fresh connection per call and the LLM layer is stateless,
    so parallel workers are safe; a small lock guards job bookkeeping.
  - Cancellation is cooperative: not-yet-started subtasks are marked cancelled;
    a running subprocess finishes but the job is flagged cancelled.

Env:
  DISPATCH_MAX_PARALLEL  max coding agents running at once (default 2)
"""

import os
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional

from activity import log_event
import db
from dispatcher import _run_task_with_loop, _load_business_settings

MAX_PARALLEL = max(1, int(os.environ.get("DISPATCH_MAX_PARALLEL", "2")))
_executor = ThreadPoolExecutor(max_workers=MAX_PARALLEL)
_lock = threading.Lock()
_active: Dict[str, int] = {}


def enqueue(project: Optional[Dict[str, Any]],
            spec: Dict[str, Any],
            target_repo: Optional[str] = None) -> Dict[str, Any]:
    """Create a job and start its subtasks across the queue pool.

    `project` pins each subtask's folder when the subtask didn't specify one;
    `target_repo` is an explicit folder override for every subtask.
    Returns job metadata (status='running' once dispatched).
    """
    job = db.create_job(project, spec)
    job_id = job["id"]
    tasks = spec.get("subtasks", [])
    task_infos: List[tuple] = []
    for t in tasks:
        cwd = (t.get("cwd") or "").strip() or target_repo or (
            (project or {}).get("folder") or "")
        task = {**t, "cwd": cwd} if cwd else t
        run_id = db.add_dispatch_run(job_id, task)
        task_infos.append((run_id, task))

    db.update_job(job_id, {"status": "running"})
    with _lock:
        _active[job_id] = len(task_infos)
    if not task_infos:
        db.update_job(job_id, {"status": "done", "summary": {"total": 0, "done": 0}})
        return {**job, "status": "done", "subtasks": 0}

    for run_id, task in task_infos:
        _executor.submit(_run_one, job_id, run_id, task, spec)
    log_event("job_started", job=job_id, project=(project or {}).get("name"),
              subtasks=len(task_infos), parallel=MAX_PARALLEL)
    return {**job, "status": "running", "subtasks": len(task_infos)}


def cancel(job_id: str) -> bool:
    """Mark a job cancelled; queued subtasks are skipped, running ones drop."""
    job = db.get_job(job_id)
    if not job:
        return False
    if job.get("status") in ("done", "cancelled"):
        return True
    db.set_job_status(job_id, "cancelled")
    log_event("job_cancelled", job=job_id)
    return True


def list_jobs(limit: int = 30) -> List[Dict[str, Any]]:
    return db.list_jobs(limit)


def status() -> Dict[str, Any]:
    return {"parallel": MAX_PARALLEL, "active": len(_active), "jobs": db.list_jobs(10)}


def _load_settings() -> Dict[str, Any]:
    try:
        return _load_business_settings()
    except Exception:  # noqa: BLE001
        return {}


def _run_one(job_id: str, run_id: int, task: Dict[str, Any], spec: Dict[str, Any]) -> None:
    """Execute one subtask (with the review loop) and persist its result."""
    try:
        job = db.get_job(job_id)
        if not job or job.get("status") == "cancelled":
            db.update_dispatch_run(run_id, {"status": "cancelled",
                                            "error": "cancelled before start"})
            return
        db.update_dispatch_run(run_id, {"status": "running"})
        settings = _load_settings()
        max_retries = max(0, int(settings.get("dispatch_max_retries", 1)))
        review_enabled = bool(settings.get("team_review", True))
        result = _run_task_with_loop(spec, task, settings, max_retries, review_enabled)
        db.update_dispatch_run(run_id, {
            "status": result.get("status", "failed"),
            "output": result.get("output", ""),
            "error": (result.get("error") or "")[:1000],
            "diff": result.get("diff", {}),
            "review": result.get("review", {}),
            "attempts": result.get("attempts", 1),
        })
    except Exception as e:  # noqa: BLE001 — never strand a job row
        log_event("dispatch_run_error", job=job_id, run=run_id, error=str(e)[:300])
        try:
            db.update_dispatch_run(run_id, {"status": "failed", "error": str(e)[:1000]})
        except Exception:  # noqa: BLE001
            pass
    finally:
        with _lock:
            _active[job_id] = _active.get(job_id, 0) - 1
            if _active[job_id] <= 0:
                _finalize(job_id)


def _finalize(job_id: str) -> None:
    """Compute the job summary once every subtask has finished."""
    try:
        job = db.get_job(job_id)
        if not job:
            return
        runs = job.get("runs") or []
        total = len(runs)
        done = sum(1 for r in runs if r["status"] == "done")
        rejected = sum(1 for r in runs if r["status"] == "rejected")
        failed = sum(1 for r in runs if r["status"] in ("failed", "timeout"))
        cancelled = sum(1 for r in runs if r["status"] == "cancelled")
        needs_attention = rejected > 0 or failed > 0 or cancelled > 0
        status = "cancelled" if job.get("status") == "cancelled" else "done"
        db.update_job(job_id, {
            "status": status,
            "summary": {
                "total": total, "done": done, "rejected": rejected,
                "failed": failed, "cancelled": cancelled,
                "needs_attention": needs_attention,
            },
        })
        log_event("job_finished", job=job_id, status=status,
                  summary={"total": total, "done": done, "rejected": rejected,
                           "failed": failed})
    except Exception as e:  # noqa: BLE001 — summary is best-effort
        log_event("job_finalize_error", job=job_id, error=str(e)[:200])