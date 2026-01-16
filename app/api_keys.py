"""
API Key Management with automatic rotation and smart load balancing.
Handles quota exhaustion by switching to next available key.
Supports parallel recordings with capacity tracking.
"""

from datetime import datetime, timedelta
from typing import Optional
import logging

from sqlalchemy.orm import Session
from sqlalchemy import or_

import google.generativeai as genai

from .database import APIKey

logger = logging.getLogger(__name__)


class APIKeyManager:
    """Manages Gemini API keys with rotation on quota exhaustion."""
    
    # Gemini limits: 5 RPM (requests per minute) per key
    MAX_REQUESTS_PER_MINUTE = 5
    KEY_LOCK_SECONDS = 15  # Lock duration to prevent race conditions
    
    QUOTA_ERROR_MESSAGES = [
        "quota",
        "rate limit",
        "resource exhausted",
        "429",
        "too many requests"
    ]
    
    def __init__(self, db: Session):
        self.db = db
        self._current_key: Optional[APIKey] = None
        self._model = None
    
    def add_key(self, key: str, name: str = None) -> APIKey:
        """Add a new API key to the pool."""
        api_key = APIKey(
            key=key,
            name=name or f"Key {self.get_key_count() + 1}",
            is_active=True,
            is_exhausted=False
        )
        self.db.add(api_key)
        self.db.commit()
        self.db.refresh(api_key)
        return api_key
    
    def get_key_count(self) -> int:
        """Get total number of keys."""
        return self.db.query(APIKey).count()
    
    def get_active_keys(self) -> list[APIKey]:
        """Get all active (non-exhausted) keys."""
        return self.db.query(APIKey).filter(
            APIKey.is_active == True,
            APIKey.is_exhausted == False
        ).all()
    
    def get_all_keys(self) -> list[APIKey]:
        """Get all keys including exhausted ones."""
        return self.db.query(APIKey).order_by(APIKey.created_at.desc()).all()
    
    def get_next_available_key(self) -> Optional[APIKey]:
        """Get the next available API key with smart load balancing.
        
        Uses a capacity-aware round-robin approach:
        1. Filters out locked keys (prevents race conditions)
        2. Filters out keys at max capacity for this minute
        3. Orders by remaining capacity (least used first)
        
        Returns the best available key, or None if all are busy/exhausted.
        """
        now = datetime.utcnow()
        
        # Get all active, non-exhausted keys
        available_keys = self.db.query(APIKey).filter(
            APIKey.is_active == True,
            APIKey.is_exhausted == False,
            # Not locked, or lock has expired
            or_(
                APIKey.locked_until == None,
                APIKey.locked_until < now
            )
        ).all()
        
        if not available_keys:
            logger.warning("⚠️ No available API keys (all locked or exhausted)")
            return None
        
        # Calculate remaining capacity for each key
        key_capacities = []
        for key in available_keys:
            remaining = self._get_remaining_capacity(key, now)
            if remaining > 0:
                key_capacities.append((key, remaining))
                logger.debug(f"🔑 Key '{key.name}' has {remaining}/{self.MAX_REQUESTS_PER_MINUTE} capacity remaining")
        
        if not key_capacities:
            logger.warning("⚠️ All API keys at capacity for this minute")
            return None
        
        # Sort by remaining capacity (descending) to pick the least loaded key
        key_capacities.sort(key=lambda x: x[1], reverse=True)
        best_key = key_capacities[0][0]
        
        logger.info(f"🎯 Selected key '{best_key.name}' with {key_capacities[0][1]} remaining capacity")
        return best_key
    
    def _get_remaining_capacity(self, key: APIKey, now: datetime) -> int:
        """Calculate remaining requests for a key in the current minute window."""
        # If no window set or window has passed, key has full capacity
        if not key.minute_window_start:
            return self.MAX_REQUESTS_PER_MINUTE
        
        # Check if we're in a new minute window
        window_age = (now - key.minute_window_start).total_seconds()
        if window_age >= 60:
            # Window expired, reset tracking
            key.requests_this_minute = 0
            key.minute_window_start = None
            self.db.commit()
            return self.MAX_REQUESTS_PER_MINUTE
        
        # Return remaining capacity
        return max(0, self.MAX_REQUESTS_PER_MINUTE - (key.requests_this_minute or 0))
    
    def acquire_key_lock(self, api_key: APIKey) -> bool:
        """Acquire a temporary lock on a key to prevent race conditions.
        
        Returns True if lock acquired, False if key was grabbed by another process.
        """
        now = datetime.utcnow()
        
        # Refresh the key to get latest state
        self.db.refresh(api_key)
        
        # Check if someone else locked it
        if api_key.locked_until and api_key.locked_until > now:
            logger.warning(f"🔒 Key '{api_key.name}' already locked until {api_key.locked_until}")
            return False
        
        # Acquire lock
        api_key.locked_until = now + timedelta(seconds=self.KEY_LOCK_SECONDS)
        self.db.commit()
        logger.debug(f"🔐 Acquired lock on key '{api_key.name}' until {api_key.locked_until}")
        return True
    
    def release_key_lock(self, api_key: APIKey):
        """Release the lock on a key."""
        api_key.locked_until = None
        self.db.commit()
        logger.debug(f"🔓 Released lock on key '{api_key.name}'")
    
    def mark_key_exhausted(self, api_key: APIKey, error_message: str = None):
        """Mark a key as exhausted (quota exceeded)."""
        api_key.is_exhausted = True
        api_key.exhausted_at = datetime.utcnow()
        api_key.last_error = error_message
        self.db.commit()
        
        # Clear current model so we get a new key next time
        self._current_key = None
        self._model = None
    
    def mark_key_used(self, api_key: APIKey, success: bool = True):
        """Update usage statistics for a key and track rate limiting."""
        now = datetime.utcnow()
        api_key.last_used_at = now
        api_key.total_requests += 1
        
        if not success:
            api_key.failed_requests += 1
        
        # Track requests per minute for rate limiting
        if not api_key.minute_window_start:
            # Start new window
            api_key.minute_window_start = now
            api_key.requests_this_minute = 1
        else:
            window_age = (now - api_key.minute_window_start).total_seconds()
            if window_age >= 60:
                # New window
                api_key.minute_window_start = now
                api_key.requests_this_minute = 1
            else:
                # Same window, increment
                api_key.requests_this_minute = (api_key.requests_this_minute or 0) + 1
        
        # Release the lock after use
        api_key.locked_until = None
        
        self.db.commit()
        logger.debug(f"📊 Key '{api_key.name}' used: {api_key.requests_this_minute}/{self.MAX_REQUESTS_PER_MINUTE} this minute")
    
    def reset_key(self, key_id: int) -> bool:
        """Reset an exhausted key (e.g., after quota resets)."""
        api_key = self.db.query(APIKey).filter(APIKey.id == key_id).first()
        if api_key:
            api_key.is_exhausted = False
            api_key.exhausted_at = None
            api_key.last_error = None
            self.db.commit()
            return True
        return False
    
    def reset_all_keys(self):
        """Reset all exhausted keys."""
        self.db.query(APIKey).update({
            APIKey.is_exhausted: False,
            APIKey.exhausted_at: None,
            APIKey.last_error: None
        })
        self.db.commit()
    
    def delete_key(self, key_id: int) -> bool:
        """Delete an API key."""
        api_key = self.db.query(APIKey).filter(APIKey.id == key_id).first()
        if api_key:
            self.db.delete(api_key)
            self.db.commit()
            return True
        return False
    
    def toggle_key(self, key_id: int) -> bool:
        """Toggle a key's active status."""
        api_key = self.db.query(APIKey).filter(APIKey.id == key_id).first()
        if api_key:
            api_key.is_active = not api_key.is_active
            self.db.commit()
            return True
        return False
    
    def is_quota_error(self, error: Exception) -> bool:
        """Check if an error is a quota/rate limit error."""
        error_str = str(error).lower()
        return any(msg in error_str for msg in self.QUOTA_ERROR_MESSAGES)
    
    def get_model(self, model_name: str = "gemini-3-flash-preview"):
        """Get a Gemini model configured with an available API key.
        
        Uses smart load balancing with capacity tracking.
        Using gemini-3-flash-preview for both transcription and breakdown (5 RPM, 250K TPM).
        """
        # If model name changed, clear cache
        if self._model and hasattr(self, '_model_name') and self._model_name != model_name:
            self._model = None
        
        # If we already have a working model with same name, return it
        if self._model and self._current_key and hasattr(self, '_model_name') and self._model_name == model_name:
            # Check if current key still has capacity
            remaining = self._get_remaining_capacity(self._current_key, datetime.utcnow())
            if remaining > 0:
                return self._model, self._current_key
            else:
                logger.info(f"🔄 Current key '{self._current_key.name}' at capacity, switching...")
                self._model = None
                self._current_key = None
        
        # Get next available key with load balancing
        api_key = self.get_next_available_key()
        if not api_key:
            raise Exception("No available API keys. All keys are either exhausted or at capacity. Please wait or add more keys.")
        
        # Acquire lock to prevent race conditions
        if not self.acquire_key_lock(api_key):
            # Someone else grabbed this key, try again
            api_key = self.get_next_available_key()
            if not api_key or not self.acquire_key_lock(api_key):
                raise Exception("All API keys are busy. Please wait a moment.")
        
        # Configure Gemini
        genai.configure(api_key=api_key.key)
        self._model = genai.GenerativeModel(model_name)
        self._current_key = api_key
        self._model_name = model_name
        
        logger.info(f"✅ Configured Gemini with key '{api_key.name}' for model {model_name}")
        return self._model, api_key
    
    def handle_error(self, error: Exception, api_key: APIKey) -> bool:
        """
        Handle an API error. Returns True if we should retry with a new key.
        """
        self.mark_key_used(api_key, success=False)
        
        if self.is_quota_error(error):
            self.mark_key_exhausted(api_key, str(error))
            
            # Check if we have more keys
            if self.get_next_available_key():
                return True  # Retry with new key
        
        return False  # Don't retry
    
    def get_status(self) -> dict:
        """Get overall API key status with capacity info."""
        all_keys = self.get_all_keys()
        active_keys = [k for k in all_keys if k.is_active and not k.is_exhausted]
        exhausted_keys = [k for k in all_keys if k.is_exhausted]
        
        now = datetime.utcnow()
        total_capacity = 0
        used_capacity = 0
        
        for key in active_keys:
            remaining = self._get_remaining_capacity(key, now)
            total_capacity += self.MAX_REQUESTS_PER_MINUTE
            used_capacity += (self.MAX_REQUESTS_PER_MINUTE - remaining)
        
        return {
            "total_keys": len(all_keys),
            "active_keys": len(active_keys),
            "exhausted_keys": len(exhausted_keys),
            "has_available_key": len(active_keys) > 0,
            "total_capacity_per_minute": total_capacity,
            "used_capacity_this_minute": used_capacity,
            "remaining_capacity": total_capacity - used_capacity
        }
    
    def get_estimated_wait_time(self, queue_position: int) -> int:
        """Estimate wait time in seconds based on queue position and available capacity.
        
        Gemini processes ~1 request per 12 seconds average, so with 5 RPM per key:
        - 1 key = 5 requests/minute = can process ~5 recordings concurrently
        - Wait time = (queue_position / total_capacity) * 60 seconds
        """
        status = self.get_status()
        capacity = status["remaining_capacity"]
        
        if capacity <= 0:
            # All keys at capacity, estimate based on minute window reset
            return 60  # Max wait is 60 seconds for window to reset
        
        if queue_position <= capacity:
            return 0  # No wait, capacity available
        
        # Estimate based on how many minute windows we need to wait
        windows_to_wait = (queue_position - capacity) // status["total_capacity_per_minute"]
        return windows_to_wait * 60
