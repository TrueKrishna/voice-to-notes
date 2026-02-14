"""
Shared API Key Management - Works with both SQLAlchemy (V1) and raw SQLite (V2).

This module provides:
1. Available model configurations
2. API key reading from database
3. Key rotation and selection logic

Decoupled from any specific version to support future enhancements.
"""

import sqlite3
import logging
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


# ============================================================================
# Available Gemini Models
# ============================================================================

@dataclass
class ModelConfig:
    """Configuration for a Gemini model."""
    id: str                  # Model ID for API calls
    display_name: str        # Human-readable name
    description: str         # Short description
    rpm_limit: int           # Requests per minute limit
    supports_audio: bool     # Whether it supports audio transcription
    recommended: bool = False  # Whether this is the recommended choice


# Available models - update this list as new models are released
AVAILABLE_MODELS = [
    ModelConfig(
        id="gemini-3-flash-preview",
        display_name="Gemini 3 Flash Preview",
        description="Latest preview model, recommended for voice transcription",
        rpm_limit=15,
        supports_audio=True,
        recommended=True,
    ),
    ModelConfig(
        id="gemini-2.0-flash",
        display_name="Gemini 2.0 Flash",
        description="Fast and efficient, good for most use cases",
        rpm_limit=15,
        supports_audio=True,
    ),
    ModelConfig(
        id="gemini-2.0-flash-lite",
        display_name="Gemini 2.0 Flash Lite",
        description="Lighter version, faster but less capable",
        rpm_limit=30,
        supports_audio=True,
    ),
    ModelConfig(
        id="gemini-1.5-pro",
        display_name="Gemini 1.5 Pro",
        description="More capable but slower, better for complex tasks",
        rpm_limit=2,
        supports_audio=True,
    ),
]

# Default model for new installations - must match V1!
DEFAULT_MODEL = "gemini-3-flash-preview"


def get_model_config(model_id: str) -> Optional[ModelConfig]:
    """Get configuration for a specific model."""
    for model in AVAILABLE_MODELS:
        if model.id == model_id:
            return model
    return None


def get_recommended_model() -> ModelConfig:
    """Get the recommended model configuration."""
    for model in AVAILABLE_MODELS:
        if model.recommended:
            return model
    return AVAILABLE_MODELS[0]


# ============================================================================
# API Key Access (raw SQLite - works everywhere)
# ============================================================================

@dataclass
class APIKeyInfo:
    """Lightweight API key info for V2 engine."""
    id: int
    key: str
    name: str
    is_active: bool
    is_exhausted: bool
    total_requests: int
    failed_requests: int
    last_used_at: Optional[datetime]
    requests_this_minute: int
    minute_window_start: Optional[datetime]


def get_active_api_keys(db_path: str) -> list[APIKeyInfo]:
    """
    Get all active (non-exhausted) API keys from the database.
    
    Args:
        db_path: Path to the voice_notes.db SQLite database
        
    Returns:
        List of APIKeyInfo objects for active keys
    """
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.execute("""
            SELECT id, key, name, is_active, is_exhausted, 
                   total_requests, failed_requests, last_used_at,
                   requests_this_minute, minute_window_start
            FROM api_keys 
            WHERE is_active = 1 AND (is_exhausted = 0 OR is_exhausted IS NULL)
            ORDER BY total_requests ASC
        """)
        
        keys = []
        for row in cursor.fetchall():
            keys.append(APIKeyInfo(
                id=row['id'],
                key=row['key'],
                name=row['name'] or f"Key {row['id']}",
                is_active=bool(row['is_active']),
                is_exhausted=bool(row['is_exhausted']),
                total_requests=row['total_requests'] or 0,
                failed_requests=row['failed_requests'] or 0,
                last_used_at=datetime.fromisoformat(row['last_used_at']) if row['last_used_at'] else None,
                requests_this_minute=row['requests_this_minute'] or 0,
                minute_window_start=datetime.fromisoformat(row['minute_window_start']) if row['minute_window_start'] else None,
            ))
        
        conn.close()
        
        if keys:
            logger.debug(f"Loaded {len(keys)} active API key(s) from database")
        
        return keys
        
    except Exception as e:
        logger.error(f"Failed to read API keys from database: {e}")
        return []


def get_api_key_strings(db_path: str) -> list[str]:
    """
    Get just the API key strings (for simple use cases).
    
    Args:
        db_path: Path to the voice_notes.db SQLite database
        
    Returns:
        List of API key strings
    """
    keys = get_active_api_keys(db_path)
    return [k.key for k in keys]


