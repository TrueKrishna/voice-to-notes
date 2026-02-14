"""
Voice-to-Notes Engine V2

Standalone audio processing pipeline.
Google Drive → Processing → Obsidian Vault

V2 Enhanced: Dual output (transcript + structured note), task extraction,
daily/weekly rollups, tag-based routing.

No FastAPI or database dependency.
Pure function interface: process_audio(file_path, mode) -> ProcessingResult
"""

__version__ = "2.1.0"

from .core import process_audio
from .models import (
    ProcessingMode, 
    ProcessingResult, 
    AudioMetadata,
    NoteStatus,
    ExtractedTask,
)
from .tasks import (
    extract_tasks_from_content,
    append_tasks_to_daily_file,
    get_tasks_for_date,
    count_tasks_for_date,
)
from .rollups import (
    generate_daily_rollup,
    generate_weekly_rollup,
    should_generate_daily_rollup,
    should_generate_weekly_rollup,
)
from .routing import (
    copy_note_to_project,
    get_note_tags,
    get_inbox_notes,
    get_tag_routes,
    set_tag_route,
)
