# db/audit.py
# SQLite store — queue + audit trail

import sqlite3
import json
import logging
from datetime import datetime, timezone
from uuid import uuid4

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DB_PATH = "audit.db"


def init_db():
    """Create tables if they don't exist."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS audit_log (
            id TEXT PRIMARY KEY,
            page_path TEXT,
            original_content TEXT,
            refreshed_content TEXT,
            reasoning TEXT,
            reviewer_action TEXT DEFAULT 'pending',
            reviewer_edits TEXT DEFAULT '',
            timestamp TEXT,
            rolled_back INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()
    logger.info("[DB] audit_log table ready")


def insert_entry(page_dict: dict, refreshed: dict, reasoning: dict) -> str:
    entry_id = str(uuid4())
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT INTO audit_log
            (id, page_path, original_content, refreshed_content, reasoning, timestamp)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        entry_id,
        page_dict.get("path"),
        json.dumps(page_dict),
        json.dumps(refreshed),
        json.dumps(reasoning),
        datetime.now(timezone.utc).isoformat()
    ))
    conn.commit()
    conn.close()
    logger.info(f"[DB] Inserted entry {entry_id} for {page_dict.get('path')}")
    return entry_id

def get_queue() -> list[dict]:
    """Return all pending entries."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM audit_log WHERE reviewer_action = 'pending' ORDER BY timestamp DESC")
    rows = [dict(row) for row in c.fetchall()]
    conn.close()
    return rows


def get_all_entries() -> list[dict]:
    """Return all entries ordered by timestamp desc."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM audit_log ORDER BY timestamp DESC")
    rows = [dict(row) for row in c.fetchall()]
    conn.close()
    return rows


def update_action(entry_id: str, action: str, edits: str = ""):
    """Update reviewer action for an entry."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        UPDATE audit_log
        SET reviewer_action = ?, reviewer_edits = ?
        WHERE id = ?
    """, (action, edits, entry_id))
    conn.commit()
    conn.close()
    logger.info(f"[DB] Entry {entry_id} marked as {action}")


def get_entry_by_id(entry_id: str) -> dict | None:
    """Fetch a single entry by ID."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM audit_log WHERE id = ?", (entry_id,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None


def mark_rolled_back(entry_id: str):
    """Mark an audit entry as rolled back."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        UPDATE audit_log
        SET rolled_back = 1
        WHERE id = ?
    """, (entry_id,))
    conn.commit()
    conn.close()
    logger.info(f"[DB] Entry {entry_id} marked as rolled back")