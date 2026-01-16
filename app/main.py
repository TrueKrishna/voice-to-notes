"""
FastAPI main application with routes.
"""

import os
import shutil
import asyncio
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, UploadFile, File, Form, Depends, HTTPException, BackgroundTasks, Request
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from .database import init_db, get_db, Recording, APIKey
from .api_keys import APIKeyManager
from .processor import AudioProcessor, SUPPORTED_FORMATS

# ============================================================================
# LOGGING CONFIGURATION
# ============================================================================

# Configure logging with rich formatting
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

logger = logging.getLogger(__name__)


# ============================================================================
# APP SETUP
# ============================================================================

UPLOAD_DIR = Path("data/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database on startup."""
    logger.info("🚀 Voice to Notes application starting up...")
    logger.info("📊 Initializing database...")
    init_db()
    logger.info("✅ Database initialized successfully")
    logger.info("🎙️  Voice to Notes ready to process audio!")
    yield
    logger.info("👋 Voice to Notes shutting down...")


app = FastAPI(
    title="Voice to Notes",
    description="Convert voice memos to structured markdown notes",
    version="1.0.0",
    lifespan=lifespan
)

# Templates
templates = Jinja2Templates(directory="app/templates")


# ============================================================================
# BACKGROUND PROCESSING
# ============================================================================

def process_recording_task(recording_id: int, file_path: Path, compress_only: bool = False):
    """Background task to process a recording."""
    from .database import SessionLocal
    
    mode = "Compress-Only" if compress_only else "Full Processing"
    logger.info(f"🎬 Starting background task | Recording ID: {recording_id} | Mode: {mode} | File: {file_path.name}")
    
    db = SessionLocal()
    try:
        processor = AudioProcessor(db)
        if compress_only:
            logger.info(f"🗜️  Compressing audio | Recording ID: {recording_id}")
            processor.compress_only(file_path, recording_id)
            logger.info(f"✅ Compression complete | Recording ID: {recording_id}")
        else:
            logger.info(f"🎙️  Processing recording | ID: {recording_id} | File: {file_path.name}")
            processor.process(file_path, recording_id)
            logger.info(f"✅ Processing complete | Recording ID: {recording_id}")
    except Exception as e:
        logger.error(f"❌ Processing failed | Recording ID: {recording_id} | Error: {e}", exc_info=True)
    finally:
        db.close()
        # Clean up uploaded file after processing (only if not compress_only)
        if not compress_only:
            try:
                file_path.unlink(missing_ok=True)
                logger.debug(f"🗑️  Cleaned up uploaded file: {file_path.name}")
            except Exception as e:
                logger.warning(f"⚠️  Failed to clean up file {file_path.name}: {e}")


# ============================================================================
# WEB ROUTES
# ============================================================================

@app.get("/", response_class=HTMLResponse)
async def home(request: Request, db: Session = Depends(get_db)):
    """Main dashboard page."""
    logger.debug("📄 Loading home page")
    recordings = db.query(Recording).order_by(Recording.created_at.desc()).limit(50).all()
    key_manager = APIKeyManager(db)
    key_status = key_manager.get_status()
    logger.debug(f"\ud83d\udcca Loaded {len(recordings)} recordings | API Keys: {key_status['total_keys']} total, {key_status['active_keys']} active")
    
    return templates.TemplateResponse("index.html", {
        "request": request,
        "recordings": recordings,
        "key_status": key_status
    })


@app.get("/recording/{recording_id}", response_class=HTMLResponse)
async def view_recording(request: Request, recording_id: int, db: Session = Depends(get_db)):
    """View a single recording's details."""
    recording = db.query(Recording).filter(Recording.id == recording_id).first()
    if not recording:
        raise HTTPException(status_code=404, detail="Recording not found")
    
    return templates.TemplateResponse("recording.html", {
        "request": request,
        "recording": recording
    })


@app.get("/keys", response_class=HTMLResponse)
async def keys_page(request: Request, db: Session = Depends(get_db)):
    """API Keys management page."""
    key_manager = APIKeyManager(db)
    keys = key_manager.get_all_keys()
    status = key_manager.get_status()
    
    return templates.TemplateResponse("keys.html", {
        "request": request,
        "keys": keys,
        "status": status
    })


# ============================================================================
# API ROUTES
# ============================================================================

@app.post("/upload")
async def upload_audio(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    tags: Optional[str] = Form(None),
    compress_only: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    """Upload an audio file for processing."""
    logger.info(f"📤 Upload request received | File: {file.filename} | Size: {file.size if hasattr(file, 'size') else 'unknown'}")
    
    # Validate file extension
    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in SUPPORTED_FORMATS:
        logger.warning(f"⚠️  Invalid file format: {file_ext} | File: {file.filename}")
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported format. Supported: {', '.join(SUPPORTED_FORMATS)}"
        )
    
    is_compress_only = compress_only == "true"
    logger.info(f"📋 Upload mode: {'Compress-Only' if is_compress_only else 'Full Processing'} | Title: {title or 'Auto'}")
    
    # Check if we have API keys (not needed for compress-only)
    if not is_compress_only:
        key_manager = APIKeyManager(db)
        available_key = key_manager.get_next_available_key()
        if not available_key:
            logger.error("❌ No API keys available for processing")
            raise HTTPException(
                status_code=400,
                detail="No API keys available. Please add an API key first."
            )
        logger.info(f"🔑 API key available for processing: {available_key.name}")
    
    # Save uploaded file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_filename = f"{timestamp}_{file.filename}"
    file_path = UPLOAD_DIR / safe_filename
    
    logger.info(f"💾 Saving uploaded file to: {file_path}")
    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    
    file_size_mb = file_path.stat().st_size / (1024 * 1024)
    logger.info(f"✅ File saved successfully | Size: {file_size_mb:.2f} MB | Path: {file_path}")
    
    # Create recording entry
    recording = Recording(
        original_filename=file.filename,
        file_format=file_ext.lstrip('.'),
        title=title or Path(file.filename).stem,
        tags=tags,
        status="pending"
    )
    db.add(recording)
    db.commit()
    db.refresh(recording)
    
    logger.info(f"📝 Created recording entry | ID: {recording.id} | Title: {recording.title}")
    
    # Start background processing
    background_tasks.add_task(process_recording_task, recording.id, file_path, is_compress_only)
    logger.info(f"🚀 Queued background processing task | Recording ID: {recording.id}")
    
    return {"success": True, "recording_id": recording.id, "compress_only": is_compress_only}


@app.post("/keys/add")
async def add_key(
    key: str = Form(...),
    name: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    """Add a new API key."""
    key_manager = APIKeyManager(db)
    
    # Basic validation
    if len(key) < 20:
        raise HTTPException(status_code=400, detail="Invalid API key format")
    
    api_key = key_manager.add_key(key.strip(), name)
    return {"success": True, "key_id": api_key.id}


@app.post("/keys/{key_id}/toggle")
async def toggle_key(key_id: int, db: Session = Depends(get_db)):
    """Toggle a key's active status."""
    key_manager = APIKeyManager(db)
    if key_manager.toggle_key(key_id):
        return {"success": True}
    raise HTTPException(status_code=404, detail="Key not found")


@app.post("/keys/{key_id}/reset")
async def reset_key(key_id: int, db: Session = Depends(get_db)):
    """Reset an exhausted key."""
    key_manager = APIKeyManager(db)
    if key_manager.reset_key(key_id):
        return {"success": True}
    raise HTTPException(status_code=404, detail="Key not found")


@app.delete("/keys/{key_id}")
async def delete_key(key_id: int, db: Session = Depends(get_db)):
    """Delete an API key."""
    key_manager = APIKeyManager(db)
    if key_manager.delete_key(key_id):
        return {"success": True}
    raise HTTPException(status_code=404, detail="Key not found")


@app.post("/keys/reset-all")
async def reset_all_keys(db: Session = Depends(get_db)):
    """Reset all exhausted keys."""
    key_manager = APIKeyManager(db)
    key_manager.reset_all_keys()
    return {"success": True}


@app.get("/recording/{recording_id}/status")
async def get_recording_status(recording_id: int, db: Session = Depends(get_db)):
    """Get the processing status of a recording with detailed step info and queue position."""
    recording = db.query(Recording).filter(Recording.id == recording_id).first()
    if not recording:
        raise HTTPException(status_code=404, detail="Recording not found")
    
    # Calculate compression ratio if available
    compression_ratio = None
    compression_savings = None
    if recording.original_size_mb and recording.compressed_size_mb:
        if recording.compressed_size_mb < recording.original_size_mb:
            compression_ratio = recording.original_size_mb / recording.compressed_size_mb
            compression_savings = (1 - recording.compressed_size_mb / recording.original_size_mb) * 100
    
    # Calculate queue position if recording is pending/processing
    queue_position = None
    estimated_wait = None
    key_status = None
    
    if recording.status in ["pending", "processing"]:
        # Count recordings ahead in queue (older with same status)
        queue_position = db.query(Recording).filter(
            Recording.status.in_(["pending", "processing"]),
            Recording.created_at < recording.created_at
        ).count() + 1  # +1 because position is 1-indexed
        
        # Get API key capacity status
        key_manager = APIKeyManager(db)
        key_status = key_manager.get_status()
        estimated_wait = key_manager.get_estimated_wait_time(queue_position)
    
    return {
        "id": recording.id,
        "status": recording.status,
        "processing_step": recording.processing_step,
        "processing_message": recording.processing_message,
        "error_message": recording.error_message,
        "original_size_mb": round(recording.original_size_mb, 2) if recording.original_size_mb else None,
        "compressed_size_mb": round(recording.compressed_size_mb, 2) if recording.compressed_size_mb else None,
        "compression_ratio": round(compression_ratio, 1) if compression_ratio else None,
        "compression_savings": round(compression_savings, 0) if compression_savings else None,
        "duration_seconds": recording.duration_seconds,
        # Queue info
        "queue_position": queue_position,
        "estimated_wait_seconds": estimated_wait,
        "key_status": key_status
    }


@app.get("/recording/{recording_id}/download/compressed")
async def download_compressed(recording_id: int, db: Session = Depends(get_db)):
    """Download the compressed audio file."""
    logger.debug(f"\ud83d\udce5 Download compressed audio request | Recording ID: {recording_id}")
    recording = db.query(Recording).filter(Recording.id == recording_id).first()
    if not recording:
        raise HTTPException(status_code=404, detail="Recording not found")
    
    if not recording.compressed_file_path:
        raise HTTPException(status_code=404, detail="Compressed file not available")
    
    file_path = Path(recording.compressed_file_path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Compressed file not found on disk")
    
    # Determine filename for download
    base_name = Path(recording.original_filename).stem
    download_name = f"{base_name}_compressed{file_path.suffix}"
    
    logger.info(f"\u2705 Serving compressed audio | Recording ID: {recording_id} | File: {download_name}")
    return FileResponse(
        str(file_path),
        filename=download_name,
        media_type="audio/opus"
    )


@app.get("/recording/{recording_id}/audio/stream")
async def stream_audio(recording_id: int, db: Session = Depends(get_db)):
    """Stream audio file for playback in browser."""
    logger.debug(f"\ud83c\udfb5 Stream audio request | Recording ID: {recording_id}")
    recording = db.query(Recording).filter(Recording.id == recording_id).first()
    if not recording:
        raise HTTPException(status_code=404, detail="Recording not found")
    
    if not recording.compressed_file_path:
        raise HTTPException(status_code=404, detail="Audio file not available")
    
    file_path = Path(recording.compressed_file_path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Audio file not found on disk")
    
    # Determine media type based on file extension
    ext = file_path.suffix.lower()
    media_type_map = {
        '.opus': 'audio/ogg',  # Opus is typically in ogg container
        '.ogg': 'audio/ogg',
        '.mp3': 'audio/mpeg',
        '.m4a': 'audio/mp4',
        '.wav': 'audio/wav',
        '.webm': 'audio/webm'
    }
    media_type = media_type_map.get(ext, 'audio/mpeg')
    
    logger.debug(f"\u2705 Streaming audio | Recording ID: {recording_id} | Type: {media_type}")
    return FileResponse(
        str(file_path),
        media_type=media_type,
        headers={"Accept-Ranges": "bytes"}  # Enable seeking in audio player
    )


@app.get("/recording/{recording_id}/download/{file_type}")
async def download_file(recording_id: int, file_type: str, db: Session = Depends(get_db)):
    """Download transcript or breakdown as markdown file."""
    recording = db.query(Recording).filter(Recording.id == recording_id).first()
    if not recording:
        raise HTTPException(status_code=404, detail="Recording not found")
    
    if file_type == "transcript":
        content = recording.transcript
        filename = f"{recording.title}_transcript.md"
    elif file_type == "breakdown":
        content = recording.breakdown
        filename = f"{recording.title}_breakdown.md"
    else:
        raise HTTPException(status_code=400, detail="Invalid file type")
    
    if not content:
        raise HTTPException(status_code=404, detail="Content not available")
    
    # Create temp file for download
    import tempfile
    temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False)
    temp_file.write(content)
    temp_file.close()
    
    return FileResponse(
        temp_file.name,
        filename=filename,
        media_type="text/markdown"
    )


@app.delete("/recording/{recording_id}")
async def delete_recording(recording_id: int, db: Session = Depends(get_db)):
    """Delete a recording."""
    recording = db.query(Recording).filter(Recording.id == recording_id).first()
    if not recording:
        raise HTTPException(status_code=404, detail="Recording not found")
    
    db.delete(recording)
    db.commit()
    return {"success": True}


@app.post("/recording/{recording_id}/abort")
async def abort_recording(recording_id: int, db: Session = Depends(get_db)):
    """Abort a processing recording."""
    recording = db.query(Recording).filter(Recording.id == recording_id).first()
    if not recording:
        raise HTTPException(status_code=404, detail="Recording not found")
    
    if recording.status in ["pending", "processing"]:
        recording.status = "failed"
        recording.error_message = "Aborted by user"
        recording.processing_step = "aborted"
        db.commit()
        return {"success": True, "message": "Recording aborted"}
    
    return {"success": False, "message": "Recording is not in a cancellable state"}


@app.post("/recording/{recording_id}/reprocess")
async def reprocess_recording(
    recording_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Reprocess a failed recording (if file still exists)."""
    recording = db.query(Recording).filter(Recording.id == recording_id).first()
    if not recording:
        raise HTTPException(status_code=404, detail="Recording not found")
    
    # Check for original file
    file_path = None
    for f in UPLOAD_DIR.iterdir():
        if recording.original_filename in f.name:
            file_path = f
            break
    
    if not file_path or not file_path.exists():
        raise HTTPException(
            status_code=400,
            detail="Original file no longer available. Please upload again."
        )
    
    # Reset status and reprocess
    recording.status = "pending"
    recording.error_message = None
    db.commit()
    
    background_tasks.add_task(process_recording_task, recording.id, file_path)
    return {"success": True}

@app.get("/storage", response_class=HTMLResponse)
async def storage_management(request: Request, db: Session = Depends(get_db)):
    """Storage management page showing all files and disk usage."""
    from pathlib import Path
    import os
    
    # Get all recordings
    recordings = db.query(Recording).order_by(Recording.created_at.desc()).all()
    
    # Calculate storage stats
    total_original = sum(r.original_size_mb or 0 for r in recordings)
    total_compressed = sum(r.compressed_size_mb or 0 for r in recordings)
    total_saved = total_original - total_compressed
    
    # Count files
    compressed_dir = Path("data/compressed")
    compressed_files = list(compressed_dir.glob("*")) if compressed_dir.exists() else []
    upload_files = list(UPLOAD_DIR.glob("*")) if UPLOAD_DIR.exists() else []
    
    # Get actual disk usage
    def get_dir_size(path):
        total = 0
        try:
            for entry in path.rglob('*'):
                if entry.is_file():
                    total += entry.stat().st_size
        except:
            pass
        return total / (1024 * 1024)  # Convert to MB
    
    compressed_disk_mb = get_dir_size(compressed_dir) if compressed_dir.exists() else 0
    uploads_disk_mb = get_dir_size(UPLOAD_DIR) if UPLOAD_DIR.exists() else 0
    
    # Get database size
    db_path = Path("data/voice_notes.db")
    db_size_mb = db_path.stat().st_size / (1024 * 1024) if db_path.exists() else 0
    
    total_disk_mb = compressed_disk_mb + uploads_disk_mb + db_size_mb
    
    storage_stats = {
        "total_recordings": len(recordings),
        "total_original_mb": round(total_original, 2),
        "total_compressed_mb": round(total_compressed, 2),
        "total_saved_mb": round(total_saved, 2),
        "compression_ratio": round((1 - total_compressed / total_original) * 100, 1) if total_original > 0 else 0,
        "compressed_files_count": len(compressed_files),
        "upload_files_count": len(upload_files),
        "compressed_disk_mb": round(compressed_disk_mb, 2),
        "uploads_disk_mb": round(uploads_disk_mb, 2),
        "db_size_mb": round(db_size_mb, 2),
        "total_disk_mb": round(total_disk_mb, 2),
    }
    
    return templates.TemplateResponse("storage.html", {
        "request": request,
        "recordings": recordings,
        "storage_stats": storage_stats,
        "orphaned_uploads": [f.name for f in upload_files],
        "compressed_files": [f.name for f in compressed_files],
    })


@app.post("/storage/cleanup-orphaned")
async def cleanup_orphaned_files(db: Session = Depends(get_db)):
    """Delete orphaned upload files that don't have associated recordings."""
    deleted_count = 0
    deleted_size = 0
    
    try:
        # Get all recording filenames
        recordings = db.query(Recording).all()
        recording_files = {r.original_filename for r in recordings}
        
        # Check upload directory
        for file_path in UPLOAD_DIR.iterdir():
            if file_path.is_file() and file_path.name not in recording_files:
                deleted_size += file_path.stat().st_size
                file_path.unlink()
                deleted_count += 1
        
        return {
            "success": True,
            "deleted_count": deleted_count,
            "deleted_size_mb": round(deleted_size / (1024 * 1024), 2)
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.post("/storage/bulk-delete")
async def bulk_delete_recordings(
    request: Request,
    db: Session = Depends(get_db)
):
    """Bulk delete multiple recordings."""
    data = await request.json()
    recording_ids = data.get("recording_ids", [])
    
    if not recording_ids:
        return {"success": False, "error": "No recordings specified"}
    
    deleted_count = 0
    
    try:
        for recording_id in recording_ids:
            recording = db.query(Recording).filter(Recording.id == recording_id).first()
            if recording:
                # Delete compressed file
                if recording.compressed_file_path:
                    try:
                        Path(recording.compressed_file_path).unlink(missing_ok=True)
                    except:
                        pass
                
                # Delete from database
                db.delete(recording)
                deleted_count += 1
        
        db.commit()
        return {"success": True, "deleted_count": deleted_count}
    except Exception as e:
        db.rollback()
        return {"success": False, "error": str(e)}


# ============================================================================
# API KEY MANAGEMENT
# ============================================================================