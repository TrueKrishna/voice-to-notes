"""
Tag-based routing and file copying.

Copies notes from Inbox to project folders based on tags.
Inbox note is preserved (source of truth), project folder gets a copy.
"""

import logging
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


# =============================================================================
# TAG ROUTES CONFIGURATION
# =============================================================================

# Default tag → folder mappings
# Can be overridden via database settings or UI
DEFAULT_TAG_ROUTES = {
    # Example mappings - these would be configured by user
    # "AlumERP": "Projects/AlumERP",
    # "Personal": "Personal",
    # "Work": "Work/General",
}


def get_tag_routes(db_path: Optional[str] = None) -> dict[str, str]:
    """Get tag → folder route mappings.
    
    Priority: Database > Default config
    
    Args:
        db_path: Path to the V1 app database for settings lookup
        
    Returns:
        Dict mapping tag names to relative folder paths
    """
    routes = DEFAULT_TAG_ROUTES.copy()
    
    # Try to load from database
    if db_path:
        try:
            import sqlite3
            conn = sqlite3.connect(db_path)
            cursor = conn.execute(
                "SELECT key, value FROM settings WHERE key LIKE 'tag_route_%'"
            )
            for row in cursor.fetchall():
                # key format: tag_route_AlumERP -> AlumERP
                tag_name = row[0].replace("tag_route_", "")
                folder_path = row[1]
                routes[tag_name] = folder_path
            conn.close()
        except Exception as e:
            logger.debug(f"Could not load tag routes from DB: {e}")
    
    return routes


def set_tag_route(tag_name: str, folder_path: str, db_path: str) -> bool:
    """Set a tag → folder route mapping in the database.
    
    Args:
        tag_name: Tag name (e.g., "AlumERP")
        folder_path: Relative folder path (e.g., "Projects/AlumERP")
        db_path: Path to the database
        
    Returns:
        True if successful, False otherwise
    """
    try:
        import sqlite3
        conn = sqlite3.connect(db_path)
        key = f"tag_route_{tag_name}"
        conn.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            (key, folder_path)
        )
        conn.commit()
        conn.close()
        logger.info(f"Tag route set: {tag_name} → {folder_path}")
        return True
    except Exception as e:
        logger.error(f"Failed to set tag route: {e}")
        return False


def delete_tag_route(tag_name: str, db_path: str) -> bool:
    """Delete a tag → folder route mapping from the database.
    
    Args:
        tag_name: Tag name to remove
        db_path: Path to the database
        
    Returns:
        True if successful, False otherwise
    """
    try:
        import sqlite3
        conn = sqlite3.connect(db_path)
        key = f"tag_route_{tag_name}"
        conn.execute("DELETE FROM settings WHERE key = ?", (key,))
        conn.commit()
        conn.close()
        logger.info(f"Tag route deleted: {tag_name}")
        return True
    except Exception as e:
        logger.error(f"Failed to delete tag route: {e}")
        return False


# =============================================================================
# NOTE COPYING
# =============================================================================

def copy_note_to_project(
    inbox_note_path: Path,
    projects_dir: Path,
    tags: list[str],
    tag_routes: Optional[dict[str, str]] = None,
) -> list[Path]:
    """Copy an inbox note to project folder(s) based on tags.
    
    The inbox note is updated with tags in frontmatter but stays in place.
    Copies are created in the appropriate project folders.
    
    Args:
        inbox_note_path: Path to the inbox note
        projects_dir: Base directory for projects (e.g., VoiceNotes/Projects)
        tags: List of tags to apply
        tag_routes: Tag → folder mappings (optional, uses defaults if not provided)
        
    Returns:
        List of paths where copies were created
    """
    if not inbox_note_path.exists():
        logger.error(f"Inbox note not found: {inbox_note_path}")
        return []
    
    routes = tag_routes or DEFAULT_TAG_ROUTES
    copied_paths = []
    
    # First, update the inbox note's frontmatter with tags
    _update_note_tags(inbox_note_path, tags)
    
    # Copy to each tag's folder
    for tag in tags:
        if tag in routes:
            dest_folder = projects_dir / routes[tag]
        else:
            # Use tag name as folder if no route configured
            dest_folder = projects_dir / tag
        
        dest_folder.mkdir(parents=True, exist_ok=True)
        dest_path = dest_folder / inbox_note_path.name
        
        # Handle collision
        if dest_path.exists():
            stem = dest_path.stem
            suffix = dest_path.suffix
            counter = 1
            while dest_path.exists():
                dest_path = dest_folder / f"{stem}_{counter}{suffix}"
                counter += 1
        
        # Copy the file
        shutil.copy2(inbox_note_path, dest_path)
        
        # Update the copy's frontmatter to indicate it's a copy
        _mark_as_copy(dest_path, inbox_note_path)
        
        copied_paths.append(dest_path)
        logger.info(f"Note copied: {dest_path}")
    
    return copied_paths


