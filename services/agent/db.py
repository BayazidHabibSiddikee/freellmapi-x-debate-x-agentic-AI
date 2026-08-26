"""
services/agent/db.py — PostgreSQL persistence for the SwordOffice team.

One database (`swordoffice`), schema `office`:
  rooms            — chat sections: one per persona (1-on-1 office), plus
                     boardroom (project meetings) and debate rooms
  messages         — every message in every room, full history
  persona_memory   — what each persona LEARNS: how teammates think, what their
                     jobs are, facts from conversations; injected into prompts

Design note: 46 personas do NOT get 46 databases. They get 46 *rooms* (rows)
and per-persona memory rows inside one governed schema. One connection pool,
one backup, consistent tooling.

Env: SWORDOFFICE_PG (default postgresql://sword:swordoffice@localhost:5432/swordoffice)
Falls back to SQLite (<root>/server/data/swordoffice.db) if PG is unreachable,
so the team never hard-fails when the container is down.
"""

import json
import os
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

PG_DSN = os.environ.get(
    "SWORDOFFICE_PG",
    "postgresql://sword:swordoffice@localhost:5432/swordoffice",
)
SQLITE_FALLBACK = Path(__file__).resolve().parents[2] / "server" / "data" / "swordoffice.db"

_pool_pg = True


def _pg_connect():
    import psycopg
    return psycopg.connect(PG_DSN, autocommit=True)


@contextmanager
def conn() -> Iterator[Any]:
    """Yield a DB connection — PostgreSQL, or SQLite fallback."""
    global _pool_pg
    if _pool_pg:
        try:
            c = _pg_connect()
        except Exception as e:  # noqa: BLE001
            print(f"[db] postgres unavailable ({e}) — falling back to sqlite")
            _pool_pg = False
        else:
            try:
                yield c
            finally:
                c.close()
            return
    SQLITE_FALLBACK.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(SQLITE_FALLBACK, timeout=30)
    try:
        yield c
    except Exception:  # noqa: BLE001
        c.rollback()
        raise
    else:
        c.commit()
    finally:
        c.close()


def init_schema() -> str:
    """Create tables; returns which backend was used ('postgres'|'sqlite')."""
    with conn() as c:
        backend = type(c).__module__
        if "psycopg" in backend:
            cur = c.cursor()
            cur.execute("CREATE SCHEMA IF NOT EXISTS office")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS office.teams (
                    id      TEXT PRIMARY KEY,
                    name    TEXT NOT NULL,
                    charter TEXT DEFAULT ''
                )""")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS office.rooms (
                    id         TEXT PRIMARY KEY,
                    kind       TEXT NOT NULL,          -- persona | boardroom | debate
                    title      TEXT NOT NULL,
                    team_id    TEXT REFERENCES office.teams(id),
                    meta       JSONB DEFAULT '{}',
                    created_at TIMESTAMPTZ DEFAULT now()
                )""")
            cur.execute("ALTER TABLE office.rooms ADD COLUMN IF NOT EXISTS team_id TEXT")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS office.messages (
                    id           BIGSERIAL PRIMARY KEY,
                    room_id      TEXT NOT NULL REFERENCES office.rooms(id) ON DELETE CASCADE,
                    role         TEXT NOT NULL,        -- user | persona | system
                    speaker      TEXT NOT NULL,
                    character_id TEXT,
                    content      TEXT NOT NULL,
                    meta         JSONB DEFAULT '{}',
                    ts           TIMESTAMPTZ DEFAULT now()
                )""")
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_messages_room ON office.messages(room_id, ts)
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS office.persona_memory (
                    id           BIGSERIAL PRIMARY KEY,
                    character_id TEXT NOT NULL,
                    kind         TEXT NOT NULL,        -- job | teammate | fact | preference
                    content      TEXT NOT NULL,
                    source_room  TEXT,
                    ts           TIMESTAMPTZ DEFAULT now()
                )""")
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_memory_char ON office.persona_memory(character_id, ts DESC)
            """)
            cur.execute("ALTER TABLE office.persona_memory ADD COLUMN IF NOT EXISTS subject_id TEXT")
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_memory_subject ON office.persona_memory(subject_id, ts DESC)
            """)
            return "postgres"

        # SQLite fallback schema (same shape, relaxed types)
        cur = c.cursor()
        cur.executescript("""
            CREATE TABLE IF NOT EXISTS teams (
                id TEXT PRIMARY KEY, name TEXT NOT NULL, charter TEXT DEFAULT '');
            CREATE TABLE IF NOT EXISTS rooms (
                id TEXT PRIMARY KEY, kind TEXT NOT NULL, title TEXT NOT NULL,
                team_id TEXT, meta TEXT DEFAULT '{}', created_at TEXT DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                room_id TEXT NOT NULL, role TEXT NOT NULL, speaker TEXT NOT NULL,
                character_id TEXT, content TEXT NOT NULL, meta TEXT DEFAULT '{}',
                ts TEXT DEFAULT CURRENT_TIMESTAMP);
            CREATE INDEX IF NOT EXISTS idx_messages_room ON messages(room_id, ts);
            CREATE TABLE IF NOT EXISTS persona_memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                character_id TEXT NOT NULL, kind TEXT NOT NULL, content TEXT NOT NULL,
                subject_id TEXT, source_room TEXT, ts TEXT DEFAULT CURRENT_TIMESTAMP);
            CREATE INDEX IF NOT EXISTS idx_memory_char ON persona_memory(character_id, ts DESC);
            CREATE INDEX IF NOT EXISTS idx_memory_subject ON persona_memory(subject_id, ts DESC);
        """)
        return "sqlite"


