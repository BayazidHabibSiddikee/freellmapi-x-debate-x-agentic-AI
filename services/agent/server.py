"""
services/agent/server.py — tool execution API for the Business team (port 5090).

Endpoints:
  GET  /tools?role=Researcher   → tools available to a role
  POST /execute                 → {tool, args, role} — validated + executed
  GET  /report                  → registry status / import errors
  GET  /health
"""

import asyncio
from typing import Any, Dict, Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from tools_registry import execute, list_tools, report, ToolError
from dispatcher import judge_spec, dispatch_spec
# Local jobs.py provides the dispatch queue (named `jobs`, not `queue`, to keep
# the stdlib `queue` importable for ThreadPoolExecutor internals).
from jobs import enqueue, cancel, list_jobs, status as queue_status
from activity import log_event
import db

app = FastAPI(title="Business Agent Tools", version="1.0")

DB_BACKEND = db.init_schema()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ExecuteRequest(BaseModel):
    tool: str
    args: Dict[str, Any] = {}
    role: Optional[str] = None
    allowed: list = []   # extra per-person tool grants from persona file


@app.get("/health")
async def health():
    return {"status": "operational", "port": 5090}


@app.get("/tools")
async def tools(role: Optional[str] = None):
    return {"tools": list_tools(role), "role": role}


@app.post("/execute")
async def run_tool(req: ExecuteRequest):
    try:
        result = await asyncio.to_thread(execute, req.tool, req.args, req.role, req.allowed)
        log_event("tool", tool=req.tool, role=req.role, ok=True)
        return {"ok": True, "tool": req.tool, "role": req.role, "result": result}
    except ToolError as e:
        log_event("tool", tool=req.tool, role=req.role, ok=False, error=str(e))
        return {"ok": False, "tool": req.tool, "error": str(e), "kind": "validation"}
    except Exception as e:  # noqa: BLE001 — surface remote/tool failures to caller
        log_event("tool", tool=req.tool, role=req.role, ok=False, error=str(e)[:300])
        return {"ok": False, "tool": req.tool, "error": str(e)[:500], "kind": "execution"}


@app.get("/report")
async def get_report():
    return report()


# ── Judge → dispatch ──────────────────────────────────────────────────────────

class JudgeRequest(BaseModel):
    topic: str
    history: list = []
    workspaces: dict = {}   # role -> workspace path hints


class DispatchRequest(BaseModel):
    spec: dict
    only: list = []   # subtask ids; empty = all


@app.post("/judge")
async def judge(req: JudgeRequest):
    try:
        spec = await asyncio.to_thread(judge_spec, req.topic, req.history, req.workspaces)
        log_event("judge", topic=req.topic[:200],
                  subtasks=[t["id"] for t in spec.get("subtasks", [])])
        return {"ok": True, "spec": spec}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e)[:500]}


@app.post("/dispatch")
async def dispatch(req: DispatchRequest):
    try:
        result = await asyncio.to_thread(dispatch_spec, req.spec, req.only or None)
        log_event("dispatch", goal=str(req.spec.get("goal", ""))[:200],
                  summary=result.get("summary"))
        return {"ok": True, **result}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e)[:500]}


# ── Jobs / parallel dispatch queue (multi-project) ───────────────────────────

class JobCreateRequest(BaseModel):
    spec: dict
    project: dict = {}          # {id, name, folder} — optional folder pin
    target_repo: str = ""       # explicit folder for every subtask


@app.post("/jobs")
async def jobs_create(req: JobCreateRequest):
    """Enqueue a spec and run its subtasks across the parallel pool."""
    try:
        spec = req.spec
        if not isinstance(spec.get("subtasks"), list) or not spec["subtasks"]:
            return {"ok": False, "error": "spec with subtasks is required"}
        project = req.project or None
        target = req.target_repo.strip() or None
        job = await asyncio.to_thread(enqueue, project, spec, target)
        log_event("jobs_create", job=job.get("id"),
                  project=(project or {}).get("name"), subtasks=job.get("subtasks"))
        return {"ok": True, "job": job}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e)[:500]}


