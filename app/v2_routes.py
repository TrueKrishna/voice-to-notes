"""
V2 Frontend Routes and API endpoints.
Provides the new dark-mode, information-dense UI.
"""

import json
import logging
from pathlib import Path
from typing import Optional, List
from datetime import datetime

from fastapi import APIRouter, Request, Depends, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from pydantic import BaseModel

from .database import get_db, Recording

# Import shared modules for model configs
try:
    from shared.api_keys import AVAILABLE_MODELS, DEFAULT_MODEL
except ImportError:
    AVAILABLE_MODELS = []
    DEFAULT_MODEL = "gemini-2.0-flash"

logger = logging.getLogger(__name__)

# Create router with /v2 prefix
router = APIRouter(prefix="/v2", tags=["v2"])

# Templates - reuse the same templates instance
templates = Jinja2Templates(directory="app/templates")


# ============================================================================
# PYDANTIC MODELS
# ============================================================================

class NoteUpdate(BaseModel):
    title: Optional[str] = None
    tags: Optional[List[str]] = None


class TaskUpdate(BaseModel):
    completed: bool


class SettingsUpdate(BaseModel):
    LOCAL_SYNC_AUDIO_DIR: Optional[str] = None
    OBSIDIAN_VAULT_DIR: Optional[str] = None
    OBSIDIAN_NOTE_SUBDIR: Optional[str] = None
    PROCESSING_MODE: Optional[str] = None
    GEMINI_MODEL: Optional[str] = None
    TRANSCRIPTION_ENGINE: Optional[str] = None
    OPENAI_API_KEY: Optional[str] = None
    STABILITY_SECONDS: Optional[str] = None
    SCAN_INTERVAL: Optional[str] = None
    AUDIO_BITRATE: Optional[str] = None


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def _get_registry_path() -> Path:
    """Get the engine registry database path."""
    import os
    return Path(os.environ.get("REGISTRY_DB_PATH", "./data/engine/registry.db"))


