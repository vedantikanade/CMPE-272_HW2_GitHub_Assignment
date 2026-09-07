# Authored by Vedanti Kanade
# Written by: [Your Name] - SJSU CMPE-272
import sqlite3
from typing import List, Dict, Any, Optional

DB_FILE = "webhooks.db"

def init_db():
    """Initializes SQLite database table for storing webhook events."""
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS webhook_events (
                delivery_id TEXT PRIMARY KEY,
                event TEXT NOT NULL,
                action TEXT,
                issue_number INTEGER,
                payload TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()

def is_duplicate_delivery(delivery_id: str) -> bool:
    """Checks if a delivery ID has already been processed (Idempotency)."""
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM webhook_events WHERE delivery_id = ?", (delivery_id,))
        return cursor.fetchone() is not None

def save_webhook_event(delivery_id: str, event: str, action: Optional[str], issue_number: Optional[int], payload: str):
    """Saves a unique webhook event to SQLite."""
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO webhook_events (delivery_id, event, action, issue_number, payload)
            VALUES (?, ?, ?, ?, ?)
        """, (delivery_id, event, action, issue_number, payload))
        conn.commit()

def get_recent_events(limit: int = 20) -> List[Dict[str, Any]]:
    """Retrieves the last N webhook deliveries."""
    with sqlite3.connect(DB_FILE) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""
            SELECT delivery_id as id, event, action, issue_number, timestamp
            FROM webhook_events
            ORDER BY timestamp DESC
            LIMIT ?
        """, (limit,))
        rows = cursor.fetchall()
        return [dict(row) for row in rows]