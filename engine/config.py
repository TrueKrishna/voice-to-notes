"""
Environment-driven configuration for the Voice-to-Notes engine.
All paths are set via environment variables. No hardcoded paths. Ever.

Supports optional DB-driven overrides: env vars provide defaults,
settings from the DB Settings table take priority when present.
"""

import os
import sys
import logging
import sqlite3
from pathlib import Path
from dataclasses import dataclass, field

from dotenv import load_dotenv

# Import shared module for model configs
try:
    from shared.api_keys import DEFAULT_MODEL, AVAILABLE_MODELS, get_model_config
except ImportError:
    # Fallback if shared module not available
    DEFAULT_MODEL = "gemini-3-flash-preview"
    AVAILABLE_MODELS = []
    get_model_config = None

logger = logging.getLogger(__name__)


@dataclass
class EngineConfig:
    """Fully environment-driven engine configuration."""

    # Required — directories
    audio_input_dir: Path = field(default_factory=lambda: Path("."))
    obsidian_vault_dir: Path = field(default_factory=lambda: Path("."))
    gemini_api_keys: list[str] = field(default_factory=list)

    # Optional — base subdirectory under vault
    obsidian_note_subdir: str = "VoiceNotes"
    
    # V2 folder structure subdirs (under obsidian_note_subdir)
    inbox_subdir: str = "Inbox"           # Structured notes land here
    transcripts_subdir: str = "Transcripts"  # Raw transcripts
    tasks_subdir: str = "Tasks"           # Daily task aggregations
    daily_subdir: str = "Daily"           # Daily summaries
    weekly_subdir: str = "Weekly"         # Weekly rollups
    projects_subdir: str = "Projects"     # Tag-routed copies
    audio_subdir: str = "Audio"           # Stored compressed audio files
    
    # Processing directories
    processing_temp_dir: Path = field(default_factory=lambda: Path("./data/engine/processing"))
    failed_dir: Path = field(default_factory=lambda: Path("./data/engine/failed"))
    registry_db_path: Path = field(default_factory=lambda: Path("./data/engine/registry.db"))

    # Engine settings
    engine_version: str = "2.0.0"
    default_mode: str = "personal_note"
    gemini_model: str = DEFAULT_MODEL  # Use shared default

    # Transcription engine: "gemini", "whisper-1", or "gpt-4o-transcribe"
    transcription_engine: str = "gemini"
    openai_api_key: str = ""

    # Watcher settings
    stability_seconds: int = 10
    scan_interval_seconds: int = 5

    # Audio settings
    audio_bitrate: str = "48k"
    supported_formats: frozenset = frozenset(
        {".mp3", ".m4a", ".wav", ".ogg", ".flac", ".webm", ".aac", ".opus", ".3gp"}
    )
    
    # Filename format settings
    # Supported: "DD_MM_YY", "YYYY-MM-DD", "MM-DD-YYYY", "YYMMDD", "YYYY-MM-DD_HH-MM"
    filename_date_format: str = "YYYY-MM-DD_HH-MM"

    @property
    def notes_output_dir(self) -> Path:
        """Full path to the Obsidian notes output directory (base)."""
        return self.obsidian_vault_dir / self.obsidian_note_subdir
    
    @property
    def inbox_dir(self) -> Path:
        """Full path to Inbox folder (structured notes)."""
        return self.notes_output_dir / self.inbox_subdir
    
    @property
    def transcripts_dir(self) -> Path:
        """Full path to Transcripts folder (raw transcripts)."""
        return self.notes_output_dir / self.transcripts_subdir
    
    @property
    def tasks_dir(self) -> Path:
        """Full path to Tasks folder (daily task files)."""
        return self.notes_output_dir / self.tasks_subdir
    
    @property
    def daily_dir(self) -> Path:
        """Full path to Daily folder (daily summaries)."""
        return self.notes_output_dir / self.daily_subdir
    
    @property
    def weekly_dir(self) -> Path:
        """Full path to Weekly folder (weekly rollups)."""
        return self.notes_output_dir / self.weekly_subdir
    
    @property
    def projects_dir(self) -> Path:
        """Full path to Projects folder (tag-routed copies)."""
        return self.notes_output_dir / self.projects_subdir

    @property
    def audio_dir(self) -> Path:
        """Full path to Audio folder (stored compressed audio)."""
        return self.notes_output_dir / self.audio_subdir

    def ensure_directories(self):
        """Create all required directories if they don't exist."""
        for d in [
            self.processing_temp_dir, 
            self.failed_dir, 
            self.notes_output_dir,
            self.inbox_dir,
            self.transcripts_dir,
            self.tasks_dir,
            self.daily_dir,
            self.weekly_dir,
            self.projects_dir,
            self.audio_dir,
        ]:
            d.mkdir(parents=True, exist_ok=True)
        self.registry_db_path.parent.mkdir(parents=True, exist_ok=True)

    def validate(self):
        """Validate the configuration at startup."""
        if not self.audio_input_dir.exists():
            logger.warning(
                f"Audio input directory does not exist yet: {self.audio_input_dir}"
            )
        # Gemini keys are always needed (for structuring, even if transcription uses OpenAI)
        if not self.gemini_api_keys:
            logger.error("No Gemini API keys configured")
            raise ValueError("At least one Gemini API key is required")
        # Validate OpenAI config when using OpenAI transcription
        if self.transcription_engine in ("whisper-1", "gpt-4o-transcribe"):
            if not self.openai_api_key:
                logger.error("OpenAI API key required when using OpenAI transcription engine")
                raise ValueError("OPENAI_API_KEY is required for OpenAI transcription")