def _read_v2_registry(limit: int = 100):
    """Read recent processing entries from the engine registry."""
    registry_path = _get_registry_path()
    if not registry_path.exists():
        return []
    
    import sqlite3, json
    conn = sqlite3.connect(str(registry_path))
    conn.row_factory = sqlite3.Row
    
    rows = conn.execute("""
        SELECT 
            id,
            filename,
            title,
            CASE WHEN success = 1 THEN 'completed' 
                 WHEN success = 0 THEN 'failed'
                 ELSE 'pending' END as status,
            COALESCE(ingested_at, processed_at) as created_at,
            duration_seconds as duration,
            note_path,
            error,
            mode,
            retry_count,
            file_hash,
            skipped,
            has_tasks,
            tags,
            projects
        FROM processed_files
        ORDER BY COALESCE(ingested_at, processed_at) DESC
        LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    
    results = []
    for row in rows:
        d = dict(row)
        # Parse JSON fields
        try:
            d["tags"] = json.loads(d.get("tags") or "[]")
        except (json.JSONDecodeError, TypeError):
            d["tags"] = []
        try:
            d["projects"] = json.loads(d.get("projects") or "[]")
        except (json.JSONDecodeError, TypeError):
            d["projects"] = []
        results.append(d)
    
    return results


def _get_v2_stats():
    """Get statistics from the engine registry."""
    registry_path = _get_registry_path()
    if not registry_path.exists():
        return {
            "total_notes": 0,
            "notes_today": 0,
            "success": 0,
            "failed": 0,
            "pending": 0,
            "processing": 0,
            "last_processed": None
        }
    
    import sqlite3
    conn = sqlite3.connect(str(registry_path))
    
    total = conn.execute("SELECT COUNT(*) FROM processed_files").fetchone()[0]
    success = conn.execute("SELECT COUNT(*) FROM processed_files WHERE success = 1").fetchone()[0]
    failed = conn.execute("SELECT COUNT(*) FROM processed_files WHERE success = 0").fetchone()[0]
    today = datetime.now().strftime("%Y-%m-%d")
    notes_today = conn.execute(
        "SELECT COUNT(*) FROM processed_files WHERE DATE(processed_at) = ? AND success = 1",
        (today,)
    ).fetchone()[0]
    last_processed = conn.execute(
        "SELECT MAX(processed_at) FROM processed_files WHERE success = 1"
    ).fetchone()[0]
    
    # Get watcher status for processing/pending
    watcher_state = "idle"
    files_in_queue = 0
    try:
        row = conn.execute("SELECT state, files_in_queue FROM watcher_status WHERE id = 1").fetchone()
        if row:
            watcher_state = row[0] or "idle"
            files_in_queue = row[1] or 0
    except Exception:
        pass
    
    conn.close()
    
    return {
        "total_notes": total,
        "notes_today": notes_today,
        "success": success,
        "failed": failed,
        "pending": files_in_queue,
        "processing": 1 if watcher_state == "processing" else 0,
        "last_processed": last_processed
    }


def _note_to_dict(recording: Recording) -> dict:
    """Convert a Recording to a note dict for templates."""
    content = recording.notes or recording.breakdown or ""
    return {
        "id": recording.id,
        "filename": recording.original_filename,
        "title": recording.title or recording.original_filename,
        "status": recording.status,
        "created_at": recording.created_at.isoformat() if recording.created_at else None,
        "processed_at": recording.processed_at.isoformat() if recording.processed_at else None,
        "duration": recording.duration_seconds,
        "content": content,
        "transcript": recording.transcript,
        "tags": recording.tags.split(",") if recording.tags else [],
        "tasks": [],  # Would need task extraction
        "preview": (content or recording.transcript or "")[:200],
        "audio_url": f"/audio/{recording.id}" if recording.compressed_file_path else None,
        "obsidian_path": None  # V1 doesn't have this
    }


# ============================================================================
# PAGE ROUTES
# ============================================================================

@router.get("/", response_class=HTMLResponse)
async def v2_dashboard(request: Request, db: Session = Depends(get_db)):
    """V2 Dashboard page — live system overview."""
    from .database import get_setting
    
    # Stats from registry
    stats = _get_v2_stats()
    
    # Watcher status
    watcher = _get_watcher_status()
    
    # API key health
    api_keys = _get_api_key_status(db)
    
    # Recent activity from registry  
    recent_activity = _read_v2_registry(limit=20)
    
    # Ingest folder files
    ingest_files = _get_ingest_files(db)
    
    # Failed files
    failed_files = _get_failed_files()
    
    # Config summary
    config = {
        "audio_input": get_setting(db, "LOCAL_SYNC_AUDIO_DIR", "Not configured"),
        "obsidian_vault": get_setting(db, "OBSIDIAN_VAULT_DIR", "Not configured"),
        "model": get_setting(db, "GEMINI_MODEL", "gemini-3-flash-preview"),
        "mode": get_setting(db, "PROCESSING_MODE", "personal_note"),
        "scan_interval": get_setting(db, "SCAN_INTERVAL", "5"),
    }
    
    return templates.TemplateResponse("v2/dashboard.html", {
        "request": request,
        "active_page": "dashboard",
        "stats": stats,
        "watcher": watcher,
        "api_keys": api_keys,
        "recent_activity": recent_activity,
        "ingest_files": ingest_files,
        "failed_files": failed_files,
        "config": config,
    })


@router.get("/inbox", response_class=HTMLResponse)
async def v2_inbox(request: Request, tag: str = None, db: Session = Depends(get_db)):
    """V2 Inbox page - list all notes (V1 recordings + V2 registry)."""
    # V1 recordings
    recordings = db.query(Recording).order_by(Recording.created_at.desc()).limit(100).all()
    notes = [_note_to_dict(r) for r in recordings]
    for n in notes:
        n["source"] = "v1"
        n["link"] = f"/v2/note/{n['id']}"
        if "tags" not in n:
            n["tags"] = []

    # V2 registry (watcher-processed)
    registry_notes = _read_v2_registry(limit=100)
    for rn in registry_notes:
        notes.append({
            "id": rn.get("id"),
            "filename": rn.get("filename", ""),
            "title": rn.get("title") or rn.get("filename", "Untitled"),
            "status": rn.get("status", "pending"),
            "created_at": rn.get("created_at"),
            "processed_at": rn.get("created_at"),
            "captured_at": rn.get("captured_at"),
            "duration": rn.get("duration"),
            "content": "",
            "transcript": "",
            "tags": rn.get("tags", []),
            "projects": rn.get("projects", []),
            "tasks": [],
            "preview": rn.get("title") or rn.get("filename", ""),
            "audio_url": None,
            "obsidian_path": rn.get("note_path"),
            "source": "registry",
            "link": f"/v2/registry-note/{rn.get('id')}",
            "mode": rn.get("mode"),
            "error": rn.get("error"),
        })

    # Sort by date descending, dedup by filename
    seen = set()
    deduped = []
    for n in sorted(notes, key=lambda x: x.get("created_at") or "", reverse=True):
        key = n.get("filename", "")
        if key and key in seen:
            continue
        seen.add(key)
        deduped.append(n)

    inbox_count = len([n for n in deduped if n["status"] != "completed"])

    return templates.TemplateResponse("v2/inbox.html", {
        "request": request,
        "active_page": "inbox",
        "notes": deduped,
        "inbox_count": inbox_count,
        "filter_tag": tag or "",
    })


@router.get("/note/{note_id}", response_class=HTMLResponse)
async def v2_note_detail(request: Request, note_id: int, db: Session = Depends(get_db)):
    """V2 Note detail page."""
    recording = db.query(Recording).filter(Recording.id == note_id).first()
    if not recording:
        raise HTTPException(status_code=404, detail="Note not found")
    
    note = _note_to_dict(recording)
    
    return templates.TemplateResponse("v2/note.html", {
        "request": request,
        "active_page": "inbox",
        "note": note
    })


@router.get("/tasks", response_class=HTMLResponse)
async def v2_tasks(request: Request, db: Session = Depends(get_db)):
    """V2 Tasks page - reads from daily task files."""
    from .database import get_setting
    from datetime import date, timedelta
    import re
    
    vault_dir = get_setting(db, "OBSIDIAN_VAULT_DIR", "")
    note_subdir = get_setting(db, "OBSIDIAN_NOTE_SUBDIR", "VoiceNotes")
    
    tasks = []
    tasks_sources = []  # Track which daily files we've read
    
    if vault_dir:
        tasks_dir = Path(vault_dir) / note_subdir / "Tasks"
        
        if tasks_dir.exists():
            # Read all daily task files from last 30 days
            today = date.today()
            for days_ago in range(31):
                check_date = today - timedelta(days=days_ago)
                daily_file = tasks_dir / f"{check_date.isoformat()}.md"
                
                if daily_file.exists():
                    tasks_sources.append(check_date.isoformat())
                    content = daily_file.read_text(encoding="utf-8")
                    
                    # Parse checkbox lines
                    checkbox_pattern = r"- \[([ x])\] (.+)"
                    for match in re.finditer(checkbox_pattern, content):
                        completed = match.group(1).lower() == "x"
                        raw_text = match.group(2)
                        
                        # Extract source backlink if present
                        source_match = re.search(r"\[\[Inbox/([^\]|]+)", raw_text)
                        source = source_match.group(1) if source_match else None
                        
                        # Extract priority emoji
                        priority = "medium"
                        if "🔴" in raw_text:
                            priority = "high"
                        elif "🟢" in raw_text:
                            priority = "low"
                        
                        # Extract due date
                        due_match = re.search(r"📅\s*([^,)]+)", raw_text)
                        due_date = due_match.group(1).strip() if due_match else None
                        
                        # Clean the text
                        clean_text = re.sub(r"\s*\([^)]*\)\s*\[\[.+?\]\]$", "", raw_text).strip()
                        clean_text = re.sub(r"\s*\[\[.+?\]\]$", "", clean_text).strip()
                        
                        tasks.append({
                            "id": len(tasks) + 1,
                            "text": clean_text,
                            "completed": completed,
                            "source": source,
                            "priority": priority,
                            "due_date": due_date,
                            "date": check_date.isoformat(),
                            "file": daily_file.name,
                        })
    
    # Count stats
    pending_count = sum(1 for t in tasks if not t["completed"])
    completed_count = sum(1 for t in tasks if t["completed"])
    
    return templates.TemplateResponse("v2/tasks.html", {
        "request": request,
        "active_page": "tasks",
        "tasks": tasks,
        "tasks_count": pending_count,
        "pending_count": pending_count,
        "completed_count": completed_count,
        "total_count": len(tasks),
    })


@router.get("/settings", response_class=HTMLResponse)
async def v2_settings(request: Request, db: Session = Depends(get_db)):
    """V2 Settings page."""
    from .database import get_setting
    
    # Settings keys and defaults (matching main.py)
    SETTINGS_KEYS = [
        "LOCAL_SYNC_AUDIO_DIR",
        "OBSIDIAN_VAULT_DIR",
        "OBSIDIAN_NOTE_SUBDIR",
        "PROCESSING_MODE",
        "GEMINI_MODEL",
        "TRANSCRIPTION_ENGINE",
        "OPENAI_API_KEY",
        "STABILITY_SECONDS",
        "SCAN_INTERVAL",
        "AUDIO_BITRATE",
        "FILENAME_DATE_FORMAT",
    ]
    
    SETTINGS_DEFAULTS = {
        "LOCAL_SYNC_AUDIO_DIR": "",
        "OBSIDIAN_VAULT_DIR": "",
        "OBSIDIAN_NOTE_SUBDIR": "VoiceNotes",
        "PROCESSING_MODE": "personal_note",
        "GEMINI_MODEL": DEFAULT_MODEL,
        "TRANSCRIPTION_ENGINE": "gemini",
        "OPENAI_API_KEY": "",
        "STABILITY_SECONDS": "10",
        "SCAN_INTERVAL": "5",
        "AUDIO_BITRATE": "48k",
        "FILENAME_DATE_FORMAT": "DD_MM_YY",
    }
    
    PROCESSING_MODES = [
        ("personal_note", "Personal Note"),
        ("idea", "Idea"),
        ("meeting", "Meeting"),
        ("reflection", "Reflection"),
        ("task_dump", "Task Dump"),
    ]
    
    # Build config dict
    config = {}
    for key in SETTINGS_KEYS:
        config[key] = get_setting(db, key, SETTINGS_DEFAULTS.get(key, ""))
    
    # Get watcher stats
    watcher_stats = None
    registry_path = Path("data/engine/registry.db")
    if registry_path.exists():
        try:
            import sqlite3
            conn = sqlite3.connect(str(registry_path))
            cursor = conn.execute(
                "SELECT COUNT(*), "
                "SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END), "
                "SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END), "
                "MAX(processed_at) "
                "FROM processed_files"
            )
            row = cursor.fetchone()
            conn.close()
            watcher_stats = {
                "total": row[0] or 0,
                "success": row[1] or 0,
                "failed": row[2] or 0,
                "last_processed": row[3] or "Never",
            }
        except Exception:
            pass
    
    # Available models - use shared config if available
    models = [(m.id, f"{m.display_name} - {m.description}") for m in AVAILABLE_MODELS] if AVAILABLE_MODELS else [
        ("gemini-2.0-flash", "Gemini 2.0 Flash - Fast and efficient"),
        ("gemini-1.5-flash", "Gemini 1.5 Flash - Stable and reliable"),
        ("gemini-1.5-pro", "Gemini 1.5 Pro - More capable but slower"),
    ]
    
    # Available transcription engines
    transcription_engines = [
        ("gemini", "Gemini (uses selected model above)"),
        ("whisper-1", "OpenAI Whisper — Fast & affordable ($0.006/min)"),
        ("gpt-4o-transcribe", "OpenAI GPT-4o Transcribe — Premium quality ($0.06/min)"),
    ]
    
    return templates.TemplateResponse("v2/settings.html", {
        "request": request,
        "active_page": "settings",
        "settings": config,
        "modes": PROCESSING_MODES,
        "models": models,
        "transcription_engines": transcription_engines,
        "watcher_stats": watcher_stats,
    })


@router.get("/projects", response_class=HTMLResponse)
async def v2_projects(request: Request, db: Session = Depends(get_db)):
    """V2 Projects page — notes grouped by processing mode AND user-assigned projects."""
    from .database import get_setting
    import sqlite3, json

    registry_path = _get_registry_path()
    mode_groups = {}
    project_groups = {}
    
    if registry_path.exists():
        try:
            conn = sqlite3.connect(str(registry_path))
            conn.row_factory = sqlite3.Row
            # Note: COALESCE(ingested_at, processed_at) aliased as 'processed_at' for template compatibility
            # This represents the actual ingestion time, falling back to processing time for old entries
            rows = conn.execute(
                "SELECT id, filename, title, mode, projects, COALESCE(ingested_at, processed_at) as processed_at, success, error, duration_seconds "
                "FROM processed_files WHERE success = 1 ORDER BY COALESCE(ingested_at, processed_at) DESC"
            ).fetchall()
            conn.close()
            
            for row in rows:
                d = dict(row)
                
                # Group by mode
                mode = d.get("mode") or "uncategorized"
                if mode not in mode_groups:
                    mode_groups[mode] = {"name": mode, "kind": "mode", "notes": [], "count": 0, "latest": None}
                mode_groups[mode]["notes"].append(d)
                mode_groups[mode]["count"] += 1
                if not mode_groups[mode]["latest"]:
                    mode_groups[mode]["latest"] = d.get("processed_at")
                
                # Group by user-assigned projects
                try:
                    projects_list = json.loads(d.get("projects") or "[]")
                except (json.JSONDecodeError, TypeError):
                    projects_list = []
                
                for proj in projects_list:
                    if proj:
                        if proj not in project_groups:
                            project_groups[proj] = {"name": proj, "kind": "project", "notes": [], "count": 0, "latest": None}
                        project_groups[proj]["notes"].append(d)
                        project_groups[proj]["count"] += 1
                        if not project_groups[proj]["latest"]:
                            project_groups[proj]["latest"] = d.get("processed_at")
                            
        except Exception as e:
            logger.error(f"Failed to read projects: {e}")

    # Combine: user projects first, then modes
    all_groups = list(project_groups.values()) + list(mode_groups.values())
    # Sort within each kind by count
    all_groups.sort(key=lambda p: (-1 if p["kind"] == "project" else 0, -p["count"]))

    return templates.TemplateResponse("v2/projects.html", {
        "request": request,
        "active_page": "projects",
        "projects": all_groups,
    })


@router.get("/archive", response_class=HTMLResponse)
async def v2_archive(request: Request, db: Session = Depends(get_db)):
    """V2 Archive page — all processed notes with date filter."""
    return templates.TemplateResponse("v2/archive.html", {
        "request": request,
        "active_page": "archive",
    })


@router.get("/keys", response_class=HTMLResponse)
async def v2_keys(request: Request, db: Session = Depends(get_db)):
    """V2 API Key management page."""
    from .database import APIKey
    keys = db.query(APIKey).order_by(APIKey.created_at).all()
    key_list = [
        {
            "id": k.id,
            "name": k.name or f"Key {k.id}",
            "key_preview": k.key[:6] + "..." + k.key[-4:] if k.key and len(k.key) > 12 else "***",
            "is_active": k.is_active,
            "is_exhausted": k.is_exhausted,
            "total_requests": k.total_requests or 0,
            "failed_requests": k.failed_requests or 0,
            "last_error": k.last_error,
            "last_used_at": k.last_used_at.isoformat() if k.last_used_at else None,
            "created_at": k.created_at.isoformat() if k.created_at else None,
            "exhausted_at": k.exhausted_at.isoformat() if k.exhausted_at else None,
        }
        for k in keys
    ]
    return templates.TemplateResponse("v2/keys.html", {
        "request": request,
        "active_page": "keys",
        "keys": key_list,
    })


@router.get("/calendar", response_class=HTMLResponse)
async def v2_calendar(request: Request, db: Session = Depends(get_db)):
    """V2 Calendar page — daily/weekly rollover view."""
    return templates.TemplateResponse("v2/calendar.html", {
        "request": request,
        "active_page": "calendar",
    })


@router.get("/registry-note/{note_id}", response_class=HTMLResponse)
async def v2_registry_note(request: Request, note_id: int, db: Session = Depends(get_db)):
    """V2 Registry note detail page — view a watcher-processed note."""
    import sqlite3
    from .database import get_setting

    registry_path = _get_registry_path()
    if not registry_path.exists():
        raise HTTPException(status_code=404, detail="Registry not found")

    conn = sqlite3.connect(str(registry_path))
    conn.row_factory = sqlite3.Row

    # Ensure tags/projects/audio_path columns exist (migration)
    for col, default in [("tags", "''"), ("projects", "'[]'"), ("audio_path", "''")]:
        try:
            conn.execute(f"ALTER TABLE processed_files ADD COLUMN {col} TEXT DEFAULT {default}")
            conn.commit()
        except sqlite3.OperationalError:
            pass

    row = conn.execute(
        "SELECT id, filename, title, mode, processed_at, success, error, "
        "duration_seconds, file_hash, retry_count, skipped, has_tasks, note_path, "
        "transcript_path, tags, projects, audio_path "
        "FROM processed_files WHERE id = ?", (note_id,)
    ).fetchone()

    # Also get list of all distinct projects for the picker
    all_projects_rows = conn.execute(
        "SELECT DISTINCT mode FROM processed_files WHERE mode IS NOT NULL AND mode != ''"
    ).fetchall()
    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="Note not found")

    note = dict(row)
    note["status"] = "completed" if note["success"] else "failed"

    # Parse tags & projects JSON
    import json
    try:
        note["tags"] = json.loads(note.get("tags") or "[]")
    except Exception:
        note["tags"] = []
    try:
        note["projects"] = json.loads(note.get("projects") or "[]")
    except Exception:
        note["projects"] = []

    # Collect known project names
    known_projects = sorted(set(r["mode"] for r in all_projects_rows))

    vault_dir = get_setting(db, "OBSIDIAN_VAULT_DIR", "")

    def _try_read(path_str):
        """Try to read a file, trying absolute path then vault-relative."""
        if not path_str:
            return ""
        try:
            p = Path(path_str)
            if p.exists():
                return p.read_text(encoding="utf-8")
        except Exception:
            pass
        if vault_dir:
            try:
                p = Path(vault_dir) / path_str
                if p.exists():
                    return p.read_text(encoding="utf-8")
            except Exception:
                pass
        return ""

    note["content"] = _try_read(note.get("note_path"))
    note["transcript"] = _try_read(note.get("transcript_path"))

    # Build audio URL if audio file exists
    audio_path_str = note.get("audio_path", "")
    if audio_path_str:
        p = Path(audio_path_str)
        if p.exists():
            note["audio_url"] = f"/v2/api/registry/{note_id}/audio"
        else:
            note["audio_url"] = None
    else:
        note["audio_url"] = None

    return templates.TemplateResponse("v2/registry-note.html", {
        "request": request,
        "active_page": "inbox",
        "note": note,
        "known_projects": known_projects,
    })


# ============================================================================
# API ROUTES
# ============================================================================

@router.get("/api/notes")
async def api_get_notes(
    limit: int = 100,
    status: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get all notes."""
    query = db.query(Recording)
    if status:
        query = query.filter(Recording.status == status)
    
    recordings = query.order_by(Recording.created_at.desc()).limit(limit).all()
    return [_note_to_dict(r) for r in recordings]


@router.get("/api/notes/{note_id}")
async def api_get_note(note_id: int, db: Session = Depends(get_db)):
    """Get a single note."""
    recording = db.query(Recording).filter(Recording.id == note_id).first()
    if not recording:
        raise HTTPException(status_code=404, detail="Note not found")
    return _note_to_dict(recording)


@router.patch("/api/notes/{note_id}")
async def api_update_note(
    note_id: int,
    update: NoteUpdate,
    db: Session = Depends(get_db)
):
    """Update a note's metadata."""
    recording = db.query(Recording).filter(Recording.id == note_id).first()
    if not recording:
        raise HTTPException(status_code=404, detail="Note not found")
    
    if update.title is not None:
        recording.title = update.title
    if update.tags is not None:
        recording.tags = ",".join(update.tags)
    
    db.commit()
    return {"success": True}


@router.post("/api/notes/{note_id}/reprocess")
async def api_reprocess_note(note_id: int, db: Session = Depends(get_db)):
    """Queue a note for reprocessing."""
    recording = db.query(Recording).filter(Recording.id == note_id).first()
    if not recording:
        raise HTTPException(status_code=404, detail="Note not found")
    
    recording.status = "pending"
    db.commit()
    
    # Would need to add to processing queue
    return {"success": True}


@router.get("/api/tasks")
async def api_get_tasks(
    filter: str = "pending",
    db: Session = Depends(get_db)
):
    """Get all tasks."""
    # Placeholder - would need task extraction
    return []


@router.patch("/api/tasks/{task_id}")
async def api_update_task(task_id: int, update: TaskUpdate):
    """Update a task's completion status."""
    # Placeholder - would need task storage
    return {"success": True}


@router.post("/api/upload")
async def api_upload(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """Upload an audio file."""
    import shutil
    from datetime import datetime
    
    # Validate file
    allowed_extensions = {'.m4a', '.mp3', '.wav', '.mp4', '.webm', '.ogg'}
    ext = Path(file.filename).suffix.lower()
    if ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Allowed: {', '.join(allowed_extensions)}"
        )
    
    # Save file
    upload_dir = Path("data/uploads")
    upload_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{timestamp}_{file.filename}"
    file_path = upload_dir / filename
    
    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    
    # Create recording entry
    recording = Recording(
        original_filename=file.filename,
        file_format=ext.lstrip('.'),
        title=Path(file.filename).stem,
        status="pending"
    )
    db.add(recording)
    db.commit()
    
    return {"success": True, "id": recording.id}


@router.get("/api/tags")
async def api_get_tags(q: str = "", db: Session = Depends(get_db)):
    """Search for tags (for autocomplete)."""
    # Get all unique tags from recordings
    recordings = db.query(Recording).filter(Recording.tags.isnot(None)).all()
    all_tags = set()
    for r in recordings:
        if r.tags:
            all_tags.update(t.strip() for t in r.tags.split(","))
    
    # Filter by query
    if q:
        q_lower = q.lower()
        all_tags = [t for t in all_tags if q_lower in t.lower()]
    
    return sorted(all_tags)[:10]


@router.get("/api/settings")
async def api_get_settings(db: Session = Depends(get_db)):
    """Get all settings."""
    from .database import get_all_settings
    return get_all_settings(db)


@router.put("/api/settings")
async def api_update_settings(settings: SettingsUpdate, db: Session = Depends(get_db)):
    """Update settings."""
    from .database import set_setting
    
    updates = settings.dict(exclude_unset=True)
    for key, value in updates.items():
        if value is not None:
            set_setting(db, key, str(value))
    
    return {"success": True}


@router.get("/api/stats")
async def api_get_stats(db: Session = Depends(get_db)):
    """Get dashboard statistics."""
    return _get_v2_stats()


# ============================================================================
# SYSTEM STATUS & LIVE MONITORING
# ============================================================================

def _get_watcher_status() -> dict:
    """Read watcher status from the engine registry."""
    import sqlite3
    registry_path = _get_registry_path()
    if not registry_path.exists():
        return {
            "state": "not_started",
            "current_file": None,
            "current_step": None,
            "last_scan_at": None,
            "scan_count": 0,
            "files_in_queue": 0,
            "updated_at": None,
        }
    try:
        conn = sqlite3.connect(str(registry_path))
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM watcher_status WHERE id = 1").fetchone()
        conn.close()
        if row:
            return dict(row)
        return {"state": "unknown"}
    except Exception as e:
        return {"state": "error", "error": str(e)}


def _get_api_key_status(db: Session) -> dict:
    """Get API key status from the main database."""
    from .database import APIKey
    try:
        keys = db.query(APIKey).all()
        active = [k for k in keys if k.is_active and not k.is_exhausted]
        exhausted = [k for k in keys if k.is_exhausted]
        return {
            "total": len(keys),
            "active": len(active),
            "exhausted": len(exhausted),
            "keys": [
                {
                    "id": k.id,
                    "name": k.name or f"Key {k.id}",
                    "is_active": k.is_active,
                    "is_exhausted": k.is_exhausted,
                    "total_requests": k.total_requests or 0,
                    "last_error": k.last_error,
                }
                for k in keys
            ],
        }
    except Exception as e:
        return {"total": 0, "active": 0, "exhausted": 0, "keys": [], "error": str(e)}


def _get_ingest_files(db: Session) -> list:
    """List audio files in the ingest directory with their processing status."""
    import sqlite3
    from .database import get_setting

    import os as _os
    audio_dir = get_setting(db, "LOCAL_SYNC_AUDIO_DIR", "") or _os.environ.get("LOCAL_SYNC_AUDIO_DIR", "")
    if not audio_dir:
        return []

    audio_path = Path(audio_dir)
    if not audio_path.exists():
        return []

    supported = {".mp3", ".m4a", ".wav", ".ogg", ".flac", ".webm", ".aac", ".opus", ".3gp"}

    # Build a lookup of processed filenames from registry
    processed_map = {}  # filename -> {status, error, processed_at, ...}
    registry_path = _get_registry_path()
    if registry_path.exists():
        try:
            conn = sqlite3.connect(str(registry_path))
            conn.row_factory = sqlite3.Row
            # Select both ingested_at and processed_at for fallback logic (line 1001)
            rows = conn.execute(
                "SELECT filename, file_hash, success, error, retry_count, processed_at, ingested_at, skipped, title "
                "FROM processed_files ORDER BY COALESCE(ingested_at, processed_at) DESC"
            ).fetchall()
            conn.close()
            for row in rows:
                d = dict(row)
                fn = d["filename"]
                if fn not in processed_map:  # Keep most recent
                    if d["success"]:
                        d["file_status"] = "completed"
                    elif d["skipped"]:
                        d["file_status"] = "skipped"
                    else:
                        d["file_status"] = "failed"
                    processed_map[fn] = d
        except Exception:
            pass

    # Check if watcher is currently processing a file
    watcher = _get_watcher_status()
    current_file = watcher.get("current_file")

    files = []
    try:
        for fp in sorted(audio_path.rglob("*")):
            if fp.is_file() and fp.suffix.lower() in supported:
                stat = fp.stat()
                name = fp.name
                rel_path = str(fp.relative_to(audio_path))
                
                info = processed_map.get(name)
                if current_file and name == current_file:
                    status = "processing"
                    error = None
                    title = None
                elif info:
                    status = info["file_status"]
                    error = info.get("error")
                    title = info.get("title")
                else:
                    status = "new"
                    error = None
                    title = None

                files.append({
                    "name": name,
                    "rel_path": rel_path,
                    "size_bytes": stat.st_size,
                    "size_mb": round(stat.st_size / (1024 * 1024), 2),
                    "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    "ingested_at": info.get("ingested_at") or info.get("processed_at") if info else None,
                    "status": status,
                    "error": error,
                    "title": title,
                    "retry_count": info.get("retry_count", 0) if info else 0,
                    "file_hash": info.get("file_hash", "") if info else "",
                })
    except Exception as e:
        logger.error(f"Failed to list ingest files: {e}")

    # Sort by ingested_at DESC (newest first), falling back to modified_at for new files
    files.sort(key=lambda f: f.get("ingested_at") or f.get("modified_at", ""), reverse=True)
    return files


def _get_failed_files() -> list:
    """Get failed files with retry status from registry."""
    import sqlite3

    MAX_RETRIES = 5
    RETRY_BACKOFF_MINUTES = [1, 5, 15, 60, 240]

    registry_path = _get_registry_path()
    if not registry_path.exists():
        return []
    try:
        conn = sqlite3.connect(str(registry_path))
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT filename, file_hash, error, retry_count, last_retry_at, skipped "
            "FROM processed_files WHERE success = 0 ORDER BY last_retry_at DESC"
        ).fetchall()
        conn.close()

        result = []
        for row in rows:
            d = dict(row)
            retry_count = d.get("retry_count") or 0
            skipped = d.get("skipped") or 0
            last_retry_at = d.get("last_retry_at")

            if skipped:
                d["next_retry"] = None
                d["file_status"] = "skipped"
            elif retry_count >= MAX_RETRIES:
                d["next_retry"] = None
                d["file_status"] = "max_retries"
            elif last_retry_at and retry_count > 0:
                from datetime import timedelta
                backoff_idx = min(retry_count - 1, len(RETRY_BACKOFF_MINUTES) - 1)
                backoff_mins = RETRY_BACKOFF_MINUTES[backoff_idx]
                last = datetime.fromisoformat(last_retry_at)
                next_retry = last + timedelta(minutes=backoff_mins)
                d["next_retry"] = next_retry.isoformat()
                d["file_status"] = "waiting" if datetime.utcnow() < next_retry else "ready"
            else:
                d["next_retry"] = datetime.utcnow().isoformat()
                d["file_status"] = "ready"
            result.append(d)
        return result
    except Exception as e:
        logger.error(f"Failed to read failed files: {e}")
        return []


