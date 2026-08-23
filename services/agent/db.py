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
            yield c
            c.close()
            return
        except Exception as e:  # noqa: BLE001
            print(f"[db] postgres unavailable ({e}) — falling back to sqlite")
            _pool_pg = False
    SQLITE_FALLBACK.parent.mkdir(parents=True, exist_ok=True)
    yield sqlite3.connect(SQLITE_FALLBACK)


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