# ── Rooms ─────────────────────────────────────────────────────────────────────

def ensure_room(room_id: str, kind: str, title: str, meta: Optional[Dict] = None) -> None:
    with conn() as c:
        cur = c.cursor()
        if "psycopg" in type(c).__module__:
            cur.execute(
                "INSERT INTO office.rooms (id, kind, title, meta) VALUES (%s,%s,%s,%s) "
                "ON CONFLICT (id) DO NOTHING",
                (room_id, kind, title, json.dumps(meta or {})),
            )
        else:
            cur.execute(
                "INSERT OR IGNORE INTO rooms (id, kind, title, meta) VALUES (%s,%s,%s,%s)",
                (room_id, kind, title, json.dumps(meta or {})),
            )


def list_rooms() -> List[Dict[str, Any]]:
    q_last = ("SELECT content FROM messages WHERE room_id = r.id ORDER BY ts DESC LIMIT 1"
              if True else "")
    with conn() as c:
        cur = c.cursor()
        is_pg = "psycopg" in type(c).__module__
        tbl_rooms = "office.rooms" if is_pg else "rooms"
        tbl_msgs = "office.messages" if is_pg else "messages"
        cur.execute(
            f"SELECT r.id, r.kind, r.title, "
            f"(SELECT COUNT(*) FROM {tbl_msgs} m WHERE m.room_id = r.id), "
            f"(SELECT content FROM {tbl_msgs} m WHERE m.room_id = r.id ORDER BY ts DESC LIMIT 1) "
            f"FROM {tbl_rooms} r ORDER BY r.title"
        )
        out = []
        for row in cur.fetchall():
            out.append({"id": row[0], "kind": row[1], "title": row[2],
                        "message_count": row[3], "last_message": (row[4] or "")[:120]})
        return out


def add_message(room_id: str, role: str, speaker: str, content: str,
                character_id: Optional[str] = None,
                meta: Optional[Dict] = None) -> None:
    with conn() as c:
        cur = c.cursor()
        is_pg = "psycopg" in type(c).__module__
        tbl = "office.messages" if is_pg else "messages"
        meta_s = json.dumps(meta or {})
        if is_pg:
            cur.execute(
                f"INSERT INTO {tbl} (room_id, role, speaker, character_id, content, meta) "
                "VALUES (%s,%s,%s,%s,%s,%s)",
                (room_id, role, speaker, character_id, content, meta_s),
            )
        else:
            cur.execute(
                f"INSERT INTO {tbl} (room_id, role, speaker, character_id, content, meta) "
                "VALUES (%s,%s,%s,%s,%s,%s)",
                (room_id, role, speaker, character_id, content, meta_s),
            )