@router.get("/api/system-status")
async def api_system_status(db: Session = Depends(get_db)):
    """Comprehensive system status for live dashboard polling.
    
    Returns watcher state, ingest folder contents, processing history,
    failed files, API key health — everything the dashboard needs.
    """
    from .database import get_setting
    
    watcher = _get_watcher_status()
    stats = _get_v2_stats()
    api_keys = _get_api_key_status(db)
    recent = _read_v2_registry(limit=30)
    failed = _get_failed_files()
    ingest = _get_ingest_files(db)
    
    # Current config 
    config = {
        "audio_input": get_setting(db, "LOCAL_SYNC_AUDIO_DIR", "Not configured"),
        "obsidian_vault": get_setting(db, "OBSIDIAN_VAULT_DIR", "Not configured"),
        "model": get_setting(db, "GEMINI_MODEL", "gemini-3-flash-preview"),
        "mode": get_setting(db, "PROCESSING_MODE", "personal_note"),
        "scan_interval": get_setting(db, "SCAN_INTERVAL", "5"),
    }

    return {
        "watcher": watcher,
        "stats": stats,
        "api_keys": api_keys,
        "recent_activity": recent,
        "failed_files": failed,
        "ingest_files": ingest,
        "config": config,
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.get("/api/ingest-files")
async def api_ingest_files(db: Session = Depends(get_db)):
    """List audio files in the ingest directory with processing status."""
    return _get_ingest_files(db)


@router.post("/api/clear-failed")
async def api_clear_failed():
    """Reset all failed files for retry."""
    import sqlite3
    registry_path = _get_registry_path()
    if not registry_path.exists():
        raise HTTPException(status_code=404, detail="Registry not found")
    try:
        conn = sqlite3.connect(str(registry_path))
        count = conn.execute("SELECT COUNT(*) FROM processed_files WHERE success = 0").fetchone()[0]
        conn.execute(
            "UPDATE processed_files SET retry_count = 0, last_retry_at = NULL, skipped = 0, error = NULL "
            "WHERE success = 0"
        )
        conn.commit()
        conn.close()
        return {"success": True, "reset_count": count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/skip-file/{file_hash}")
async def api_skip_file(file_hash: str):
    """Skip a failed file (won't be retried)."""
    import sqlite3
    registry_path = _get_registry_path()
    if not registry_path.exists():
        raise HTTPException(status_code=404, detail="Registry not found")
    try:
        conn = sqlite3.connect(str(registry_path))
        conn.execute("UPDATE processed_files SET skipped = 1 WHERE file_hash = ?", (file_hash,))
        conn.commit()
        conn.close()
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/retry-file/{file_hash}")
async def api_retry_file(file_hash: str):
    """Reset a failed file for immediate retry."""
    import sqlite3
    registry_path = _get_registry_path()
    if not registry_path.exists():
        raise HTTPException(status_code=404, detail="Registry not found")
    try:
        conn = sqlite3.connect(str(registry_path))
        conn.execute(
            "UPDATE processed_files SET skipped = 0, retry_count = 0, last_retry_at = NULL "
            "WHERE file_hash = ?",
            (file_hash,),
        )
        conn.commit()
        conn.close()
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/reset-exhausted-keys")
async def api_reset_exhausted_keys(db: Session = Depends(get_db)):
    """Reset all exhausted API keys back to active."""
    from .database import APIKey
    try:
        keys = db.query(APIKey).filter(APIKey.is_exhausted == True).all()
        for k in keys:
            k.is_exhausted = False
            k.exhausted_at = None
        db.commit()
        return {"success": True, "reset_count": len(keys)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# API KEY MANAGEMENT ENDPOINTS
# ============================================================================

class KeyAddRequest(BaseModel):
    key: str
    name: str = ""


@router.post("/api/keys/add")
async def api_add_key(body: KeyAddRequest, db: Session = Depends(get_db)):
    """Add a new API key."""
    from .database import APIKey
    
    if len(body.key.strip()) < 20:
        raise HTTPException(status_code=400, detail="Invalid API key format (too short)")
    
    api_key = APIKey(
        key=body.key.strip(),
        name=body.name.strip() if body.name else None,
        is_active=True,
        is_exhausted=False,
        total_requests=0,
        failed_requests=0,
    )
    db.add(api_key)
    db.commit()
    db.refresh(api_key)
    return {"success": True, "key_id": api_key.id}


@router.post("/api/keys/{key_id}/toggle")
async def api_toggle_key(key_id: int, db: Session = Depends(get_db)):
    """Toggle an API key's active status."""
    from .database import APIKey
    k = db.query(APIKey).filter(APIKey.id == key_id).first()
    if not k:
        raise HTTPException(status_code=404, detail="Key not found")
    k.is_active = not k.is_active
    db.commit()
    return {"success": True, "is_active": k.is_active}


@router.post("/api/keys/{key_id}/reset")
async def api_reset_key(key_id: int, db: Session = Depends(get_db)):
    """Reset a single exhausted API key."""
    from .database import APIKey
    k = db.query(APIKey).filter(APIKey.id == key_id).first()
    if not k:
        raise HTTPException(status_code=404, detail="Key not found")
    k.is_exhausted = False
    k.exhausted_at = None
    k.last_error = None
    db.commit()
    return {"success": True}


@router.delete("/api/keys/{key_id}")
async def api_delete_key(key_id: int, db: Session = Depends(get_db)):
    """Delete an API key."""
    from .database import APIKey
    k = db.query(APIKey).filter(APIKey.id == key_id).first()
    if not k:
        raise HTTPException(status_code=404, detail="Key not found")
    db.delete(k)
    db.commit()
    return {"success": True}


@router.get("/api/keys")
async def api_list_keys(db: Session = Depends(get_db)):
    """List all API keys with status."""
    from .database import APIKey
    keys = db.query(APIKey).order_by(APIKey.created_at).all()
    return {"keys": [
        {
            "id": k.id,
            "name": k.name or f"Key {k.id}",
            "key_preview": k.key[:6] + "..." + k.key[-4:] if k.key and len(k.key) > 12 else "***",
            "is_active": k.is_active,
            "is_exhausted": k.is_exhausted,
            "total_requests": k.total_requests or 0,
            "failed_requests": k.failed_requests or 0,
            "last_error": k.last_error,
            "last_used_at": k.last_used_at.isoformat() if k.last_used_at else None,
            "created_at": k.created_at.isoformat() if k.created_at else None,
            "exhausted_at": k.exhausted_at.isoformat() if k.exhausted_at else None,
        }
        for k in keys
    ]}


# ============================================================================
# CALENDAR / ROLLOVER ENDPOINTS
# ============================================================================

@router.get("/api/calendar-data")
async def api_calendar_data(
    year: int = 0,
    month: int = 0,
    db: Session = Depends(get_db),
):
    """Get calendar data: notes per day for heatmap + daily rollup content."""
    import sqlite3
    from .database import get_setting

    now = datetime.now()
    if year == 0:
        year = now.year
    if month == 0:
        month = now.month

    # Notes per day from registry
    daily_counts = {}
    daily_notes = {}
    registry_path = _get_registry_path()
    if registry_path.exists():
        try:
            conn = sqlite3.connect(str(registry_path))
            conn.row_factory = sqlite3.Row
            # Get daily counts for the month
            rows = conn.execute(
                "SELECT DATE(COALESCE(ingested_at, processed_at)) as day, COUNT(*) as cnt, "
                "SUM(CASE WHEN success=1 THEN 1 ELSE 0 END) as ok, "
                "SUM(CASE WHEN success=0 THEN 1 ELSE 0 END) as fail "
                "FROM processed_files "
                "WHERE strftime('%Y', COALESCE(ingested_at, processed_at)) = ? AND strftime('%m', COALESCE(ingested_at, processed_at)) = ? "
                "GROUP BY DATE(COALESCE(ingested_at, processed_at)) ORDER BY day",
                (str(year), f"{month:02d}")
            ).fetchall()
            for row in rows:
                daily_counts[row["day"]] = {
                    "total": row["cnt"], "success": row["ok"], "failed": row["fail"]
                }

            # Get individual notes for the month
            note_rows = conn.execute(
                "SELECT id, filename, title, mode, COALESCE(ingested_at, processed_at) as processed_at, success, error, "
                "duration_seconds, file_hash, has_tasks "
                "FROM processed_files "
                "WHERE strftime('%Y', COALESCE(ingested_at, processed_at)) = ? AND strftime('%m', COALESCE(ingested_at, processed_at)) = ? "
                "ORDER BY COALESCE(ingested_at, processed_at) DESC",
                (str(year), f"{month:02d}")
            ).fetchall()
            conn.close()
            for row in note_rows:
                d = dict(row)
                day = d["processed_at"][:10] if d.get("processed_at") else None
                if day:
                    if day not in daily_notes:
                        daily_notes[day] = []
                    daily_notes[day].append(d)
        except Exception as e:
            logger.error(f"Calendar data error: {e}")

    # Check for daily rollup files
    vault_dir = get_setting(db, "OBSIDIAN_VAULT_DIR", "")
    note_subdir = get_setting(db, "OBSIDIAN_NOTE_SUBDIR", "VoiceNotes")
    daily_rollups = {}
    if vault_dir:
        daily_dir = Path(vault_dir) / note_subdir / "Daily"
        if daily_dir.exists():
            for f in daily_dir.glob(f"{year}-{month:02d}-*.md"):
                day = f.stem  # e.g., "2026-02-15"
                try:
                    content = f.read_text(encoding="utf-8")
                    # Extract title
                    import re
                    title_match = re.search(r"^# (.+)$", content, re.MULTILINE)
                    daily_rollups[day] = {
                        "title": title_match.group(1) if title_match else f.stem,
                        "path": str(f),
                        "exists": True,
                    }
                except Exception:
                    daily_rollups[day] = {"title": f.stem, "exists": True}

    # Weekly rollups
    weekly_rollups = []
    if vault_dir:
        weekly_dir = Path(vault_dir) / note_subdir / "Weekly"
        if weekly_dir.exists():
            for f in sorted(weekly_dir.glob(f"{year}-W*.md")):
                try:
                    content = f.read_text(encoding="utf-8")
                    import re
                    title_match = re.search(r"^# (.+)$", content, re.MULTILINE)
                    weekly_rollups.append({
                        "filename": f.stem,
                        "title": title_match.group(1) if title_match else f.stem,
                        "exists": True,
                    })
                except Exception:
                    weekly_rollups.append({"filename": f.stem, "exists": True})

    return {
        "year": year,
        "month": month,
        "daily_counts": daily_counts,
        "daily_notes": daily_notes,
        "daily_rollups": daily_rollups,
        "weekly_rollups": weekly_rollups,
    }


# ============================================================================
# ARCHIVE ENDPOINTS
# ============================================================================

@router.get("/api/archive")
async def api_archive(
    page: int = 1,
    per_page: int = 50,
    status: str = "all",
    from_date: str = "",
    to_date: str = "",
):
    """Get paginated archive of all processed files."""
    import sqlite3
    registry_path = _get_registry_path()
    if not registry_path.exists():
        return {"items": [], "total": 0, "page": page, "per_page": per_page}

    try:
        conn = sqlite3.connect(str(registry_path))
        conn.row_factory = sqlite3.Row

        where_clauses = []
        params = []

        if status == "completed":
            where_clauses.append("success = 1")
        elif status == "failed":
            where_clauses.append("success = 0")

        if from_date:
            where_clauses.append("DATE(processed_at) >= ?")
            params.append(from_date)
        if to_date:
            where_clauses.append("DATE(processed_at) <= ?")
            params.append(to_date)

        where_sql = (" WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

        total = conn.execute(f"SELECT COUNT(*) FROM processed_files{where_sql}", params).fetchone()[0]

        offset = (page - 1) * per_page
        rows = conn.execute(
            f"SELECT id, filename, title, mode, COALESCE(ingested_at, processed_at) as processed_at, success, error, "
            f"duration_seconds, file_hash, retry_count, skipped, has_tasks "
            f"FROM processed_files{where_sql} "
            f"ORDER BY COALESCE(ingested_at, processed_at) DESC LIMIT ? OFFSET ?",
            params + [per_page, offset]
        ).fetchall()
        conn.close()

        items = []
        for row in rows:
            d = dict(row)
            d["status"] = "completed" if d["success"] else "failed"
            items.append(d)

        return {
            "items": items,
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": (total + per_page - 1) // per_page,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# REGISTRY CRUD ENDPOINTS
# ============================================================================

@router.delete("/api/registry/{note_id}")
async def api_delete_registry_note(note_id: int):
    """Delete a processed file entry from the registry."""
    import sqlite3
    registry_path = _get_registry_path()
    if not registry_path.exists():
        raise HTTPException(status_code=404, detail="Registry not found")
    try:
        conn = sqlite3.connect(str(registry_path))
        cursor = conn.execute("DELETE FROM processed_files WHERE id = ?", (note_id,))
        conn.commit()
        deleted = cursor.rowcount
        conn.close()
        if deleted == 0:
            raise HTTPException(status_code=404, detail="Note not found")
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/registry/{note_id}/reprocess")
async def api_reprocess_registry_note(note_id: int):
    """Reprocess a registry note by deleting it so the watcher picks it up again."""
    import sqlite3
    registry_path = _get_registry_path()
    if not registry_path.exists():
        raise HTTPException(status_code=404, detail="Registry not found")
    try:
        conn = sqlite3.connect(str(registry_path))
        cursor = conn.execute("DELETE FROM processed_files WHERE id = ?", (note_id,))
        conn.commit()
        deleted = cursor.rowcount
        conn.close()
        if deleted == 0:
            raise HTTPException(status_code=404, detail="Note not found")
        return {"success": True, "message": "Entry removed from registry. Watcher will reprocess on next scan."}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/registry/{note_id}/preview")
async def api_registry_preview(note_id: int, db: Session = Depends(get_db)):
    """Fetch content & transcript for a registry note (used by inbox preview)."""
    import sqlite3
    from .database import get_setting

    registry_path = _get_registry_path()
    if not registry_path.exists():
        raise HTTPException(status_code=404, detail="Registry not found")

    conn = sqlite3.connect(str(registry_path))
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT note_path, transcript_path, audio_path FROM processed_files WHERE id = ?", (note_id,)
    ).fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="Note not found")

    d = dict(row)
    vault_dir = get_setting(db, "OBSIDIAN_VAULT_DIR", "")

    def _try_read(path_str):
        if not path_str:
            return ""
        try:
            p = Path(path_str)
            if p.exists():
                return p.read_text(encoding="utf-8")
        except Exception:
            pass
        if vault_dir:
            try:
                p = Path(vault_dir) / path_str
                if p.exists():
                    return p.read_text(encoding="utf-8")
            except Exception:
                pass
        return ""

    # Build audio URL if audio file exists
    audio_url = None
    audio_path_str = d.get("audio_path", "")
    if audio_path_str:
        try:
            audio_path = Path(audio_path_str)
            if audio_path.exists():
                audio_url = f"/v2/api/registry/{note_id}/audio"
        except Exception:
            pass

    return {
        "content": _try_read(d.get("note_path")),
        "transcript": _try_read(d.get("transcript_path")),
        "audio_url": audio_url,
    }


# ============================================================================
# TAGS & PROJECTS ENDPOINTS
# ============================================================================

@router.get("/api/all-tags")
async def api_all_tags():
    """Get all unique tags from the registry with counts."""
    import sqlite3, json
    registry_path = _get_registry_path()
    if not registry_path.exists():
        return {"tags": []}
    
    conn = sqlite3.connect(str(registry_path))
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT tags FROM processed_files WHERE tags IS NOT NULL AND tags != '[]'").fetchall()
    conn.close()
    
    # Aggregate tags with counts
    tag_counts = {}
    for row in rows:
        try:
            tags = json.loads(row["tags"] or "[]")
            for tag in tags:
                tag = tag.strip().lower() if tag else ""
                if tag:
                    tag_counts[tag] = tag_counts.get(tag, 0) + 1
        except (json.JSONDecodeError, TypeError):
            pass
    
    # Sort by count desc, then alphabetically
    sorted_tags = sorted(tag_counts.items(), key=lambda x: (-x[1], x[0]))
    return {"tags": [{"name": t[0], "count": t[1]} for t in sorted_tags]}


@router.get("/api/all-projects")
async def api_all_projects(db: Session = Depends(get_db)):
    """Get all unique projects from the registry with counts, plus user-created project folders."""
    import sqlite3, json
    from .database import get_setting
    
    registry_path = _get_registry_path()
    project_counts = {}
    
    # Get projects from registry
    if registry_path.exists():
        conn = sqlite3.connect(str(registry_path))
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT projects FROM processed_files WHERE projects IS NOT NULL AND projects != '[]'").fetchall()
        conn.close()
        
        for row in rows:
            try:
                projects = json.loads(row["projects"] or "[]")
                for proj in projects:
                    proj = proj.strip() if proj else ""
                    if proj:
                        project_counts[proj] = project_counts.get(proj, 0) + 1
            except (json.JSONDecodeError, TypeError):
                pass
    
    # Also check for project folders in Obsidian
    vault_dir = get_setting(db, "OBSIDIAN_VAULT_DIR", "")
    note_subdir = get_setting(db, "OBSIDIAN_NOTE_SUBDIR", "VoiceNotes")
    project_folders = []
    
    if vault_dir:
        projects_dir = Path(vault_dir) / note_subdir / "Projects"
        if projects_dir.exists():
            for folder in projects_dir.iterdir():
                if folder.is_dir():
                    folder_name = folder.name
                    if folder_name not in project_counts:
                        project_counts[folder_name] = 0
                    project_folders.append(folder_name)
    
    # Sort by count desc, then alphabetically
    sorted_projects = sorted(project_counts.items(), key=lambda x: (-x[1], x[0]))
    return {
        "projects": [{"name": p[0], "count": p[1], "has_folder": p[0] in project_folders} for p in sorted_projects],
        "projects_dir": str(Path(vault_dir) / note_subdir / "Projects") if vault_dir else None
    }


@router.post("/api/projects")
async def api_create_project(request: Request, db: Session = Depends(get_db)):
    """Create a new project folder in Obsidian. Body: { "name": "Project Name" }"""
    from .database import get_setting
    
    body = await request.json()
    name = body.get("name", "").strip()
    
    if not name:
        raise HTTPException(status_code=400, detail="Project name is required")
    
    vault_dir = get_setting(db, "OBSIDIAN_VAULT_DIR", "")
    if not vault_dir:
        raise HTTPException(status_code=400, detail="Obsidian vault not configured")
    
    note_subdir = get_setting(db, "OBSIDIAN_NOTE_SUBDIR", "VoiceNotes")
    projects_dir = Path(vault_dir) / note_subdir / "Projects"
    project_folder = projects_dir / name
    
    if project_folder.exists():
        raise HTTPException(status_code=400, detail="Project already exists")
    
    try:
        project_folder.mkdir(parents=True, exist_ok=True)
        return {"success": True, "name": name, "path": str(project_folder)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/api/projects/{project_name}")
async def api_delete_project(project_name: str, db: Session = Depends(get_db)):
    """Delete a project folder (must be empty). URL encoded project name."""
    from .database import get_setting
    import urllib.parse
    
    name = urllib.parse.unquote(project_name)
    
    vault_dir = get_setting(db, "OBSIDIAN_VAULT_DIR", "")
    if not vault_dir:
        raise HTTPException(status_code=400, detail="Obsidian vault not configured")
    
    note_subdir = get_setting(db, "OBSIDIAN_NOTE_SUBDIR", "VoiceNotes")
    project_folder = Path(vault_dir) / note_subdir / "Projects" / name
    
    if not project_folder.exists():
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Check if folder is empty
    contents = list(project_folder.iterdir())
    if contents:
        raise HTTPException(status_code=400, detail=f"Project folder is not empty ({len(contents)} items)")
    
    try:
        project_folder.rmdir()
        return {"success": True, "name": name}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/api/registry/{note_id}/tags")
async def api_update_tags(note_id: int, request: Request, db: Session = Depends(get_db)):
    """Update tags for a registry note and sync to Obsidian file. Body: { "tags": ["tag1", "tag2"] }"""
    import sqlite3, json, re
    from .database import get_setting
    
    body = await request.json()
    tags = body.get("tags", [])
    registry_path = _get_registry_path()
    if not registry_path.exists():
        raise HTTPException(status_code=404, detail="Registry not found")
    try:
        conn = sqlite3.connect(str(registry_path))
        conn.row_factory = sqlite3.Row
        
        # Get the note path first
        row = conn.execute("SELECT note_path FROM processed_files WHERE id = ?", (note_id,)).fetchone()
        if not row:
            conn.close()
            raise HTTPException(status_code=404, detail="Note not found")
        
        note_path = row["note_path"]
        
        # Update registry
        conn.execute("UPDATE processed_files SET tags = ? WHERE id = ?", (json.dumps(tags), note_id))
        conn.commit()
        conn.close()
        
        # Update Obsidian file if it exists
        obsidian_updated = False
        if note_path:
            file_path = Path(note_path)
            if file_path.exists():
                try:
                    content = file_path.read_text(encoding="utf-8")
                    # Update tags in frontmatter
                    tags_yaml = f"tags: [{', '.join(repr(t) for t in tags)}]" if tags else "tags: []"
                    content = re.sub(r'^tags:.*$', tags_yaml, content, count=1, flags=re.MULTILINE)
                    file_path.write_text(content, encoding="utf-8")
                    obsidian_updated = True
                except Exception as e:
                    logger.warning(f"Failed to update Obsidian file: {e}")
        
        return {"success": True, "tags": tags, "obsidian_updated": obsidian_updated}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/api/registry/{note_id}/projects")
async def api_update_projects(note_id: int, request: Request, db: Session = Depends(get_db)):
    """Update project assignments for a registry note and sync to Obsidian file. Body: { "projects": ["proj1"] }"""
    import sqlite3, json, re
    from .database import get_setting
    
    body = await request.json()
    projects = body.get("projects", [])
    registry_path = _get_registry_path()
    if not registry_path.exists():
        raise HTTPException(status_code=404, detail="Registry not found")
    try:
        conn = sqlite3.connect(str(registry_path))
        conn.row_factory = sqlite3.Row
        
        # Get the note path first
        row = conn.execute("SELECT note_path FROM processed_files WHERE id = ?", (note_id,)).fetchone()
        if not row:
            conn.close()
            raise HTTPException(status_code=404, detail="Note not found")
        
        note_path = row["note_path"]
        
        # Update registry
        conn.execute("UPDATE processed_files SET projects = ? WHERE id = ?", (json.dumps(projects), note_id))
        conn.commit()
        conn.close()
        
        # Update Obsidian file if it exists
        obsidian_updated = False
        vault_dir = get_setting(db, "OBSIDIAN_VAULT_DIR", "")
        
        if note_path:
            file_path = Path(note_path)
            if file_path.exists():
                try:
                    content = file_path.read_text(encoding="utf-8")
                    
                    # Check if projects field exists in frontmatter
                    projects_yaml = f"projects: [{', '.join(repr(p) for p in projects)}]" if projects else "projects: []"
                    
                    if re.search(r'^projects:', content, flags=re.MULTILINE):
                        # Update existing projects field
                        content = re.sub(r'^projects:.*$', projects_yaml, content, count=1, flags=re.MULTILINE)
                    else:
                        # Add projects field after tags
                        content = re.sub(r'^(tags:.*?)$', r'\1\n' + projects_yaml, content, count=1, flags=re.MULTILINE)
                    
                    file_path.write_text(content, encoding="utf-8")
                    obsidian_updated = True
                except Exception as e:
                    logger.warning(f"Failed to update Obsidian file: {e}")
        
        # Create project folders if they don't exist
        folders_created = []
        if vault_dir and projects:
            note_subdir = get_setting(db, "OBSIDIAN_NOTE_SUBDIR", "VoiceNotes")
            projects_dir = Path(vault_dir) / note_subdir / "Projects"
            projects_dir.mkdir(parents=True, exist_ok=True)
            
            for proj in projects:
                proj_folder = projects_dir / proj
                if not proj_folder.exists():
                    proj_folder.mkdir(parents=True, exist_ok=True)
                    folders_created.append(proj)
        
        return {"success": True, "projects": projects, "obsidian_updated": obsidian_updated, "folders_created": folders_created}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/registry/{note_id}/download/{file_type}")
async def api_download_file(note_id: int, file_type: str):
    """Download note content or transcript as a file. file_type: 'note' or 'transcript'."""
    import sqlite3
    from .database import get_db as _get_db_raw
    registry_path = _get_registry_path()
    if not registry_path.exists():
        raise HTTPException(status_code=404, detail="Registry not found")

    conn = sqlite3.connect(str(registry_path))
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT filename, note_path, transcript_path FROM processed_files WHERE id = ?",
        (note_id,)
    ).fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="Note not found")

    d = dict(row)
    path_key = "note_path" if file_type == "note" else "transcript_path"
    file_path_str = d.get(path_key, "")

    if not file_path_str:
        raise HTTPException(status_code=404, detail=f"No {file_type} file path stored")

    # Try absolute path, then vault-relative
    from pathlib import Path as PPath
    content = ""
    for try_path in [PPath(file_path_str)]:
        if try_path.exists():
            content = try_path.read_text(encoding="utf-8")
            break

    if not content:
        # Try vault-relative
        vault_dir = os.environ.get("OBSIDIAN_VAULT_DIR", "")
        if vault_dir:
            try_path = PPath(vault_dir) / file_path_str
            if try_path.exists():
                content = try_path.read_text(encoding="utf-8")

    if not content:
        raise HTTPException(status_code=404, detail=f"{file_type.title()} file not found on disk")

    stem = PPath(d["filename"]).stem
    suffix = "note" if file_type == "note" else "transcript"
    download_name = f"{stem}_{suffix}.md"

    from fastapi.responses import Response
    return Response(
        content=content,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{download_name}"'}
    )


@router.get("/api/registry/{note_id}/audio")
async def api_registry_audio(note_id: int):
    """Serve stored compressed audio for a registry note."""
    import sqlite3
    registry_path = _get_registry_path()
    if not registry_path.exists():
        raise HTTPException(status_code=404, detail="Registry not found")

    conn = sqlite3.connect(str(registry_path))
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT audio_path, filename FROM processed_files WHERE id = ?", (note_id,)
    ).fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="Note not found")

    audio_path_str = row["audio_path"] if row["audio_path"] else ""
    if not audio_path_str:
        raise HTTPException(status_code=404, detail="No audio stored for this note")

    audio_path = Path(audio_path_str)
    if not audio_path.exists():
        raise HTTPException(status_code=404, detail="Audio file not found on disk")

    # Determine MIME type from extension
    ext = audio_path.suffix.lower()
    mime_map = {
        ".opus": "audio/ogg",
        ".ogg": "audio/ogg",
        ".mp3": "audio/mpeg",
        ".m4a": "audio/mp4",
        ".wav": "audio/wav",
        ".webm": "audio/webm",
        ".aac": "audio/aac",
        ".flac": "audio/flac",
    }
    mime = mime_map.get(ext, "audio/ogg")

    from fastapi.responses import FileResponse
    return FileResponse(
        path=str(audio_path),
        media_type=mime,
        filename=row["filename"],
    )
