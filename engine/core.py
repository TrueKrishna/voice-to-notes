"""
Core processing pipeline orchestrator.

This is the main entry point for processing audio files.
Pure function interface — no FastAPI, no ORM, no database dependency.

V2 Enhanced: Dual output (transcript + structured note), task extraction,
daily task aggregation support.

Usage:
    from engine import process_audio, ProcessingMode

    result = process_audio("recording.m4a", mode="personal_note")
    print(result.title, result.inbox_path, result.transcript_path)
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from .config import EngineConfig, load_config
from .models import ProcessingMode, ProcessingResult, NoteStatus
from .audio import check_ffmpeg, get_audio_metadata, compress_audio
from .ai import GeminiClient
from .prompts import get_transcription_prompt, get_structuring_prompt, get_task_extraction_prompt
from .titlegen import parse_title_and_content, fallback_title
from .markdown import save_dual_output, save_note

logger = logging.getLogger(__name__)


def process_audio(
    file_path: str | Path,
    mode: str = "personal_note",
    config: Optional[EngineConfig] = None,
    extract_tasks: bool = True,
) -> ProcessingResult:
    """Process an audio file through the complete pipeline.

    Pipeline:
        1. Extract audio metadata (ffprobe)
        2. Compress to Opus (ffmpeg)
        3. Transcribe with Gemini AI
        4. Generate structured breakdown with Gemini AI
        5. Extract tasks (optional)
        6. Save dual output: Transcript + Inbox note

    Args:
        file_path: Path to the audio file.
        mode: Processing mode — determines the AI structuring prompt.
              One of: personal_note, idea, meeting, reflection, task_dump
        config: Engine configuration. If None, loads from environment.
        extract_tasks: Whether to run task extraction (default: True).

    Returns:
        ProcessingResult with all outputs, metadata, and saved note paths.

    Raises:
        Exception: If any pipeline step fails after retries.
    """
    file_path = Path(file_path)
    config = config or load_config()
    proc_mode = ProcessingMode(mode)

    result = ProcessingResult(
        source_file=file_path.name,
        mode=proc_mode,
        status=NoteStatus.INBOX,
    )

    try:
        logger.info(f"{'=' * 60}")
        logger.info(f"Processing: {file_path.name}")
        logger.info(f"Mode: {proc_mode.value}")
        logger.info(f"{'=' * 60}")

        # ── Step 1: Audio metadata ──────────────────────────────────
        logger.info("Step 1/6 — Extracting audio metadata")
        result.metadata = get_audio_metadata(file_path)
        if result.metadata.duration:
            mins = int(result.metadata.duration // 60)
            secs = int(result.metadata.duration % 60)
            logger.info(f"  Duration: {mins}:{secs:02d}")
        if result.metadata.codec:
            logger.info(f"  Codec: {result.metadata.codec}")
        if result.metadata.recorded_at:
            logger.info(f"  Recorded: {result.metadata.recorded_at}")

        # ── Step 2: Compress ────────────────────────────────────────
        logger.info("Step 2/6 — Compressing audio (FFmpeg → Opus)")
        if check_ffmpeg():
            compressed_path, orig_mb, comp_mb = compress_audio(
                file_path, config.audio_bitrate
            )
            result.original_size_mb = orig_mb
            result.compressed_size_mb = comp_mb
            result.compressed_path = compressed_path
            audio_for_ai = compressed_path
        else:
            logger.warning("  FFmpeg not found — using original file")
            result.original_size_mb = file_path.stat().st_size / (1024 * 1024)
            result.compressed_size_mb = result.original_size_mb
            audio_for_ai = file_path

        # ── Step 3: Transcribe ──────────────────────────────────────
        logger.info("Step 3/6 — Transcribing with Gemini AI")
        client = GeminiClient(config.gemini_api_keys, config.gemini_model)
        transcription_prompt = get_transcription_prompt()
        result.transcript = client.transcribe(audio_for_ai, transcription_prompt)
        logger.info(f"  Transcript length: {len(result.transcript)} chars")

        # ── Step 4: Structure ───────────────────────────────────────
        logger.info("Step 4/6 — Generating structured breakdown")
        structuring_prompt = get_structuring_prompt(proc_mode)
        structured_output = client.structure(result.transcript, structuring_prompt)

        # Parse title from AI output
        title, content = parse_title_and_content(structured_output)
        result.title = title or fallback_title(result.transcript)
        result.structured_content = content
        logger.info(f"  Title: {result.title}")

        # ── Step 5: Extract Tasks ───────────────────────────────────
        if extract_tasks:
            logger.info("Step 5/6 — Extracting tasks")
            try:
                from .tasks import extract_tasks_from_content
                result.tasks = extract_tasks_from_content(
                    result.structured_content, 
                    result.transcript,
                    client
                )
                result.has_tasks = len(result.tasks) > 0
                logger.info(f"  Tasks found: {len(result.tasks)}")
            except Exception as e:
                logger.warning(f"  Task extraction failed (non-fatal): {e}")
                result.tasks = []
                result.has_tasks = False
        else:
            logger.info("Step 5/6 — Skipping task extraction")
            result.tasks = []
            result.has_tasks = False

        # ── Step 6: Save dual output to Obsidian ────────────────────
        logger.info("Step 6/6 — Saving to Obsidian vault (dual output)")
        
        transcript_path, inbox_path = save_dual_output(
            result,
            inbox_dir=config.inbox_dir,
            transcripts_dir=config.transcripts_dir,
            engine_version=config.engine_version,
        )
        
        result.transcript_path = transcript_path
        result.inbox_path = inbox_path
        result.note_path = inbox_path  # Legacy compatibility

        # Cleanup compressed temp file
        if result.compressed_path and result.compressed_path != file_path:
            try:
                result.compressed_path.unlink(missing_ok=True)
            except Exception:
                pass

        result.success = True
        result.processed_at = datetime.utcnow()

        logger.info(f"{'=' * 60}")
        logger.info(f"✅ Done: {file_path.name}")
        logger.info(f"   Transcript: {result.transcript_path}")
        logger.info(f"   Note: {result.inbox_path}")
        if result.has_tasks:
            logger.info(f"   Tasks: {len(result.tasks)} extracted")
        logger.info(f"{'=' * 60}")

        return result

    except Exception as e:
        result.error = str(e)
        logger.error(f"❌ Pipeline failed: {file_path.name} — {e}", exc_info=True)

        # Cleanup compressed temp
        if result.compressed_path and result.compressed_path != file_path:
            try:
                result.compressed_path.unlink(missing_ok=True)
            except Exception:
                pass

        raise