def get_messages(room_id: str, limit: int = 200) -> List[Dict[str, Any]]:
    with conn() as c:
        cur = c.cursor()
        is_pg = "psycopg" in type(c).__module__
        tbl = "office.messages" if is_pg else "messages"
        cur.execute(
            f"SELECT role, speaker, character_id, content, ts FROM {tbl} "
            f"WHERE room_id = %s ORDER BY ts DESC LIMIT %s",
            (room_id, limit),
        )
        rows = cur.fetchall()
    return [{"role": r[0], "speaker": r[1], "character_id": r[2],
             "content": r[3], "ts": str(r[4])} for r in reversed(rows)]



# ── Teams (the "industry" layer) ──────────────────────────────────────────────

def create_team(team_id: str, name: str, charter: str = "") -> Dict[str, Any]:
    with conn() as c:
        cur = c.cursor()
        is_pg = "psycopg" in type(c).__module__
        tbl = "office.teams" if is_pg else "teams"
        if is_pg:
            cur.execute(
                f"INSERT INTO {tbl} (id, name, charter) VALUES (%s,%s,%s) "
                "ON CONFLICT (id) DO UPDATE SET name=%s, charter=%s",
                (team_id, name, charter, name, charter),
            )
        else:
            cur.execute(
                f"INSERT INTO {tbl} (id, name, charter) VALUES (%s,%s,%s) "
                "ON CONFLICT(id) DO UPDATE SET name=excluded.name, charter=excluded.charter",
                (team_id, name, charter),
            )
    return {"id": team_id, "name": name, "charter": charter}


def list_teams() -> List[Dict[str, Any]]:
    with conn() as c:
        cur = c.cursor()
        is_pg = "psycopg" in type(c).__module__
        tbl_t = "office.teams" if is_pg else "teams"
        tbl_r = "office.rooms" if is_pg else "rooms"
        cur.execute(
            f"SELECT t.id, t.name, t.charter, "
            f"(SELECT COUNT(*) FROM {tbl_r} r WHERE r.team_id = t.id) FROM {tbl_t} t ORDER BY t.name"
        )
        return [{"id": r[0], "name": r[1], "charter": r[2], "rooms": r[3]} for r in cur.fetchall()]


def delete_team(team_id: str) -> bool:
    with conn() as c:
        cur = c.cursor()
        is_pg = "psycopg" in type(c).__module__
        tbl = "office.teams" if is_pg else "teams"
        cur.execute(f"DELETE FROM {tbl} WHERE id = %s", (team_id,))
        return cur.rowcount > 0


# ── Dispatch queue (multi-project / parallel jobs) ────────────────────────────
#
# A "job" is a whole judge spec (goal + subtasks) that can target ONE or MORE
# projects/folders. Subtasks are persisted as individual rows so the console
# dashboard can show per-repo progress while a pool of worker threads runs them.

JOB_STATUSES = ("pending", "running", "done", "failed", "cancelled")