def load_config(env_file: str = ".env") -> EngineConfig:
    """Load configuration from environment variables.

    Required env vars:
        LOCAL_SYNC_AUDIO_DIR — path to the Google Drive synced audio folder
        OBSIDIAN_VAULT_DIR   — path to the Obsidian vault root
        GEMINI_API_KEYS      — comma-separated Gemini API keys
                               (or GEMINI_API_KEY for a single key)
    """
    load_dotenv(env_file)

    # --- Required: audio input directory ---
    audio_input = os.environ.get("LOCAL_SYNC_AUDIO_DIR")
    if not audio_input:
        logger.error("LOCAL_SYNC_AUDIO_DIR is required but not set")
        sys.exit(1)

    # --- Required: Obsidian vault directory ---
    obsidian_vault = os.environ.get("OBSIDIAN_VAULT_DIR")
    if not obsidian_vault:
        logger.error("OBSIDIAN_VAULT_DIR is required but not set")
        sys.exit(1)

    # --- Required: API keys ---
    keys_str = os.environ.get("GEMINI_API_KEYS", "")
    keys = [k.strip() for k in keys_str.split(",") if k.strip()]
    if not keys:
        single = os.environ.get("GEMINI_API_KEY", "").strip()
        if single:
            keys = [single]
    if not keys:
        logger.error("GEMINI_API_KEYS or GEMINI_API_KEY is required")
        sys.exit(1)

    config = EngineConfig(
        audio_input_dir=Path(audio_input),
        obsidian_vault_dir=Path(obsidian_vault),
        gemini_api_keys=keys,
        obsidian_note_subdir=os.environ.get("OBSIDIAN_NOTE_SUBDIR", "VoiceNotes"),
        processing_temp_dir=Path(
            os.environ.get("PROCESSING_TEMP_DIR", "./data/engine/processing")
        ),
        failed_dir=Path(os.environ.get("FAILED_DIR", "./data/engine/failed")),
        registry_db_path=Path(
            os.environ.get("REGISTRY_DB_PATH", "./data/engine/registry.db")
        ),
        engine_version=os.environ.get("ENGINE_VERSION", "2.0.0"),
        default_mode=os.environ.get("PROCESSING_MODE", "personal_note"),
        gemini_model=os.environ.get("GEMINI_MODEL", "gemini-2.5-flash-preview-05-20"),
        transcription_engine=os.environ.get("TRANSCRIPTION_ENGINE", "gemini"),
        openai_api_key=os.environ.get("OPENAI_API_KEY", ""),
        stability_seconds=int(os.environ.get("STABILITY_SECONDS", "10")),
        scan_interval_seconds=int(os.environ.get("SCAN_INTERVAL", "5")),
        audio_bitrate=os.environ.get("AUDIO_BITRATE", "48k"),
    )

    config.ensure_directories()
    logger.info(f"Config loaded | Input: {config.audio_input_dir} | Vault: {config.notes_output_dir}")
    return config


# ============================================================================
# DB-driven settings key → EngineConfig field mapping
# ============================================================================

_SETTINGS_MAP = {
    "audio_input_dir":      ("LOCAL_SYNC_AUDIO_DIR",   str),
    "obsidian_vault_dir":   ("OBSIDIAN_VAULT_DIR",     str),
    "obsidian_note_subdir": ("OBSIDIAN_NOTE_SUBDIR",   str),
    "default_mode":         ("PROCESSING_MODE",        str),
    "gemini_model":         ("GEMINI_MODEL",           str),
    "stability_seconds":    ("STABILITY_SECONDS",      int),
    "scan_interval_seconds":("SCAN_INTERVAL",          int),
    "audio_bitrate":        ("AUDIO_BITRATE",          str),
    "transcription_engine": ("TRANSCRIPTION_ENGINE",   str),
    "openai_api_key":       ("OPENAI_API_KEY",         str),
    "filename_date_format": ("FILENAME_DATE_FORMAT",   str),
}


