"""
Database configuration and models using SQLAlchemy.
Supports SQLite (default) or PostgreSQL.
"""

import os
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, Boolean, Float, event
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Database URL - defaults to SQLite, can use PostgreSQL
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "sqlite:///./data/voice_notes.db"
)

# Handle PostgreSQL URL format from some cloud providers
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Create engine
if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
    
    # Enable WAL mode for crash safety and better concurrent access
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()
else:
    engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# ============================================================================
# MODELS
# ============================================================================

class Recording(Base):
    """Stores information about processed audio recordings."""
    __tablename__ = "recordings"

    id = Column(Integer, primary_key=True, index=True)
    
    # File info
    original_filename = Column(String(500), nullable=False)
    file_format = Column(String(20))  # mp3, m4a, wav, etc.
    original_size_mb = Column(Float)
    compressed_size_mb = Column(Float)
    compressed_file_path = Column(String(500))  # Path to compressed file (for compress-only mode)
    is_compress_only = Column(Boolean, default=False)  # If True, only compression was done
    duration_seconds = Column(Float)
    
    # Audio metadata
    sample_rate = Column(Integer)  # Hz (e.g., 44100, 48000)
    bit_rate = Column(Integer)  # kbps
    channels = Column(Integer)  # 1=mono, 2=stereo
    codec = Column(String(50))  # aac, mp3, opus, etc.
    recorded_at = Column(DateTime)  # Actual recording timestamp from file metadata
    
    # Processing status
    status = Column(String(50), default="pending")  # pending, compressing, transcribing, analyzing, completed, failed
    processing_step = Column(String(50))  # Current step for UI display
    processing_message = Column(String(500))  # Detailed message (e.g., "Waiting 120s for rate limit...")
    error_message = Column(Text)
    
    # API Key tracking
    api_key_id = Column(Integer)  # Which API key was used for this recording
    api_key_name = Column(String(100))  # Friendly name of the key used
    
    # Content
    transcript = Column(Text)
    breakdown = Column(Text)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    processed_at = Column(DateTime)
    
    # Optional tags/notes
    title = Column(String(500))
    tags = Column(String(500))  # Comma-separated
    notes = Column(Text)


class APIKey(Base):
    """Stores Gemini API keys for rotation."""
    __tablename__ = "api_keys"

    id = Column(Integer, primary_key=True, index=True)
    
    # Key info
    key = Column(String(200), nullable=False)
    name = Column(String(100))  # Friendly name like "Personal", "Work"
    
    # Status
    is_active = Column(Boolean, default=True)
    is_exhausted = Column(Boolean, default=False)  # Quota exceeded
    
    # Usage tracking
    total_requests = Column(Integer, default=0)
    failed_requests = Column(Integer, default=0)
    last_used_at = Column(DateTime)
    last_error = Column(Text)
    
    # Capacity tracking for parallel processing
    locked_until = Column(DateTime)  # Prevents race conditions when acquiring key
    requests_this_minute = Column(Integer, default=0)  # Track RPM usage
    minute_window_start = Column(DateTime)  # Start of current minute window
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    exhausted_at = Column(DateTime)


class Settings(Base):
    """Application settings."""
    __tablename__ = "settings"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(100), unique=True, nullable=False)
    value = Column(Text)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ============================================================================
# DATABASE HELPERS
# ============================================================================

def init_db():
    """Initialize database tables."""
    # Ensure data directory exists for SQLite
    if DATABASE_URL.startswith("sqlite"):
        os.makedirs("data", exist_ok=True)
    
    Base.metadata.create_all(bind=engine)


def get_db():
    """Get database session (for FastAPI dependency injection)."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ============================================================================
# SETTINGS HELPERS
# ============================================================================

def get_setting(db, key: str, default=None) -> str | None:
    """Get a setting value by key, or return default if not set."""
    row = db.query(Settings).filter(Settings.key == key).first()
    if row and row.value is not None and row.value != "":
        return row.value
    return default


def set_setting(db, key: str, value: str):
    """Create or update a setting."""
    row = db.query(Settings).filter(Settings.key == key).first()
    if row:
        row.value = value
        row.updated_at = datetime.utcnow()
    else:
        row = Settings(key=key, value=value)
        db.add(row)
    db.commit()


def get_all_settings(db) -> dict[str, str]:
    """Get all settings as a dict."""
    rows = db.query(Settings).all()
    return {row.key: row.value for row in rows}