def _ensure_jobs(c: Any) -> None:
    if "psycopg" in type(c).__module__:
        cur = c.cursor()
        cur.execute("CREATE SCHEMA IF NOT EXISTS office")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS office.jobs (
                id           TEXT PRIMARY KEY,
                project_id   TEXT,
                project_name TEXT,
                goal         TEXT NOT NULL,
                status       TEXT NOT NULL DEFAULT 'pending',
                spec         JSONB DEFAULT '{}',
                summary      JSONB DEFAULT '{}',
                created_at   TIMESTAMPTZ DEFAULT now(),
                updated_at   TIMESTAMPTZ DEFAULT now()
            )""")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS office.dispatch_runs (
                id         BIGSERIAL PRIMARY KEY,
                job_id     TEXT NOT NULL REFERENCES office.jobs(id) ON DELETE CASCADE,
                task_id    TEXT NOT NULL,
                title      TEXT DEFAULT '',
                cwd        TEXT DEFAULT '',
                agent      TEXT DEFAULT 'claude',
                status     TEXT NOT NULL DEFAULT 'pending',
                output     TEXT DEFAULT '',
                diff       JSONB DEFAULT '{}',
                review     JSONB DEFAULT '{}',
                error      TEXT DEFAULT '',
                attempts   INTEGER DEFAULT 1,
                created_at TIMESTAMPTZ DEFAULT now(),
                updated_at TIMESTAMPTZ DEFAULT now()
            )""")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_dispatch_runs_job ON office.dispatch_runs(job_id)")
    else:
        cur = c.cursor()
        cur.executescript("""
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                project_id TEXT, project_name TEXT, goal TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                spec TEXT DEFAULT '{}', summary TEXT DEFAULT '{}',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE IF NOT EXISTS dispatch_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id TEXT NOT NULL, task_id TEXT NOT NULL, title TEXT DEFAULT '',
                cwd TEXT DEFAULT '', agent TEXT DEFAULT 'claude',
                status TEXT NOT NULL DEFAULT 'pending',
                output TEXT DEFAULT '', diff TEXT DEFAULT '{}',
                review TEXT DEFAULT '{}', error TEXT DEFAULT '',
                attempts INTEGER DEFAULT 1,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP);
            CREATE INDEX IF NOT EXISTS idx_dispatch_runs_job ON dispatch_runs(job_id);
        """)


def _ph(is_pg: bool, n: int = 1) -> str:
    """Backend-correct placeholder tokens: %s for Postgres, ? for SQLite."""
    return ", ".join(["%s" if is_pg else "?"] * n)


def create_job(project: Optional[Dict[str, Any]], spec: Dict[str, Any]) -> Dict[str, Any]:
    """Persist a queued job. `project` may be null (uses each subtask's own cwd)."""
    import uuid
    pid = project.get("id") if project else None
    pname = project.get("name") if project else None
    job_id = f"job_{uuid.uuid4().hex[:10]}"
    with conn() as c:
        _ensure_jobs(c)
        cur = c.cursor()
        is_pg = "psycopg" in type(c).__module__
        tbl = "office.jobs" if is_pg else "jobs"
        ph = _ph(is_pg, 7)
        cur.execute(
            f"INSERT INTO {tbl} (id, project_id, project_name, goal, status, spec, created_at) "
            f"VALUES ({ph})",
            (job_id, pid, pname, (spec.get("goal") or "")[:300], "pending",
             json.dumps(spec, default=str)[:12000],
             "now()" if is_pg else "CURRENT_TIMESTAMP"),
        )
    return {"id": job_id, "project_id": pid, "project_name": pname,
            "goal": spec.get("goal"), "status": "pending"}


def add_dispatch_run(job_id: str, task: Dict[str, Any]) -> int:
    """Create a row for one subtask inside a job; returns the run row id."""
    with conn() as c:
        _ensure_jobs(c)
        cur = c.cursor()
        is_pg = "psycopg" in type(c).__module__
        tbl = "office.dispatch_runs" if is_pg else "dispatch_runs"
        ph = _ph(is_pg, 5)
        if is_pg:
            cur.execute(
                f"INSERT INTO {tbl} (job_id, task_id, title, cwd, agent) "
                f"VALUES ({ph}) RETURNING id",
                (job_id, task.get("id"), task.get("title", ""),
                 task.get("cwd", ""), task.get("agent", "claude")),
            )
            return int(cur.fetchone()[0])
        cur.execute(
            f"INSERT INTO {tbl} (job_id, task_id, title, cwd, agent) "
            f"VALUES ({ph})",
            (job_id, task.get("id"), task.get("title", ""),
             task.get("cwd", ""), task.get("agent", "claude")),
        )
        return int(cur.lastrowid)