def _read_db_settings(db_path: str) -> dict[str, str]:
    """Read all settings from the V1 app's Settings table (raw SQLite, no ORM)."""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.execute("SELECT key, value FROM settings")
        settings = {row[0]: row[1] for row in cursor.fetchall()}
        conn.close()
        return settings
    except Exception as e:
        logger.debug(f"Could not read DB settings: {e}")
        return {}


def _read_api_keys_from_db(db_path: str) -> list[str]:
    """Read active API keys from the V1 app's api_keys table."""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.execute(
            "SELECT key FROM api_keys WHERE is_active = 1 AND (is_exhausted = 0 OR is_exhausted IS NULL)"
        )
        keys = [row[0] for row in cursor.fetchall() if row[0]]
        conn.close()
        if keys:
            logger.info(f"Loaded {len(keys)} API key(s) from database")
        return keys
    except Exception as e:
        logger.debug(f"Could not read API keys from DB: {e}")
        return []


def load_config_from_db(db_path: str | None = None) -> EngineConfig:
    """Load config from env vars, then overlay DB settings on top.

    Priority: DB Settings > env vars > dataclass defaults.
    This is called by the watcher on each scan cycle for hot-reload.

    Args:
        db_path: Path to the V1 app SQLite database.
                 Defaults to DATABASE_URL or ./data/voice_notes.db.
    """
    load_dotenv()

    # Resolve DB path
    if not db_path:
        db_url = os.environ.get("DATABASE_URL", "sqlite:///./data/voice_notes.db")
        # Extract file path from sqlite:///... URL
        if db_url.startswith("sqlite:///"):
            db_path = db_url.replace("sqlite:///", "", 1)
        else:
            db_path = "./data/voice_notes.db"

    db_settings = _read_db_settings(db_path)

    def _get(env_key: str, db_key: str = None, default: str = "") -> str:
        """Get value with priority: DB > env > default."""
        db_val = db_settings.get(db_key or env_key, "")
        if db_val:
            return db_val
        return os.environ.get(env_key, default)

    # --- Required: audio input directory ---
    # IMPORTANT: We do NOT fall back to /data/gdrive - that would scan ALL of Google Drive!
    # User MUST configure this explicitly via Settings UI.
    audio_input = _get("LOCAL_SYNC_AUDIO_DIR")
    if not audio_input:
        logger.warning("⚠️  LOCAL_SYNC_AUDIO_DIR not set! Configure via Settings page at http://localhost:9123/settings")
        # Use a non-existent placeholder - watcher will skip scanning gracefully
        audio_input = "/NOT_CONFIGURED/audio-input"

    # --- Required: Obsidian vault directory ---
    obsidian_vault = _get("OBSIDIAN_VAULT_DIR")
    if not obsidian_vault:
        logger.warning("⚠️  OBSIDIAN_VAULT_DIR not set! Configure via Settings page at http://localhost:9123/settings")
        obsidian_vault = "/NOT_CONFIGURED/obsidian-vault"

    # --- API keys: from V1 database (api_keys table) first, then env vars ---
    keys = _read_api_keys_from_db(db_path)
    if not keys:
        # Fallback to env vars
        keys_str = os.environ.get("GEMINI_API_KEYS", "")
        keys = [k.strip() for k in keys_str.split(",") if k.strip()]
        if not keys:
            single = os.environ.get("GEMINI_API_KEY", "").strip()
            if single:
                keys = [single]
    if not keys:
        logger.warning("No Gemini API keys configured")

    config = EngineConfig(
        audio_input_dir=Path(audio_input),
        obsidian_vault_dir=Path(obsidian_vault),
        gemini_api_keys=keys,
        obsidian_note_subdir=_get("OBSIDIAN_NOTE_SUBDIR", default="VoiceNotes"),
        processing_temp_dir=Path(
            os.environ.get("PROCESSING_TEMP_DIR", "./data/engine/processing")
        ),
        failed_dir=Path(os.environ.get("FAILED_DIR", "./data/engine/failed")),
        registry_db_path=Path(
            os.environ.get("REGISTRY_DB_PATH", "./data/engine/registry.db")
        ),
        engine_version=os.environ.get("ENGINE_VERSION", "2.0.0"),
        default_mode=_get("PROCESSING_MODE", default="personal_note"),
        gemini_model=_get("GEMINI_MODEL", default=DEFAULT_MODEL),
        transcription_engine=_get("TRANSCRIPTION_ENGINE", default="gemini"),
        openai_api_key=_get("OPENAI_API_KEY", default=""),
        stability_seconds=int(_get("STABILITY_SECONDS", default="10")),
        scan_interval_seconds=int(_get("SCAN_INTERVAL", default="5")),
        audio_bitrate=_get("AUDIO_BITRATE", default="48k"),
    )

    config.ensure_directories()
    return config
