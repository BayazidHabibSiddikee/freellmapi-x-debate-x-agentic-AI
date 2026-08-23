"""
services/agent/industry.py — Phase 3: cross-team knowledge marketplace.

Teams stop being silos: any team's hard-won lesson can be published to a
shared pool and surfaced to *other* teams when they face a related problem.
One table, one connection strategy — reuses services/agent/db.py's conn()
(Postgres `office` schema, SQLite fallback), so there is exactly one backup
and one governance surface for everything the industry knows.
"""

import os
import time
from typing import Any, Dict, List, Optional

from db import conn  # same directory — dispatcher adds this to sys.path

TABLE = "industry_insights"


def _ensure(c: Any) -> None:
    if "psycopg" in type(c).__module__:
        cur = c.cursor()
        cur.execute("CREATE SCHEMA IF NOT EXISTS office")
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS office.{TABLE} (
                id         BIGSERIAL PRIMARY KEY,
                team       TEXT NOT NULL DEFAULT 'main',
                author     TEXT NOT NULL,
                topic      TEXT NOT NULL,
                insight    TEXT NOT NULL,
                created_at TIMESTAMPTZ DEFAULT now()
            )""")
        cur.execute(f"CREATE INDEX IF NOT EXISTS idx_{TABLE}_topic ON office.{TABLE}(topic)")
        cur.execute(f"CREATE INDEX IF NOT EXISTS idx_{TABLE}_team ON office.{TABLE}(team, created_at DESC)")
    else:
        cur = c.cursor()
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS {TABLE} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                team TEXT NOT NULL DEFAULT 'main',
                author TEXT NOT NULL,
                topic TEXT NOT NULL,
                insight TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )""")


def publish(team: str, author: str, topic: str, insight: str) -> Dict[str, Any]:
    """Record a reusable lesson so OTHER teams can find it later."""
    topic = (topic or "").strip()
    insight = (insight or "").strip()
    if not topic or not insight:
        raise ValueError("publish requires non-empty 'topic' and 'insight'")
    with conn() as c:
        _ensure(c)
        cur = c.cursor()
        if "psycopg" in type(c).__module__:
            cur.execute(
                f"INSERT INTO office.{TABLE} (team, author, topic, insight) VALUES (%s,%s,%s,%s) RETURNING id",
                (team, author, topic[:120], insight[:2000]),
            )
            new_id = cur.fetchone()[0]
        else:
            cur.execute(
                f"INSERT INTO {TABLE} (team, author, topic, insight) VALUES (?,?,?,?)",
                (team, author, topic[:120], insight[:2000]),
            )
            new_id = cur.lastrowid
    return {"published": True, "id": new_id, "team": team, "topic": topic}


def search(query: str, exclude_team: Optional[str] = None, limit: int = 6) -> List[Dict[str, Any]]:
    """Find insights from the marketplace; by default EXCLUDE your own team."""
    query = (query or "").strip()
    if not query:
        return []
    words = [w for w in query.lower().split() if len(w) > 2][:5]
    if not words:
        return []
    with conn() as c:
        _ensure(c)
        cur = c.cursor()
        like = "%" + ("%".join(words)) + "%"
        if "psycopg" in type(c).__module__:
            sql = (f"SELECT id, team, author, topic, insight, created_at FROM office.{TABLE} "
                   "WHERE (lower(topic) LIKE %s OR lower(insight) LIKE %s)"
                   + (" AND team <> %s" if exclude_team else "")
                   + " ORDER BY created_at DESC LIMIT %s")
            args: List[Any] = [like, like]
            if exclude_team:
                args.append(exclude_team)
            args.append(max(1, min(limit, 20)))
            cur.execute(sql, tuple(args))
            cols = ["id", "team", "author", "topic", "insight", "created_at"]
        else:
            sql = (f"SELECT id, team, author, topic, insight, created_at FROM {TABLE} "
                   "WHERE (lower(topic) LIKE ? OR lower(insight) LIKE ?)"
                   + (" AND team <> ?" if exclude_team else "")
                   + " ORDER BY id DESC LIMIT ?")
            args = [like, like]
            if exclude_team:
                args.append(exclude_team)
            args.append(max(1, min(limit, 20)))
            cur.execute(sql, tuple(args))
            cols = ["id", "team", "author", "topic", "insight", "created_at"]
        rows = [dict(zip(cols, r)) for r in cur.fetchall()]
    return rows


def status() -> Dict[str, Any]:
    with conn() as c:
        _ensure(c)
        cur = c.cursor()
        if "psycopg" in type(c).__module__:
            cur.execute(f"SELECT count(*), count(DISTINCT team) FROM office.{TABLE}")
        else:
            cur.execute(f"SELECT count(*), count(DISTINCT team) FROM {TABLE}")
        total, teams = cur.fetchone()
    return {"backend": "postgres" if "psycopg" in type(c).__module__ else "sqlite",
            "total_insights": int(total), "teams_sharing": int(teams)}
