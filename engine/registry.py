"""
SQLite registry for idempotent processing.

Tracks which files have been processed (by content hash) to prevent
duplicate processing. Lightweight — no ORM, just raw SQLite.

Also tracks watcher system status for UI visibility.
"""

import hashlib
import json
import logging
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Retry configuration
MAX_RETRIES = 5
RETRY_BACKOFF_MINUTES = [1, 5, 15, 60, 240]  # Exponential backoff


class ProcessingRegistry:
    """SQLite-backed registry of processed audio files.

    Uses SHA-256 content hashes to prevent duplicate processing,
    even if files are renamed or re-synced.
    """

    def __init__(self, db_path: Path):
        self.db_path = db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        """Create the processed_files and watcher_status tables."""
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS processed_files (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    filename TEXT NOT NULL,
                    file_hash TEXT NOT NULL UNIQUE,
                    file_size INTEGER,
                    mode TEXT,
                    title TEXT,
                    note_path TEXT,
                    duration_seconds REAL,
                    processed_at TEXT NOT NULL,
                    success INTEGER DEFAULT 1,
                    error TEXT,
                    retry_count INTEGER DEFAULT 0,
                    last_retry_at TEXT,
                    skipped INTEGER DEFAULT 0
                )
            """)
            # Add new columns if they don't exist (migration)
            try:
                conn.execute("ALTER TABLE processed_files ADD COLUMN retry_count INTEGER DEFAULT 0")
            except sqlite3.OperationalError:
                pass
            try:
                conn.execute("ALTER TABLE processed_files ADD COLUMN last_retry_at TEXT")
            except sqlite3.OperationalError:
                pass
            try:
                conn.execute("ALTER TABLE processed_files ADD COLUMN skipped INTEGER DEFAULT 0")
            except sqlite3.OperationalError:
                pass
            try:
                conn.execute("ALTER TABLE processed_files ADD COLUMN transcript_path TEXT")
            except sqlite3.OperationalError:
                pass
            try:
                conn.execute("ALTER TABLE processed_files ADD COLUMN has_tasks INTEGER DEFAULT 0")
            except sqlite3.OperationalError:
                pass
            try:
                conn.execute("ALTER TABLE processed_files ADD COLUMN audio_path TEXT")
            except sqlite3.OperationalError:
                pass
            try:
                conn.execute("ALTER TABLE processed_files ADD COLUMN ingested_at TEXT")
            except sqlite3.OperationalError:
                pass
            
            # Watcher status table - tracks what the system is doing RIGHT NOW
            conn.execute("""
                CREATE TABLE IF NOT EXISTS watcher_status (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    state TEXT DEFAULT 'idle',
                    current_file TEXT,
                    current_step TEXT,
                    last_scan_at TEXT,
                    scan_count INTEGER DEFAULT 0,
                    files_in_queue INTEGER DEFAULT 0,
                    updated_at TEXT
                )
            """)
            # Initialize single status row if not exists
            conn.execute("""
                INSERT OR IGNORE INTO watcher_status (id, state, updated_at)
                VALUES (1, 'starting', ?)
            """, (datetime.utcnow().isoformat(),))

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(str(self.db_path))

    @staticmethod
    def compute_hash(file_path: Path) -> str:
        """Compute SHA-256 hash of a file's contents."""
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        return sha256.hexdigest()

    def is_processed(self, file_hash: str) -> bool:
        """Check if a file with this hash was already successfully processed."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT id FROM processed_files WHERE file_hash = ? AND success = 1",
                (file_hash,),
            ).fetchone()
            return row is not None

    def should_skip(self, file_hash: str) -> tuple[bool, str]:
        """Check if a file should be skipped (already processed, skipped, or in backoff).
        
        Returns: (should_skip, reason)
        """
        with self._connect() as conn:
            row = conn.execute(
                """SELECT success, skipped, retry_count, last_retry_at, error
                   FROM processed_files WHERE file_hash = ?""",
                (file_hash,),
            ).fetchone()
            
            if not row:
                return False, ""
            
            success, skipped, retry_count, last_retry_at, error = row
            
            # Already successfully processed
            if success:
                return True, "already_processed"
            
            # Manually skipped by user
            if skipped:
                return True, "skipped_by_user"
            
            # Max retries exceeded
            if retry_count >= MAX_RETRIES:
                return True, f"max_retries_exceeded ({retry_count})"
            
            # Check backoff timing
            if last_retry_at and retry_count > 0:
                backoff_idx = min(retry_count - 1, len(RETRY_BACKOFF_MINUTES) - 1)
                backoff_mins = RETRY_BACKOFF_MINUTES[backoff_idx]
                last_retry = datetime.fromisoformat(last_retry_at)
                next_retry = last_retry + timedelta(minutes=backoff_mins)
                if datetime.utcnow() < next_retry:
                    mins_left = (next_retry - datetime.utcnow()).total_seconds() / 60
                    return True, f"backoff ({mins_left:.0f}m until retry #{retry_count + 1})"
            
            return False, ""

    def record_success(
        self,
        filename: str,
        file_hash: str,
        file_size: int,
        mode: str,
        title: str,
        note_path: str,
        duration: Optional[float] = None,
        transcript_path: str = "",
        has_tasks: bool = False,
        audio_path: str = "",
    ):
        """Record a successfully processed file."""
        now = datetime.utcnow().isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO processed_files
                    (filename, file_hash, file_size, mode, title, note_path,
                     duration_seconds, processed_at, ingested_at, success, error,
                     transcript_path, has_tasks, audio_path)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, NULL, ?, ?, ?)
                """,
                (
                    filename,
                    file_hash,
                    file_size,
                    mode,
                    title,
                    note_path,
                    duration,
                    now,
                    now,
                    transcript_path,
                    1 if has_tasks else 0,
                    audio_path,
                ),
            )
        logger.info(f"Registry: recorded success for {filename}")

    def record_failure(
        self,
        filename: str,
        file_hash: str,
        file_size: int,
        error: str,
    ):
        """Record a failed processing attempt with retry tracking."""
        now = datetime.utcnow().isoformat()
        with self._connect() as conn:
            # Get current retry count
            row = conn.execute(
                "SELECT retry_count FROM processed_files WHERE file_hash = ?",
                (file_hash,),
            ).fetchone()
            retry_count = (row[0] or 0) + 1 if row else 1
            
            conn.execute(
                """
                INSERT INTO processed_files
                    (filename, file_hash, file_size, processed_at, success, error,
                     retry_count, last_retry_at)
                VALUES (?, ?, ?, ?, 0, ?, ?, ?)
                ON CONFLICT(file_hash) DO UPDATE SET
                    processed_at = excluded.processed_at,
                    error = excluded.error,
                    retry_count = excluded.retry_count,
                    last_retry_at = excluded.last_retry_at
                """,
                (
                    filename,
                    file_hash,
                    file_size,
                    now,
                    error,
                    retry_count,
                    now,
                ),
            )
        logger.warning(f"Registry: recorded failure #{retry_count} for {filename} — {error}")

    def get_stats(self) -> dict:
        """Get processing statistics."""
        with self._connect() as conn:
            total = conn.execute("SELECT COUNT(*) FROM processed_files").fetchone()[0]
            success = conn.execute(
                "SELECT COUNT(*) FROM processed_files WHERE success = 1"
            ).fetchone()[0]
            failed = conn.execute(
                "SELECT COUNT(*) FROM processed_files WHERE success = 0"
            ).fetchone()[0]
        return {"total": total, "success": success, "failed": failed}

    def get_recent(self, limit: int = 20) -> list[dict]:
        """Get recently processed files, sorted by ingested_at DESC (newest first)."""
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT filename, mode, title, note_path, duration_seconds,
                       processed_at, ingested_at, success, error, retry_count, skipped
                FROM processed_files
                ORDER BY COALESCE(ingested_at, processed_at) DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
            return [dict(row) for row in rows]

    # =========================================================================
    # Failed Files Management
    # =========================================================================

    def get_failed_files(self) -> list[dict]:
        """Get all failed files with retry info."""
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT filename, file_hash, error, retry_count, last_retry_at, skipped
                FROM processed_files
                WHERE success = 0
                ORDER BY last_retry_at DESC
                """,
            ).fetchall()
            
            result = []
            for row in rows:
                d = dict(row)
                # Calculate next retry time
                if d['skipped']:
                    d['next_retry'] = None
                    d['status'] = 'skipped'
                elif d['retry_count'] >= MAX_RETRIES:
                    d['next_retry'] = None
                    d['status'] = 'max_retries'
                elif d['last_retry_at']:
                    backoff_idx = min(d['retry_count'] - 1, len(RETRY_BACKOFF_MINUTES) - 1)
                    backoff_mins = RETRY_BACKOFF_MINUTES[backoff_idx]
                    last = datetime.fromisoformat(d['last_retry_at'])
                    next_retry = last + timedelta(minutes=backoff_mins)
                    d['next_retry'] = next_retry.isoformat()
                    d['status'] = 'waiting' if datetime.utcnow() < next_retry else 'ready'
                else:
                    d['next_retry'] = datetime.utcnow().isoformat()
                    d['status'] = 'ready'
                result.append(d)
            return result

    def skip_file(self, file_hash: str):
        """Mark a file as skipped (won't be retried)."""
        with self._connect() as conn:
            conn.execute(
                "UPDATE processed_files SET skipped = 1 WHERE file_hash = ?",
                (file_hash,),
            )
        logger.info(f"Registry: marked {file_hash[:8]}... as skipped")

    def unskip_file(self, file_hash: str):
        """Unmark a file as skipped (will be retried)."""
        with self._connect() as conn:
            conn.execute(
                "UPDATE processed_files SET skipped = 0, retry_count = 0 WHERE file_hash = ?",
                (file_hash,),
            )
        logger.info(f"Registry: unmarked {file_hash[:8]}... for retry")

    def clear_failed(self):
        """Remove all failed entries (they'll be reprocessed fresh)."""
        with self._connect() as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM processed_files WHERE success = 0"
            ).fetchone()[0]
            conn.execute("DELETE FROM processed_files WHERE success = 0")
        logger.info(f"Registry: cleared {count} failed entries")
        return count

    def skip_all_failed(self):
        """Mark all failed files as skipped."""
        with self._connect() as conn:
            count = conn.execute(
                "UPDATE processed_files SET skipped = 1 WHERE success = 0 AND skipped = 0"
            ).rowcount
        logger.info(f"Registry: skipped {count} failed files")
        return count

    # =========================================================================
    # Watcher Status (System State)
    # =========================================================================

    def update_watcher_status(
        self,
        state: str,
        current_file: Optional[str] = None,
        current_step: Optional[str] = None,
        files_in_queue: int = 0,
    ):
        """Update the watcher's current status."""
        now = datetime.utcnow().isoformat()
        with self._connect() as conn:
            if state == "scanning":
                conn.execute(
                    """UPDATE watcher_status SET
                        state = ?, current_file = NULL, current_step = NULL,
                        last_scan_at = ?, scan_count = scan_count + 1,
                        files_in_queue = ?, updated_at = ?
                    WHERE id = 1""",
                    (state, now, files_in_queue, now),
                )
            else:
                conn.execute(
                    """UPDATE watcher_status SET
                        state = ?, current_file = ?, current_step = ?,
                        files_in_queue = ?, updated_at = ?
                    WHERE id = 1""",
                    (state, current_file, current_step, files_in_queue, now),
                )

    def get_watcher_status(self) -> dict:
        """Get the current watcher status."""
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM watcher_status WHERE id = 1"
            ).fetchone()
            if row:
                return dict(row)
            return {
                "state": "unknown",
                "current_file": None,
                "current_step": None,
                "last_scan_at": None,
                "scan_count": 0,
                "files_in_queue": 0,
                "updated_at": None,
            }
