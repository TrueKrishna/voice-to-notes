"""
Obsidian-native markdown note generation.

Builds notes with YAML frontmatter, structured content from AI,
full transcript, and link placeholders for future backlink support.

V2 Enhanced: Dual output (transcript + structured note), DD_MM_YY naming,
cross-linking between files, task extraction support.
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from .models import ProcessingResult, NoteStatus
from .titlegen import slugify

logger = logging.getLogger(__name__)


def get_filename_base(result: ProcessingResult, date_format: str = "YYYY_MM_DD_HH_MM") -> tuple[str, datetime]:
    """Generate the base filename (without extension) in date_slug format.
    
    Args:
        result: ProcessingResult with title and metadata
        date_format: Format string. Supported values:
            - "YYYY_MM_DD_HH_MM" (default): 2026_02_16_14_30
            - "DD_MM_YY": 25_01_25
            - "YYYY-MM-DD": 2025-01-25
            - "MM-DD-YYYY": 01-25-2025
            - "YYMMDD": 250125
    
    Returns:
        Tuple of (filename_base, timestamp_used)
    """
    # Prefer the original recording timestamp
    ts = result.metadata.recorded_at or result.created_at
    if ts is None:
        ts = datetime.utcnow()
    
    slug = slugify(result.title)
    
    # Map format names to strftime patterns
    format_map = {
        "YYYY_MM_DD_HH_MM": "%Y_%m_%d_%H_%M",
        "DD_MM_YY": "%d_%m_%y",
        "YYYY-MM-DD": "%Y-%m-%d",
        "MM-DD-YYYY": "%m-%d-%Y",
        "YYMMDD": "%y%m%d",
    }
    strftime_fmt = format_map.get(date_format, "%Y_%m_%d_%H_%M")
    
    filename_base = f"{ts.strftime(strftime_fmt)}_{slug}"
    
    return filename_base, ts


def _resolve_path_collision(path: Path) -> Path:
    """Handle filename collision by appending _1, _2, etc."""
    if not path.exists():
        return path
    
    stem = path.stem
    suffix = path.suffix
    counter = 1
    while path.exists():
        path = path.parent / f"{stem}_{counter}{suffix}"
        counter += 1
    return path


# =============================================================================
# TRANSCRIPT OUTPUT (Raw verbatim transcript)
# =============================================================================

def build_transcript_note(result: ProcessingResult, engine_version: str = "2.0.0", date_format: str = "YYYY_MM_DD_HH_MM") -> str:
    """Build a minimal transcript-only markdown file.
    
    Format:
        ---
        id: <uuid>
        type: transcript
        created_at: <ISO timestamp>
        source: voice
        audio_file: <filename>
        duration: <seconds>
        note: "[[Inbox/DD_MM_YY_slug]]"
        ---
        
        # Transcript: <Title>
        
        <full verbatim transcript>
    """
    filename_base, _ = get_filename_base(result, date_format)
    
    lines = ["---"]
    lines.append(f"id: {result.id}")
    lines.append("type: transcript")
    lines.append(f"created_at: {result.created_at.isoformat()}")
    lines.append("source: voice")
    lines.append(f"audio_file: \"{result.source_file}\"")
    
    if result.metadata.duration is not None:
        lines.append(f"duration: {result.metadata.duration:.1f}")
    
    lines.append(f"engine_version: {engine_version}")
    # Cross-link to the structured note
    lines.append(f"note: \"[[Inbox/{filename_base}]]\"")
    lines.append("---")
    lines.append("")
    lines.append(f"# Transcript: {result.title}")
    lines.append("")
    lines.append(result.transcript)
    
    return "\n".join(lines)


def save_transcript(
    result: ProcessingResult,
    transcripts_dir: Path,
    engine_version: str = "2.0.0",
    date_format: str = "YYYY_MM_DD_HH_MM",
) -> Path:
    """Save the raw transcript to the Transcripts folder.
    
    Returns the path where the transcript was saved.
    """
    filename_base, _ = get_filename_base(result, date_format)
    transcript_path = transcripts_dir / f"{filename_base}.md"
    transcript_path = _resolve_path_collision(transcript_path)
    
    transcripts_dir.mkdir(parents=True, exist_ok=True)
    content = build_transcript_note(result, engine_version, date_format)
    transcript_path.write_text(content, encoding="utf-8")
    
    logger.info(f"Transcript saved: {transcript_path}")
    return transcript_path


# =============================================================================
# INBOX / STRUCTURED NOTE OUTPUT
# =============================================================================

def build_inbox_note(
    result: ProcessingResult, 
    engine_version: str = "2.0.0",
    transcript_path: Optional[Path] = None,
    date_format: str = "YYYY_MM_DD_HH_MM",
) -> str:
    """Build a complete Obsidian-compatible structured note for Inbox.

    Format:
        ---
        id: <uuid>
        type: voice-note
        created_at: <ISO timestamp>
        recorded: <date>
        processed: <ISO timestamp>
        source: voice
        audio_file: <filename>
        duration: <seconds>
        duration_min: <minutes>
        mode: <processing mode>
        status: inbox
        has_tasks: true/false
        tags: []
        transcript: "[[Transcripts/DD_MM_YY_slug]]"
        engine_version: <semver>
        ---

        # <Title>

        ## Summary / Key Ideas / etc. (from AI structuring)

        ---
        
        > **Source**: [[Transcripts/DD_MM_YY_slug|View full transcript]]
    """
    filename_base, ts = get_filename_base(result, date_format)
    
    # Build frontmatter
    lines = ["---"]
    lines.append(f"id: {result.id}")
    lines.append("type: voice-note")
    lines.append(f"created_at: {result.created_at.isoformat()}")
    lines.append(f"recorded: {ts.strftime('%Y-%m-%d')}")
    
    if result.processed_at:
        lines.append(f"processed: {result.processed_at.isoformat()}")
    
    lines.append("source: voice")
    lines.append(f"audio_file: \"{result.source_file}\"")
    
    if result.metadata.duration is not None:
        lines.append(f"duration: {result.metadata.duration:.1f}")
        lines.append(f"duration_min: {int(result.metadata.duration // 60)}")
    
    lines.append(f"mode: {result.mode.value}")
    lines.append(f"status: {result.status.value}")
    lines.append(f"has_tasks: {str(result.has_tasks).lower()}")
    
    if result.tags:
        tags_str = ", ".join(f'"{t}"' for t in result.tags)
        lines.append(f"tags: [{tags_str}]")
    else:
        lines.append("tags: []")
    
    # Cross-link to transcript
    lines.append(f"transcript: \"[[Transcripts/{filename_base}]]\"")
    lines.append(f"engine_version: {engine_version}")
    lines.append("---")
    
    # Content
    parts = [
        "\n".join(lines),
        "",
        f"# {result.title}",
        "",
        result.structured_content,
        "",
        "---",
        "",
        f"> **Source**: [[Transcripts/{filename_base}|View full transcript]]",
        "",
    ]
    
    return "\n".join(parts)


def save_inbox_note(
    result: ProcessingResult,
    inbox_dir: Path,
    engine_version: str = "2.0.0",
    transcript_path: Optional[Path] = None,
    date_format: str = "YYYY_MM_DD_HH_MM",
) -> Path:
    """Save the structured note to the Inbox folder.
    
    Returns the path where the note was saved.
    """
    filename_base, _ = get_filename_base(result, date_format)
    inbox_path = inbox_dir / f"{filename_base}.md"
    inbox_path = _resolve_path_collision(inbox_path)
    
    inbox_dir.mkdir(parents=True, exist_ok=True)
    content = build_inbox_note(result, engine_version, transcript_path, date_format)
    inbox_path.write_text(content, encoding="utf-8")
    
    logger.info(f"Note saved: {inbox_path}")
    return inbox_path


# =============================================================================
# COMBINED SAVE (Both transcript + inbox note)
# =============================================================================

def save_dual_output(
    result: ProcessingResult,
    inbox_dir: Path,
    transcripts_dir: Path,
    engine_version: str = "2.0.0",
    date_format: str = "YYYY_MM_DD_HH_MM",
) -> tuple[Path, Path]:
    """Save both transcript and structured note.
    
    Args:
        result: ProcessingResult with all extracted data
        inbox_dir: Path to save the structured note
        transcripts_dir: Path to save the raw transcript
        engine_version: Semver string for metadata
        date_format: Filename date format (DD_MM_YY, YYYY-MM-DD, etc.)
    
    Returns:
        Tuple of (transcript_path, inbox_path)
    """
    # Save transcript first
    transcript_path = save_transcript(result, transcripts_dir, engine_version, date_format)
    result.transcript_path = transcript_path
    
    # Save inbox note with cross-link
    inbox_path = save_inbox_note(result, inbox_dir, engine_version, transcript_path, date_format)
    result.inbox_path = inbox_path
    result.note_path = inbox_path  # For legacy compatibility
    
    return transcript_path, inbox_path


# =============================================================================
# LEGACY COMPATIBILITY
# =============================================================================

def build_note(result: ProcessingResult, engine_version: str = "2.0.0") -> str:
    """Legacy: Build a complete note (calls build_inbox_note)."""
    return build_inbox_note(result, engine_version)


def get_note_path(result: ProcessingResult, output_dir: Path) -> Path:
    """Legacy: Generate the file path for a note.
    
    Now uses DD_MM_YY format instead of YYYY-MM-DD.
    """
    filename_base, _ = get_filename_base(result)
    return output_dir / f"{filename_base}.md"


def save_note(
    result: ProcessingResult,
    output_dir: Path,
    engine_version: str = "2.0.0",
) -> Path:
    """Legacy: Save note to output_dir (single output mode)."""
    note_content = build_inbox_note(result, engine_version)
    note_path = get_note_path(result, output_dir)
    note_path = _resolve_path_collision(note_path)
    
    output_dir.mkdir(parents=True, exist_ok=True)
    note_path.write_text(note_content, encoding="utf-8")
    logger.info(f"Note saved: {note_path}")
    return note_path


def _build_frontmatter(result: ProcessingResult, engine_version: str) -> str:
    """Legacy: Build YAML frontmatter block."""
    # Delegate to build_inbox_note's frontmatter
    lines = ["---"]
    lines.append(f"id: {result.id}")
    lines.append(f"created_at: {result.created_at.isoformat()}")
    lines.append("source: voice")
    lines.append(f"audio_file: \"{result.source_file}\"")
    if result.metadata.duration is not None:
        lines.append(f"duration: {result.metadata.duration:.1f}")
    lines.append(f"engine_version: {engine_version}")
    lines.append(f"mode: {result.mode.value}")
    if result.tags:
        tags_str = ", ".join(f'"{t}"' for t in result.tags)
        lines.append(f"tags: [{tags_str}]")
    else:
        lines.append("tags: []")
    lines.append("---")
    return "\n".join(lines)