@app.get("/jobs")
async def jobs_list(limit: int = 30):
    try:
        return {"ok": True, "jobs": list_jobs(min(limit, 100))}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e)[:500]}


@app.get("/jobs/{job_id}")
async def jobs_detail(job_id: str):
    job = db.get_job(job_id)
    if not job:
        return {"ok": False, "error": "job not found"}
    return {"ok": True, "job": job}


@app.post("/jobs/{job_id}/cancel")
async def jobs_cancel(job_id: str):
    ok = await asyncio.to_thread(cancel, job_id)
    if not ok:
        return {"ok": False, "error": "job not found"}
    return {"ok": True}


@app.get("/queue/status")
async def queue_status_endpoint():
    return {"ok": True, "queue": queue_status()}



# ── Office: persistent rooms, messages, persona memory ───────────────────────

class RoomCreate(BaseModel):
    id: str
    kind: str = "persona"       # persona | boardroom | debate
    title: str
    meta: dict = {}

class MessageIn(BaseModel):
    role: str                    # user | persona
    speaker: str
    content: str
    character_id: Optional[str] = None

class MemoryIn(BaseModel):
    kind: str = "fact"           # job | teammate | fact | preference
    content: str
    subject_id: Optional[str] = None   # who this memory is ABOUT


@app.get("/db/status")
async def db_status():
    return {**db.status(), "requested_backend": DB_BACKEND}


@app.get("/rooms")
async def rooms():
    return {"rooms": db.list_rooms()}


@app.post("/rooms")
async def create_room(req: RoomCreate):
    db.ensure_room(req.id, req.kind, req.title, req.meta)
    return {"ok": True}


@app.delete("/rooms/{room_id}")
async def delete_room(room_id: str):
    with db.conn() as c:
        cur = c.cursor()
        pfx = "office." if "psycopg" in type(c).__module__ else ""
        cur.execute(f"DELETE FROM {pfx}rooms WHERE id = %s", (room_id,))
        deleted = cur.rowcount > 0
    return {"ok": bool(deleted)}


@app.get("/rooms/{room_id}/messages")
async def room_messages(room_id: str, limit: int = 200):
    return {"messages": db.get_messages(room_id, min(limit, 500))}


@app.post("/rooms/{room_id}/messages")
async def add_message(room_id: str, req: MessageIn):
    db.add_message(room_id, req.role, req.speaker, req.content, req.character_id)
    log_event("office_message", room=room_id, role=req.role)
    return {"ok": True}


@app.get("/persona/{character_id}/memory")
async def persona_memory(character_id: str, limit: int = 20):
    return {"memories": db.recall_about(character_id, limit)}


@app.post("/persona/{character_id}/memory")
async def remember_for(character_id: str, req: MemoryIn):
    db.remember(character_id, req.kind, req.content, subject_id=req.subject_id)
    return {"ok": True}


@app.get("/persona/{character_id}/memory/context")
async def persona_memory_context(character_id: str, limit: int = 6,
                                 about: str = ""):
    subjects = [s.strip() for s in about.split(",") if s.strip()] or None
    return {"context": db.memory_context(character_id, limit, subjects)}


# ── Teams ─────────────────────────────────────────────────────────────────────

class TeamIn(BaseModel):
    id: Optional[str] = None
    name: str
    charter: str = ""


@app.get("/teams")
async def teams_list():
    return {"teams": db.list_teams()}


@app.post("/teams")
async def teams_create(req: TeamIn):
    import uuid
    team_id = req.id or f"team_{uuid.uuid4().hex[:8]}"
    return {"ok": True, "team": db.create_team(team_id, req.name, req.charter)}


@app.delete("/teams/{team_id}")
async def teams_delete(team_id: str):
    return {"ok": db.delete_team(team_id)}

if __name__ == "__main__":
    import argparse
    import uvicorn

    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=5090)
    args = parser.parse_args()
    uvicorn.run(app, host="127.0.0.1", port=args.port)
