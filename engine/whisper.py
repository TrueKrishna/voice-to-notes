"""
OpenAI transcription client — supports whisper-1 and gpt-4o-transcribe models.

Provides the same interface as GeminiClient.transcribe() for drop-in use
in the processing pipeline. Only handles transcription (audio → text).
Structuring (text → structured note) still uses Gemini.

Models:
    whisper-1          — $0.006/min, 25MB limit, fast and affordable
    gpt-4o-transcribe  — $0.06/min, 25MB limit, ChatGPT-quality transcription
"""

import time
import logging
from pathlib import Path

from openai import OpenAI, APIError, RateLimitError, APIConnectionError

logger = logging.getLogger(__name__)

# OpenAI audio API has a 25MB file size limit
MAX_FILE_SIZE_MB = 25
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024

# Retry configuration
MAX_RETRIES = 5
INITIAL_BACKOFF_SECONDS = 2


class OpenAITranscriber:
    """OpenAI audio transcription client with retry logic.

    Supports whisper-1 and gpt-4o-transcribe models.
    Handles rate limits with exponential backoff.
    """

    def __init__(self, api_key: str, model: str = "whisper-1"):
        if not api_key:
            raise ValueError("OpenAI API key is required")
        if model not in ("whisper-1", "gpt-4o-transcribe"):
            raise ValueError(f"Unsupported OpenAI transcription model: {model}. "
                             f"Use 'whisper-1' or 'gpt-4o-transcribe'.")
        self._client = OpenAI(api_key=api_key)
        self._model = model
        logger.info(f"OpenAI transcriber initialized | model={model}")

    def transcribe(self, audio_path: Path, prompt: str = "", max_retries: int = MAX_RETRIES) -> str:
        """Transcribe an audio file using OpenAI's audio API.

        Args:
            audio_path: Path to the audio file (mp3, m4a, wav, opus, etc.)
            prompt: Optional prompt to guide transcription style/vocabulary.
            max_retries: Maximum number of retry attempts on transient errors.

        Returns:
            Transcribed text as a string.

        Raises:
            ValueError: If the file exceeds the 25MB size limit.
            Exception: If all retries are exhausted.
        """
        audio_path = Path(audio_path)

        # Check file size
        file_size = audio_path.stat().st_size
        if file_size > MAX_FILE_SIZE_BYTES:
            size_mb = file_size / (1024 * 1024)
            raise ValueError(
                f"Audio file is {size_mb:.1f}MB — exceeds OpenAI's {MAX_FILE_SIZE_MB}MB limit. "
                f"Ensure audio compression is enabled (current file: {audio_path.name})."
            )

        logger.info(f"Transcribing with OpenAI {self._model}: {audio_path.name} "
                     f"({file_size / (1024 * 1024):.1f}MB)")

        last_error = None
        for attempt in range(1, max_retries + 1):
            try:
                with open(audio_path, "rb") as audio_file:
                    response = self._client.audio.transcriptions.create(
                        file=audio_file,
                        model=self._model,
                        prompt=prompt if prompt else None,
                        response_format="text",
                    )

                # response is a string when response_format="text"
                transcript = response.strip() if isinstance(response, str) else response.text.strip()

                if not transcript:
                    raise ValueError("OpenAI returned an empty transcript")

                logger.info(f"Transcription complete | {len(transcript)} chars | model={self._model}")
                return transcript

            except RateLimitError as e:
                last_error = e
                wait = INITIAL_BACKOFF_SECONDS * (2 ** (attempt - 1))
                logger.warning(f"Rate limited (attempt {attempt}/{max_retries}), "
                               f"waiting {wait}s: {e}")
                time.sleep(wait)

            except APIConnectionError as e:
                last_error = e
                wait = INITIAL_BACKOFF_SECONDS * (2 ** (attempt - 1))
                logger.warning(f"Connection error (attempt {attempt}/{max_retries}), "
                               f"retrying in {wait}s: {e}")
                time.sleep(wait)

            except APIError as e:
                last_error = e
                # Don't retry on 4xx errors (except 429 which is RateLimitError)
                if hasattr(e, 'status_code') and e.status_code and 400 <= e.status_code < 500:
                    logger.error(f"OpenAI API error (non-retryable): {e}")
                    raise
                wait = INITIAL_BACKOFF_SECONDS * (2 ** (attempt - 1))
                logger.warning(f"API error (attempt {attempt}/{max_retries}), "
                               f"retrying in {wait}s: {e}")
                time.sleep(wait)

            except Exception as e:
                last_error = e
                logger.error(f"Unexpected error during transcription: {e}")
                raise

        # All retries exhausted
        raise RuntimeError(
            f"OpenAI transcription failed after {max_retries} attempts. "
            f"Last error: {last_error}"
        )
