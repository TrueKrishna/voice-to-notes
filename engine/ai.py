"""
Gemini AI client with automatic key rotation and retry logic.
No database dependency — manages keys in-memory with round-robin rotation.

Uses the new google-genai SDK (replaces deprecated google-generativeai).

Rate limit handling:
- On 429, waits for rate limit window to clear (60s max) instead of marking key exhausted
- Only marks key as "exhausted" after multiple consecutive 429s (truly exhausted quota)
"""

import time
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional

from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

# Error message markers for classification
_QUOTA_MARKERS = ["429", "quota", "rate limit", "resource exhausted", "too many requests"]
_NETWORK_MARKERS = ["broken pipe", "errno 32", "connection", "reset", "timeout"]
_DAILY_QUOTA_MARKERS = ["per_day", "perday", "daily", "quotaexceeded", "limit: 0"]  # Daily quota exhausted

# Rate limit configuration
RATE_LIMIT_WAIT_SECONDS = 15  # Wait time after hitting 429 before retrying same key
MAX_429_BEFORE_EXHAUST = 3     # Number of consecutive 429s before marking key exhausted


class GeminiClient:
    """Gemini API client with automatic key rotation on quota exhaustion.

    Supports multiple API keys with round-robin selection.
    On quota errors (429), waits for rate limit window to clear before retrying.
    On network errors, retries with exponential backoff.
    """

    def __init__(self, api_keys: list[str], model_name: str = "gemini-3-flash-preview"):
        if not api_keys:
            raise ValueError("At least one API key is required")
        self._keys = api_keys
        self._model_name = model_name
        self._key_index = 0
        self._exhausted: set[int] = set()
        self._key_cooldowns: dict[int, datetime] = {}  # key_idx -> cooldown_until
        self._key_429_counts: dict[int, int] = {}  # key_idx -> consecutive 429 count
        self._current_client: Optional[genai.Client] = None
        self._current_key_idx: Optional[int] = None

    def _get_available_key(self) -> tuple[int, str]:
        """Get the next available API key via round-robin.
        
        Respects cooldown periods for rate-limited keys.
        Waits if all keys are in cooldown but not exhausted.
        """
        now = datetime.utcnow()
        
        # Clear expired cooldowns
        expired = [idx for idx, until in self._key_cooldowns.items() if until <= now]
        for idx in expired:
            del self._key_cooldowns[idx]
            self._key_429_counts.pop(idx, None)  # Reset 429 count after cooldown
        
        # Get keys that are not exhausted AND not in cooldown
        available = [
            (i, k) for i, k in enumerate(self._keys) 
            if i not in self._exhausted and i not in self._key_cooldowns
        ]
        
        if available:
            idx = self._key_index % len(available)
            self._key_index += 1
            return available[idx]
        
        # All keys in cooldown but not exhausted - wait for the soonest one
        in_cooldown = [
            (i, k) for i, k in enumerate(self._keys) 
            if i not in self._exhausted and i in self._key_cooldowns
        ]
        
        if in_cooldown:
            # Find the key with the soonest cooldown expiry
            soonest_idx = min(in_cooldown, key=lambda x: self._key_cooldowns[x[0]])[0]
            wait_time = (self._key_cooldowns[soonest_idx] - now).total_seconds()
            if wait_time > 0:
                logger.info(f"⏳ All keys rate-limited. Waiting {wait_time:.0f}s for key {soonest_idx + 1} to become available...")
                time.sleep(wait_time + 1)  # +1 for safety margin
            
            # Remove from cooldown and return
            del self._key_cooldowns[soonest_idx]
            self._key_429_counts.pop(soonest_idx, None)
            return soonest_idx, self._keys[soonest_idx]
        
        # All keys truly exhausted (daily quota exceeded)
        raise Exception(
            "All API keys exhausted. Wait for quota reset or add more keys."
        )
    
    def _handle_rate_limit(self, key_idx: int, error: Exception = None):
        """Handle a 429 rate limit error for a key.
        
        If the error is a daily quota exhaustion, immediately marks the key 
        as exhausted (no point retrying a daily limit).
        Otherwise, puts key in cooldown. After MAX_429_BEFORE_EXHAUST consecutive 429s,
        marks the key as truly exhausted.
        """
        # Daily quota errors: immediately exhaust the key
        if error and self._is_daily_quota_error(error):
            logger.warning(f"🚫 Key {key_idx + 1} hit DAILY quota limit — marking exhausted immediately. Error: {str(error)[:120]}")
            self._exhausted.add(key_idx)
            self._key_cooldowns.pop(key_idx, None)
            self._key_429_counts.pop(key_idx, None)
            return
        
        self._key_429_counts[key_idx] = self._key_429_counts.get(key_idx, 0) + 1
        consecutive_429s = self._key_429_counts[key_idx]
        
        if consecutive_429s >= MAX_429_BEFORE_EXHAUST:
            logger.warning(f"🚫 Key {key_idx + 1} hit {consecutive_429s} consecutive 429s - marking as exhausted")
            self._exhausted.add(key_idx)
            self._key_cooldowns.pop(key_idx, None)
        else:
            cooldown_until = datetime.utcnow() + timedelta(seconds=RATE_LIMIT_WAIT_SECONDS)
            self._key_cooldowns[key_idx] = cooldown_until
            logger.warning(f"⏸️ Key {key_idx + 1} rate-limited ({consecutive_429s}/{MAX_429_BEFORE_EXHAUST}), cooldown until {cooldown_until.strftime('%H:%M:%S')}")

    def _get_client(self, key_idx: int, key: str) -> genai.Client:
        """Get or create a genai.Client for the given key."""
        if self._current_key_idx != key_idx:
            self._current_client = genai.Client(api_key=key)
            self._current_key_idx = key_idx
        return self._current_client

    @staticmethod
    def _is_quota_error(e: Exception) -> bool:
        s = str(e).lower()
        return any(m in s for m in _QUOTA_MARKERS)
    
    @staticmethod
    def _is_daily_quota_error(e: Exception) -> bool:
        """Check if error is specifically a daily quota exhaustion (not per-minute)."""
        s = str(e).lower().replace(" ", "").replace("_", "")
        return any(m in s for m in _DAILY_QUOTA_MARKERS)

    @staticmethod
    def _is_network_error(e: Exception) -> bool:
        s = str(e).lower()
        return any(m in s for m in _NETWORK_MARKERS)

    def transcribe(self, audio_path: Path, prompt: str, max_retries: int = 5) -> str:
        """Transcribe an audio file using Gemini.

        Uploads the file, sends with the prompt, and returns the transcription text.
        Handles key rotation and retries automatically.
        """
        last_error = None

        for attempt in range(max_retries):
            key_idx, key = self._get_available_key()
            client = self._get_client(key_idx, key)

            try:
                logger.info(
                    f"Transcribing {audio_path.name} "
                    f"(attempt {attempt + 1}/{max_retries}, key {key_idx + 1}/{len(self._keys)})"
                )

                # Upload audio file
                audio_file = client.files.upload(file=str(audio_path))
                try:
                    response = client.models.generate_content(
                        model=self._model_name,
                        contents=[prompt, audio_file],
                        config=types.GenerateContentConfig(
                            temperature=1.0,       # Google recommends 1.0 to avoid looping
                            top_p=0.95,
                            top_k=40,
                            max_output_tokens=65536,
                        ),
                    )
                finally:
                    # Always clean up the uploaded file
                    try:
                        client.files.delete(name=audio_file.name)
                    except Exception:
                        pass

                self._validate_response(response)
                self._key_429_counts.pop(key_idx, None)  # Clear 429 count on success
                logger.info(f"Transcription complete: {len(response.text)} chars")
                return response.text

            except Exception as e:
                last_error = e
                if self._is_quota_error(e):
                    self._handle_rate_limit(key_idx, error=e)
                    continue
                if self._is_network_error(e):
                    wait = min(5 * (2 ** attempt), 30)
                    logger.warning(f"Network error, retrying in {wait}s: {e}")
                    time.sleep(wait)
                    continue
                raise

        raise Exception(f"Transcription failed after {max_retries} attempts: {last_error}")

    def structure(self, transcript: str, prompt: str, max_retries: int = 5) -> str:
        """Generate a structured breakdown of a transcript.

        The prompt must contain {transcript} which will be replaced with the
        actual transcript text.
        """
        last_error = None
        full_prompt = prompt.replace("{transcript}", transcript)

        for attempt in range(max_retries):
            key_idx, key = self._get_available_key()
            client = self._get_client(key_idx, key)

            try:
                logger.info(
                    f"Structuring content "
                    f"(attempt {attempt + 1}/{max_retries}, key {key_idx + 1}/{len(self._keys)})"
                )

                response = client.models.generate_content(
                    model=self._model_name,
                    contents=full_prompt,
                    config=types.GenerateContentConfig(
                        temperature=1.0,
                        top_p=0.95,
                        top_k=40,
                        max_output_tokens=65536,
                    ),
                )

                self._validate_response(response)
                self._key_429_counts.pop(key_idx, None)  # Clear 429 count on success
                logger.info(f"Structuring complete: {len(response.text)} chars")
                return response.text

            except Exception as e:
                last_error = e
                if self._is_quota_error(e):
                    self._handle_rate_limit(key_idx, error=e)
                    continue
                if self._is_network_error(e):
                    wait = min(5 * (2 ** attempt), 30)
                    logger.warning(f"Network error, retrying in {wait}s: {e}")
                    time.sleep(wait)
                    continue
                raise

        raise Exception(f"Structuring failed after {max_retries} attempts: {last_error}")

    @staticmethod
    def _validate_response(response):
        """Validate a Gemini API response before accessing .text."""
        if not response:
            raise Exception("Empty response from Gemini API")

        # Check for candidates
        if not hasattr(response, "candidates") or not response.candidates:
            raise Exception("No candidates in Gemini response")

        # Check finish reason
        candidate = response.candidates[0]
        finish = getattr(candidate, "finish_reason", None)
        # In the new SDK, finish_reason is a string enum like "STOP", "MAX_TOKENS" etc.
        if finish and str(finish) not in ("STOP", "FinishReason.STOP", "UNSPECIFIED", "FinishReason.UNSPECIFIED", "0", "1"):
            if "MAX_TOKENS" in str(finish):
                logger.warning("Response hit max token limit — returning partial content")
                if hasattr(response, "text") and response.text:
                    return  # Accept partial
                raise Exception("Hit max tokens with no content")
            raise Exception(f"Abnormal finish reason: {finish}")

        # Check for empty text
        if not response.text or not response.text.strip():
            raise Exception("Empty text in Gemini response")