def update_dispatch_run(run_id: int, patch: Dict[str, Any]) -> None:
    """Patch a subtask run row: status, output, diff, review, error, attempts."""
    if not patch:
        return
    with conn() as c:
        _ensure_jobs(c)
        cur = c.cursor()
        is_pg = "psycopg" in type(c).__module__
        tbl = "office.dispatch_runs" if is_pg else "dispatch_runs"
        cols: list = []
        vals: list = []
        for k in ("status", "output", "error", "task_id", "cwd", "agent"):
            if k in patch:
                cols.append(k)
                vals.append(patch[k])
        for k in ("diff", "review"):
            if k in patch:
                cols.append(k)
                vals.append(json.dumps(patch[k], default=str))
        if "attempts" in patch:
            cols.append("attempts")
            vals.append(int(patch["attempts"]))
        if not cols:
            return
        p = "%s" if is_pg else "?"
        set_parts = ", ".join(f"{c} = {p}" for c in cols)
        cur.execute(
            f"UPDATE {tbl} SET {set_parts}, updated_at = {p} WHERE id = {p}",
            (*vals, "now()" if is_pg else "CURRENT_TIMESTAMP", run_id))


def update_job(job_id: str, patch: Dict[str, Any]) -> None:
    with conn() as c:
        _ensure_jobs(c)
        cur = c.cursor()
        is_pg = "psycopg" in type(c).__module__
        tbl = "office.jobs" if is_pg else "jobs"
        cols: list = []
        vals: list = []
        for k in ("status", "goal", "project_id", "project_name"):
            if k in patch:
                cols.append(k)
                vals.append(patch[k])
        for k in ("spec", "summary"):
            if k in patch:
                cols.append(k)
                vals.append(json.dumps(patch[k], default=str))
        if not cols:
            return
        p = "%s" if is_pg else "?"
        set_parts = ", ".join(f"{c} = {p}" for c in cols)
        cur.execute(
            f"UPDATE {tbl} SET {set_parts}, updated_at = {p} WHERE id = {p}",
            (*vals, "now()" if is_pg else "CURRENT_TIMESTAMP", job_id))


def list_jobs(limit: int = 30) -> List[Dict[str, Any]]:
    """Dashboard rows: job + completed-subtask counts + status."""
    with conn() as c:
        _ensure_jobs(c)
        cur = c.cursor()
        is_pg = "psycopg" in type(c).__module__
        tj = "office.jobs" if is_pg else "jobs"
        tr = "office.dispatch_runs" if is_pg else "dispatch_runs"
        p = "%s" if is_pg else "?"
        cur.execute(
            f"SELECT j.id, j.project_id, j.project_name, j.goal, j.status, "
            f"j.created_at, j.updated_at, "
            f"(SELECT COUNT(*) FROM {tr} r WHERE r.job_id = j.id), "
            f"(SELECT COUNT(*) FROM {tr} r WHERE r.job_id = j.id AND r.status = 'done') "
            f"FROM {tj} j ORDER BY j.created_at DESC LIMIT {p}",
            (min(int(limit), 100),),
        )
        out = []
        for row in cur.fetchall():
            out.append({
                "id": row[0], "project_id": row[1], "project_name": row[2],
                "goal": (row[3] or "")[:160], "status": row[4],
                "created_at": str(row[5]), "updated_at": str(row[6]),
                "subtasks": int(row[7] or 0), "done": int(row[8] or 0),
            })
        return out


def get_job(job_id: str) -> Optional[Dict[str, Any]]:
    with conn() as c:
        _ensure_jobs(c)
        cur = c.cursor()
        is_pg = "psycopg" in type(c).__module__
        tj = "office.jobs" if is_pg else "jobs"
        tr = "office.dispatch_runs" if is_pg else "dispatch_runs"
        p = "%s" if is_pg else "?"
        cur.execute(
            f"SELECT id, project_id, project_name, goal, status, spec, summary, "
            f"created_at, updated_at FROM {tj} WHERE id = {p}", (job_id,))
        row = cur.fetchone()
        if not row:
            return None
        job = {
            "id": row[0], "project_id": row[1], "project_name": row[2],
            "goal": row[3], "status": row[4],
            "spec": json.loads(row[5] or "{}"),
            "summary": json.loads(row[6] or "{}"),
            "created_at": str(row[7]), "updated_at": str(row[8]),
        }
        cur.execute(
            f"SELECT id, task_id, title, cwd, agent, status, output, diff, review, "
            f"error, attempts FROM {tr} WHERE job_id = {p} ORDER BY id", (job_id,))
        runs = []
        for r in cur.fetchall():
            runs.append({
                "id": int(r[0]), "task_id": r[1], "title": r[2], "cwd": r[3],
                "agent": r[4], "status": r[5],
                "output": (r[6] or "")[-4000:],
                "diff": json.loads(r[7] or "{}"),
                "review": json.loads(r[8] or "{}"),
                "error": (r[9] or "")[-500:],
                "attempts": int(r[10] or 1),
            })
        job["runs"] = runs
        job["done"] = sum(1 for r in runs if r["status"] == "done")
        job["total"] = len(runs)
        return job