def _update_note_tags(note_path: Path, tags: list[str]) -> None:
    """Update the tags in a note's YAML frontmatter."""
    content = note_path.read_text(encoding="utf-8")
    
    # Find and replace tags line
    tags_str = ", ".join(f'"{t}"' for t in tags)
    new_tags_line = f"tags: [{tags_str}]"
    
    # Replace existing tags line
    content = re.sub(
        r"^tags:\s*\[.*?\]$",
        new_tags_line,
        content,
        flags=re.MULTILINE
    )
    
    # Update status to reviewed
    content = re.sub(
        r"^status:\s*\w+$",
        "status: reviewed",
        content,
        flags=re.MULTILINE
    )
    
    note_path.write_text(content, encoding="utf-8")


def _mark_as_copy(copy_path: Path, source_path: Path) -> None:
    """Mark a copied note as a copy in its frontmatter."""
    content = copy_path.read_text(encoding="utf-8")
    
    # Add copy_of field after the type field
    source_name = source_path.stem
    copy_of_line = f"copy_of: \"[[Inbox/{source_name}]]\""
    
    # Insert after type: voice-note line
    content = re.sub(
        r"(^type:\s*voice-note$)",
        f"\\1\n{copy_of_line}",
        content,
        flags=re.MULTILINE
    )
    
    copy_path.write_text(content, encoding="utf-8")


# =============================================================================
# UTILITIES
# =============================================================================

def get_note_tags(note_path: Path) -> list[str]:
    """Read tags from a note's frontmatter.
    
    Args:
        note_path: Path to the note file
        
    Returns:
        List of tag strings (empty if no tags)
    """
    if not note_path.exists():
        return []
    
    content = note_path.read_text(encoding="utf-8")
    
    # Parse tags from frontmatter
    tags_match = re.search(r"^tags:\s*\[([^\]]*)\]$", content, re.MULTILINE)
    if not tags_match:
        return []
    
    tags_str = tags_match.group(1)
    if not tags_str.strip():
        return []
    
    # Parse individual tags (quoted strings)
    tags = re.findall(r'"([^"]+)"', tags_str)
    return tags


def get_inbox_notes(inbox_dir: Path, status: Optional[str] = None) -> list[dict]:
    """List all notes in the inbox.
    
    Args:
        inbox_dir: Path to the inbox directory
        status: Filter by status (inbox, reviewed, archived) or None for all
        
    Returns:
        List of dicts with note info (path, name, title, status, tags, has_tasks)
    """
    notes = []
    
    if not inbox_dir.exists():
        return notes
    
    for note_path in inbox_dir.glob("*.md"):
        try:
            content = note_path.read_text(encoding="utf-8")
            
            # Extract metadata
            title_match = re.search(r"^# (.+)$", content, re.MULTILINE)
            title = title_match.group(1) if title_match else note_path.stem
            
            status_match = re.search(r"^status:\s*(\w+)$", content, re.MULTILINE)
            note_status = status_match.group(1) if status_match else "inbox"
            
            # Filter by status if specified
            if status and note_status != status:
                continue
            
            tags = get_note_tags(note_path)
            
            has_tasks_match = re.search(r"^has_tasks:\s*(.+)$", content, re.MULTILINE)
            has_tasks = has_tasks_match and has_tasks_match.group(1).lower() == "true"
            
            mode_match = re.search(r"^mode:\s*(.+)$", content, re.MULTILINE)
            mode = mode_match.group(1) if mode_match else "unknown"
            
            recorded_match = re.search(r"^recorded:\s*(.+)$", content, re.MULTILINE)
            recorded = recorded_match.group(1) if recorded_match else None
            
            notes.append({
                "path": note_path,
                "name": note_path.stem,
                "title": title,
                "status": note_status,
                "tags": tags,
                "has_tasks": has_tasks,
                "mode": mode,
                "recorded": recorded,
            })
        except Exception as e:
            logger.warning(f"Could not parse note {note_path}: {e}")
    
    # Sort by name (date-first naming means chronological order)
    notes.sort(key=lambda n: n["name"], reverse=True)
    
    return notes
