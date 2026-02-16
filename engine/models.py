"""
Data models for the processing engine.
No external dependencies — pure Python dataclasses.
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional


class ProcessingMode(str, Enum):
    """Processing modes determine AI prompt strategy."""
    PERSONAL_NOTE = "personal_note"
    IDEA = "idea"
    MEETING = "meeting"
    REFLECTION = "reflection"
    TASK_DUMP = "task_dump"

class NoteStatus(str, Enum):
    """Status of a note in the processing pipeline."""
    INBOX = "inbox"           # Just processed, pending review
    REVIEWED = "reviewed"     # User has reviewed/tagged
    ARCHIVED = "archived"     # No longer active


@dataclass
class ExtractedTask:
    """A task extracted from a voice recording."""
    text: str
    due_date: Optional[str] = None
    assignee: Optional[str] = None
    priority: Optional[str] = None  # high, medium, low
    completed: bool = False

@dataclass
class AudioMetadata:
    """Metadata extracted from audio file via ffprobe."""
    duration: Optional[float] = None
    sample_rate: Optional[int] = None
    bit_rate: Optional[int] = None
    channels: Optional[int] = None
    codec: Optional[str] = None
    recorded_at: Optional[datetime] = None


@dataclass
class ProcessingResult:
    """Complete result of processing an audio file."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source_file: str = ""
    mode: ProcessingMode = ProcessingMode.PERSONAL_NOTE

    # Audio
    metadata: AudioMetadata = field(default_factory=AudioMetadata)
    original_size_mb: float = 0.0
    compressed_size_mb: float = 0.0
    compressed_path: Optional[Path] = None

    # AI output
    transcript: str = ""
    structured_content: str = ""
    title: str = ""
    tags: list[str] = field(default_factory=list)
    
    # Extracted tasks
    tasks: list[ExtractedTask] = field(default_factory=list)
    has_tasks: bool = False

    # Output paths (dual output)
    transcript_path: Optional[Path] = None  # Raw transcript file
    inbox_path: Optional[Path] = None       # Structured note in Inbox
    note_path: Optional[Path] = None        # Legacy: same as inbox_path
    audio_path: Optional[Path] = None       # Stored compressed audio
    status: NoteStatus = NoteStatus.INBOX

    # Timing
    created_at: datetime = field(default_factory=datetime.utcnow)
    processed_at: Optional[datetime] = None

    # Status
    success: bool = False
    error: Optional[str] = None