def set_job_status(job_id: str, status: str) -> None:
    update_job(job_id, {"status": status if status in JOB_STATUSES else "failed"})

# ── Persona memory (how they learn each other) ────────────────────────────────

def remember(character_id: str, kind: str, content: str,
             source_room: Optional[str] = None,
             subject_id: Optional[str] = None) -> None:
    """Store a memory. observer = character_id; subject = who it's ABOUT (optional).

    Directional example: remember('ada_architect', 'teammate',
        'Kai always asks for tests before dispatching', subject_id='kai_builder')
    """
    with conn() as c:
        cur = c.cursor()
        is_pg = "psycopg" in type(c).__module__
        tbl = "office.persona_memory" if is_pg else "persona_memory"
        cur.execute(
            f"INSERT INTO {tbl} (character_id, kind, content, source_room, subject_id) "
            "VALUES (%s,%s,%s,%s,%s)",
            (character_id, kind, content[:2000], source_room, subject_id),
        )


def recall_about(observer_id: str, limit: int = 6,
                 about_subjects: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """What observer remembers — optionally prioritized by teammate present."""
    with conn() as c:
        cur = c.cursor()
        is_pg = "psycopg" in type(c).__module__
        tbl = "office.persona_memory" if is_pg else "persona_memory"
        rows = []
        if about_subjects:
            marks = ",".join(["%s"] * len(about_subjects)) if is_pg else \
                    ",".join(["?"] * len(about_subjects))
            cur.execute(
                f"SELECT kind, content, ts, subject_id FROM {tbl} "
                f"WHERE character_id = %s AND subject_id IN ({marks}) "
                f"ORDER BY ts DESC LIMIT %s",
                (observer_id, *about_subjects, limit),
            )
            rows = cur.fetchall()
        if len(rows) < limit:
            remaining = limit - len(rows)
            cur.execute(
                f"SELECT kind, content, ts, subject_id FROM {tbl} "
                f"WHERE character_id = %s ORDER BY ts DESC LIMIT %s",
                (observer_id, remaining),
            )
            seen = {(r[0], r[1]) for r in rows}
            rows += [r for r in cur.fetchall() if (r[0], r[1]) not in seen]
    return [{"kind": r[0], "content": r[1], "ts": str(r[2]), "subject_id": r[3]}
            for r in rows]


def memory_context(character_id: str, limit: int = 6,
                   about_subjects: Optional[List[str]] = None) -> str:
    """Render memories for injection into a system prompt."""
    mems = recall_about(character_id, limit, about_subjects)
    if not mems:
        return ""
    lines = [f"- ({m['kind']}) {m['content']}" for m in mems]
    return "\nThings you remember from working together:\n" + "\n".join(lines)


def status() -> Dict[str, Any]:
    with conn() as c:
        backend = "postgres" if "psycopg" in type(c).__module__ else "sqlite"
        cur = c.cursor()
        pfx = "office." if backend == "postgres" else ""
        cur.execute(f"SELECT COUNT(*) FROM {pfx}rooms")
        rooms = cur.fetchone()[0]
        cur.execute(f"SELECT COUNT(*) FROM {pfx}messages")
        msgs = cur.fetchone()[0]
        cur.execute(f"SELECT COUNT(*) FROM {pfx}persona_memory")
        mems = cur.fetchone()[0]
    return {"backend": backend, "rooms": rooms, "messages": msgs, "memories": mems}
