from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "app.db"


def get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                messages_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS user_preferences (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT NOT NULL,
                value TEXT NOT NULL,
                tags TEXT,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS teams (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                roster_json TEXT NOT NULL,
                budget REAL NOT NULL,
                total_cost REAL NOT NULL,
                notes TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS session_rosters (
                session_id TEXT PRIMARY KEY,
                roster_json TEXT NOT NULL,
                budget REAL NOT NULL DEFAULT 200.0,
                slots INTEGER NOT NULL DEFAULT 12,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
            )
            """
        )
        conn.commit()


def _load_messages(messages_json: str) -> List[Dict[str, Any]]:
    try:
        return json.loads(messages_json)
    except json.JSONDecodeError:
        return []


def get_session_messages(session_id: str) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT messages_json FROM sessions WHERE id = ?",
            (session_id,),
        ).fetchone()
        if not row:
            return []
        return _load_messages(row["messages_json"])


def save_session_messages(session_id: str, messages: List[Dict[str, Any]]) -> None:
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        existing = conn.execute(
            "SELECT id FROM sessions WHERE id = ?",
            (session_id,),
        ).fetchone()
        if existing:
            conn.execute(
                """
                UPDATE sessions
                SET messages_json = ?, updated_at = ?
                WHERE id = ?
                """,
                (json.dumps(messages), now, session_id),
            )
        else:
            conn.execute(
                """
                INSERT INTO sessions (id, messages_json, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                """,
                (session_id, json.dumps(messages), now, now),
            )
        conn.commit()


def append_session_message(session_id: str, role: str, content: str) -> None:
    messages = get_session_messages(session_id)
    messages.append({"role": role, "content": content})
    save_session_messages(session_id, messages)


def add_preference(key: str, value: str, tags: Optional[str] = None) -> None:
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO user_preferences (key, value, tags, updated_at)
            VALUES (?, ?, ?, ?)
            """,
            (key, value, tags, now),
        )
        conn.commit()


def query_preferences() -> List[Dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT key, value, tags, updated_at FROM user_preferences ORDER BY updated_at DESC"
        ).fetchall()
        return [dict(row) for row in rows]


def save_team(
    team_id: str,
    name: str,
    roster_json: str,
    budget: float,
    total_cost: float,
    notes: Optional[str] = None,
) -> None:
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO teams (id, name, roster_json, budget, total_cost, notes, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (team_id, name, roster_json, budget, total_cost, notes, now),
        )
        conn.commit()


def list_teams() -> List[Dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, name, roster_json, budget, total_cost, notes, created_at
            FROM teams
            ORDER BY created_at DESC
            """
        ).fetchall()
        return [dict(row) for row in rows]


def get_session_roster(session_id: str) -> Dict[str, Any]:
    """Get current roster for a session."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT roster_json, budget, slots FROM session_rosters WHERE session_id = ?",
            (session_id,),
        ).fetchone()
        if not row:
            return {
                "players": [],
                "budget": 200.0,
                "slots": 12,
                "total_cost": 0.0,
            }
        roster_data = json.loads(row["roster_json"])
        return {
            "players": roster_data.get("players", []),
            "budget": float(row["budget"]),
            "slots": int(row["slots"]),
            "total_cost": sum(p.get("dollar_value", 0.0) for p in roster_data.get("players", [])),
        }


def update_session_roster(
    session_id: str,
    players: List[Dict[str, Any]],
    budget: float = 200.0,
    slots: int = 12,
) -> None:
    """Update roster for a session."""
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc).isoformat()
    roster_json = json.dumps({"players": players})
    with get_connection() as conn:
        existing = conn.execute(
            "SELECT session_id FROM session_rosters WHERE session_id = ?",
            (session_id,),
        ).fetchone()
        if existing:
            conn.execute(
                """
                UPDATE session_rosters
                SET roster_json = ?, budget = ?, slots = ?, updated_at = ?
                WHERE session_id = ?
                """,
                (roster_json, budget, slots, now, session_id),
            )
        else:
            conn.execute(
                """
                INSERT INTO session_rosters (session_id, roster_json, budget, slots, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (session_id, roster_json, budget, slots, now),
            )
        conn.commit()


def clear_session_roster(session_id: str) -> None:
    """Clear roster for a session."""
    with get_connection() as conn:
        conn.execute(
            "DELETE FROM session_rosters WHERE session_id = ?",
            (session_id,),
        )
        conn.commit()
