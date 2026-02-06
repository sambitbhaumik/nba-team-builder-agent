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
                key TEXT NOT NULL,
                value TEXT NOT NULL
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
                updated_at TEXT NOT NULL,
                FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS pending_approvals (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                action_type TEXT NOT NULL,
                details_json TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending', -- 'pending', 'approved', 'rejected'
                created_at TEXT NOT NULL,
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


def get_session_messages(session_id: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT messages_json FROM sessions WHERE id = ?",
            (session_id,),
        ).fetchone()
        if not row:
            return []
        messages = _load_messages(row["messages_json"])
        if limit is not None:
            return messages[-limit:] if len(messages) >= limit else messages
        return messages


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


def add_preference(key: str, value: str) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO user_preferences (key, value)
            VALUES (?, ?)
            """,
            (key, value),
        )
        conn.commit()


def query_preferences() -> List[Dict[str, str]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT key, value FROM user_preferences"
        ).fetchall()
        return [dict[str, str](row) for row in rows]


def clear_user_preferences() -> None:
    """Clear all user preferences."""
    with get_connection() as conn:
        conn.execute("DELETE FROM user_preferences")
        conn.commit()


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
            "SELECT roster_json, budget FROM session_rosters WHERE session_id = ?",
            (session_id,),
        ).fetchone()
        if not row:
            return {
                "players": [],
                "budget": 200.0,
                "total_cost": 0.0,
            }
        roster_data = json.loads(row["roster_json"])
        total_cost = sum(p.get("dollar_value", 0.0) for p in roster_data.get("players", []))
        remaining_budget = float(row["budget"]) - total_cost
        return {
            "players": roster_data.get("players", []),
            "budget": float(row["budget"]),
            "total_cost": total_cost,
            "remaining_budget": remaining_budget,
        }


def update_session_roster(
    session_id: str,
    players: List[Dict[str, Any]],
    budget: float = 200.0,
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
                SET roster_json = ?, budget = ?, updated_at = ?
                WHERE session_id = ?
                """,
                (roster_json, budget, now, session_id),
            )
        else:
            conn.execute(
                """
                INSERT INTO session_rosters (session_id, roster_json, budget, updated_at)
                VALUES (?, ?, ?, ?)
                """,
                (session_id, roster_json, budget, now),
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


def create_pending_approval(
    approval_id: str,
    session_id: str,
    action_type: str,
    details: Dict[str, Any]
) -> None:
    """Create a new pending approval."""
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO pending_approvals (id, session_id, action_type, details_json, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, 'pending', ?, ?)
            """,
            (approval_id, session_id, action_type, json.dumps(details), now, now),
        )
        conn.commit()


def get_pending_approval(approval_id: str) -> Optional[Dict[str, Any]]:
    """Get a pending approval by ID."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM pending_approvals WHERE id = ?",
            (approval_id,),
        ).fetchone()
        if not row:
            return None
        res = dict(row)
        res["details"] = json.loads(res["details_json"])
        return res


def update_approval_status(approval_id: str, status: str) -> None:
    """Update approval status."""
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE pending_approvals
            SET status = ?, updated_at = ?
            WHERE id = ?
            """,
            (status, now, approval_id),
        )
        conn.commit()


def get_latest_pending_approval(session_id: str) -> Optional[Dict[str, Any]]:
    """Get the latest pending approval for a session."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM pending_approvals WHERE session_id = ? AND status = 'pending' ORDER BY created_at DESC LIMIT 1",
            (session_id,),
        ).fetchone()
        if not row:
            return None
        res = dict(row)
        res["details"] = json.loads(res["details_json"])
        return res
