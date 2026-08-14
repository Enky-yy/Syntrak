"""SQLite database persistence for Syntrak Web Server."""

import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


def get_db_path() -> Path:
    """Get path to database from environment variables or default to ~/.syntrak/syntrak.db."""
    db_env = (
        os.getenv("DATABASE_URL")
        or os.getenv("SQL_DATABASE_URL")
        or os.getenv("DATABASE_PATH")
        or os.getenv("SQL_DATABASE_PATH")
        or os.getenv("SYNTRAK_DATABASE_PATH")
    )
    if db_env:
        # Strip sqlite URI prefix if present
        if db_env.startswith("sqlite:///"):
            db_env = db_env[len("sqlite:///"):]
        elif db_env.startswith("sqlite://"):
            db_env = db_env[len("sqlite://"):]
        p = Path(db_env).expanduser()
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    db_dir = Path.home() / ".syntrak"
    db_dir.mkdir(parents=True, exist_ok=True)
    return db_dir / "syntrak.db"


class Database:
    """Thread-safe SQLite database manager for chat history and users."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or get_db_path()
        self.init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def init_db(self):
        """Create database tables if they do not exist."""
        with self._get_connection() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    email TEXT UNIQUE NOT NULL,
                    name TEXT,
                    picture TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS conversations (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS messages (
                    id TEXT PRIMARY KEY,
                    conversation_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT,
                    events_json TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_conversations_user ON conversations(user_id, updated_at);
                CREATE INDEX IF NOT EXISTS idx_messages_conv ON messages(conversation_id, created_at);
            """)

    # User operations
    def upsert_user(self, user_id: str, email: str, name: Optional[str] = None, picture: Optional[str] = None) -> Dict[str, Any]:
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO users (id, email, name, picture)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    email = excluded.email,
                    name = COALESCE(excluded.name, users.name),
                    picture = COALESCE(excluded.picture, users.picture)
            """, (user_id, email, name, picture))
            row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
            return dict(row)

    def get_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
            return dict(row) if row else None

    # Conversation operations
    def create_conversation(self, user_id: str, title: Optional[str] = None, conversation_id: Optional[str] = None) -> Dict[str, Any]:
        conv_id = conversation_id or str(uuid.uuid4())
        conv_title = title or "New Chat"
        now = datetime.now(timezone.utc).isoformat()

        # Ensure user exists (auto-create guest if needed)
        self.upsert_user(user_id=user_id, email=f"{user_id}@local.user", name="Guest Developer")

        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO conversations (id, user_id, title, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
            """, (conv_id, user_id, conv_title, now, now))
            row = conn.execute("SELECT * FROM conversations WHERE id = ?", (conv_id,)).fetchone()
            return dict(row)

    def get_conversations(self, user_id: str) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.execute("""
                SELECT c.id, c.user_id, c.title, c.created_at, c.updated_at,
                       COUNT(m.id) as message_count
                FROM conversations c
                LEFT JOIN messages m ON c.id = m.conversation_id
                WHERE c.user_id = ?
                GROUP BY c.id
                ORDER BY c.updated_at DESC
            """, (user_id,))
            return [dict(row) for row in cursor.fetchall()]

    def get_conversation(self, conversation_id: str, user_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            if user_id:
                row = conn.execute("SELECT * FROM conversations WHERE id = ? AND user_id = ?", (conversation_id, user_id)).fetchone()
            else:
                row = conn.execute("SELECT * FROM conversations WHERE id = ?", (conversation_id,)).fetchone()
            return dict(row) if row else None

    def update_conversation_title(self, conversation_id: str, title: str, user_id: Optional[str] = None) -> bool:
        with self._get_connection() as conn:
            now = datetime.now(timezone.utc).isoformat()
            if user_id:
                cursor = conn.execute("""
                    UPDATE conversations SET title = ?, updated_at = ?
                    WHERE id = ? AND user_id = ?
                """, (title, now, conversation_id, user_id))
            else:
                cursor = conn.execute("""
                    UPDATE conversations SET title = ?, updated_at = ?
                    WHERE id = ?
                """, (title, now, conversation_id))
            return cursor.rowcount > 0

    def touch_conversation(self, conversation_id: str):
        with self._get_connection() as conn:
            now = datetime.now(timezone.utc).isoformat()
            conn.execute("UPDATE conversations SET updated_at = ? WHERE id = ?", (now, conversation_id))

    def delete_conversation(self, conversation_id: str, user_id: Optional[str] = None) -> bool:
        with self._get_connection() as conn:
            if user_id:
                cursor = conn.execute("DELETE FROM conversations WHERE id = ? AND user_id = ?", (conversation_id, user_id))
            else:
                cursor = conn.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))
            return cursor.rowcount > 0

    # Message operations
    def add_message(
        self,
        conversation_id: str,
        role: str,
        content: Optional[str] = None,
        events: Optional[List[Dict[str, Any]]] = None,
        message_id: Optional[str] = None
    ) -> Dict[str, Any]:
        msg_id = message_id or str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        events_json = json.dumps(events) if events else None

        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO messages (id, conversation_id, role, content, events_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (msg_id, conversation_id, role, content, events_json, now))

        self.touch_conversation(conversation_id)
        return {
            "id": msg_id,
            "conversation_id": conversation_id,
            "role": role,
            "content": content,
            "events": events or [],
            "created_at": now
        }

    def get_messages(self, conversation_id: str) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.execute("""
                SELECT id, conversation_id, role, content, events_json, created_at
                FROM messages
                WHERE conversation_id = ?
                ORDER BY created_at ASC
            """, (conversation_id,))
            results = []
            for row in cursor.fetchall():
                data = dict(row)
                data["events"] = json.loads(data["events_json"]) if data.get("events_json") else []
                del data["events_json"]
                results.append(data)
            return results


# Global singleton instance
default_db = Database()