def mark_key_used(db_path: str, key_id: int, success: bool = True):
    """
    Update usage statistics for a key.
    
    Args:
        db_path: Path to the voice_notes.db SQLite database
        key_id: The ID of the key that was used
        success: Whether the request was successful
    """
    try:
        conn = sqlite3.connect(db_path)
        now = datetime.utcnow()
        
        # Get current state
        cursor = conn.execute(
            "SELECT minute_window_start, requests_this_minute FROM api_keys WHERE id = ?",
            (key_id,)
        )
        row = cursor.fetchone()
        if not row:
            conn.close()
            return
            
        minute_window_start = row[0]
        requests_this_minute = row[1] or 0
        
        # Calculate new values
        if not minute_window_start:
            # Start new window
            new_window_start = now.isoformat()
            new_requests = 1
        else:
            window_start = datetime.fromisoformat(minute_window_start)
            window_age = (now - window_start).total_seconds()
            if window_age >= 60:
                # New window
                new_window_start = now.isoformat()
                new_requests = 1
            else:
                # Same window
                new_window_start = minute_window_start
                new_requests = requests_this_minute + 1
        
        # Update the key
        if success:
            conn.execute("""
                UPDATE api_keys SET 
                    last_used_at = ?,
                    total_requests = total_requests + 1,
                    minute_window_start = ?,
                    requests_this_minute = ?
                WHERE id = ?
            """, (now.isoformat(), new_window_start, new_requests, key_id))
        else:
            conn.execute("""
                UPDATE api_keys SET 
                    last_used_at = ?,
                    total_requests = total_requests + 1,
                    failed_requests = failed_requests + 1,
                    minute_window_start = ?,
                    requests_this_minute = ?
                WHERE id = ?
            """, (now.isoformat(), new_window_start, new_requests, key_id))
        
        conn.commit()
        conn.close()
        logger.debug(f"Updated key {key_id}: {new_requests} requests this minute")
        
    except Exception as e:
        logger.error(f"Failed to update key usage: {e}")


def mark_key_exhausted(db_path: str, key_id: int, error_message: str = None):
    """
    Mark a key as exhausted (quota exceeded).
    
    Args:
        db_path: Path to the voice_notes.db SQLite database
        key_id: The ID of the key to mark as exhausted
        error_message: Optional error message to store
    """
    try:
        conn = sqlite3.connect(db_path)
        now = datetime.utcnow()
        
        conn.execute("""
            UPDATE api_keys SET 
                is_exhausted = 1,
                exhausted_at = ?,
                last_error = ?
            WHERE id = ?
        """, (now.isoformat(), error_message, key_id))
        
        conn.commit()
        conn.close()
        logger.warning(f"Marked key {key_id} as exhausted: {error_message}")
        
    except Exception as e:
        logger.error(f"Failed to mark key exhausted: {e}")


def get_best_available_key(db_path: str, rpm_limit: int = 5) -> Optional[APIKeyInfo]:
    """
    Get the best available API key using smart load balancing.
    
    Selects the key with the most remaining capacity for this minute.
    
    Args:
        db_path: Path to the voice_notes.db SQLite database
        rpm_limit: Requests per minute limit for the model
        
    Returns:
        The best available APIKeyInfo, or None if all keys are busy/exhausted
    """
    keys = get_active_api_keys(db_path)
    if not keys:
        return None
    
    now = datetime.utcnow()
    
    # Calculate remaining capacity for each key
    key_capacities = []
    for key in keys:
        remaining = _get_remaining_capacity(key, now, rpm_limit)
        if remaining > 0:
            key_capacities.append((key, remaining))
    
    if not key_capacities:
        logger.warning("All API keys at capacity for this minute")
        return None
    
    # Sort by remaining capacity (descending) to pick the least loaded key
    key_capacities.sort(key=lambda x: x[1], reverse=True)
    best_key = key_capacities[0][0]
    
    logger.debug(f"Selected key '{best_key.name}' with {key_capacities[0][1]} remaining capacity")
    return best_key


def _get_remaining_capacity(key: APIKeyInfo, now: datetime, rpm_limit: int) -> int:
    """Calculate remaining requests for a key in the current minute window."""
    if not key.minute_window_start:
        return rpm_limit
    
    window_age = (now - key.minute_window_start).total_seconds()
    if window_age >= 60:
        return rpm_limit
    
    return max(0, rpm_limit - key.requests_this_minute)


# ============================================================================
# Quota Error Detection
# ============================================================================

QUOTA_ERROR_MESSAGES = [
    "quota",
    "rate limit", 
    "resource exhausted",
    "429",
    "too many requests"
]


def is_quota_error(error: Exception) -> bool:
    """Check if an error is a quota/rate limit error."""
    error_str = str(error).lower()
    return any(msg in error_str for msg in QUOTA_ERROR_MESSAGES)
