"""
Task extraction and daily task file management.

Extracts actionable tasks from voice recordings and aggregates them
into daily task files in Obsidian-compatible format.
"""

import logging
import re
from datetime import datetime, date
from pathlib import Path
from typing import Optional

from .models import ExtractedTask, ProcessingResult
from .prompts import get_task_extraction_prompt

logger = logging.getLogger(__name__)


def extract_tasks_from_content(
    structured_content: str,
    transcript: str,
    ai_client,
) -> list[ExtractedTask]:
    """Extract tasks from structured content using AI.
    
    Args:
        structured_content: The AI-generated structured breakdown
        transcript: The raw transcript for additional context
        ai_client: GeminiClient instance for AI calls
        
    Returns:
        List of ExtractedTask objects
    """
    prompt_template = get_task_extraction_prompt()
    prompt = prompt_template.format(
        content=structured_content[:4000],  # Limit content size
        transcript=transcript[:2000],  # Limit transcript size
    )
    
    try:
        # GeminiClient.structure(transcript, prompt) - pass empty string as "transcript"
        # since we've embedded all content in the prompt itself
        response = ai_client.structure("", prompt)
        
        return _parse_task_response(response)
    except Exception as e:
        logger.warning(f"Task extraction failed: {e}")
        return []


def _parse_task_response(response: str) -> list[ExtractedTask]:
    """Parse AI response into ExtractedTask objects."""
    tasks = []
    
    if "NO_TASKS" in response.upper():
        return tasks
    
    # Parse lines matching: TASK: ... | DUE: ... | ASSIGNEE: ... | PRIORITY: ...
    pattern = r"TASK:\s*(.+?)\s*\|\s*DUE:\s*(.+?)\s*\|\s*ASSIGNEE:\s*(.+?)\s*\|\s*PRIORITY:\s*(\w+)"
    
    for match in re.finditer(pattern, response, re.IGNORECASE):
        text = match.group(1).strip()
        due = match.group(2).strip()
        assignee = match.group(3).strip()
        priority = match.group(4).strip().lower()
        
        # Normalize values
        if due.lower() in ("none", "n/a", "-", ""):
            due = None
        if assignee.lower() in ("self", "me", "-", ""):
            assignee = None
        if priority not in ("high", "medium", "low"):
            priority = "medium"
        
        tasks.append(ExtractedTask(
            text=text,
            due_date=due,
            assignee=assignee,
            priority=priority,
        ))
    
    return tasks


# =============================================================================
# DAILY TASK FILE MANAGEMENT
# =============================================================================

def get_daily_task_file_path(tasks_dir: Path, for_date: Optional[date] = None) -> Path:
    """Get the path to the daily task file.
    
    Format: Tasks/YYYY-MM-DD.md
    """
    target_date = for_date or date.today()
    return tasks_dir / f"{target_date.isoformat()}.md"


def append_tasks_to_daily_file(
    tasks: list[ExtractedTask],
    source_note_path: Path,
    tasks_dir: Path,
    for_date: Optional[date] = None,
) -> Path:
    """Append extracted tasks to the daily task file.
    
    Creates the file if it doesn't exist, otherwise appends to it.
    
    Args:
        tasks: List of ExtractedTask objects
        source_note_path: Path to the source note (for backlinks)
        tasks_dir: Directory for task files
        for_date: Date for the task file (default: today)
        
    Returns:
        Path to the daily task file
    """
    if not tasks:
        return None
    
    tasks_dir.mkdir(parents=True, exist_ok=True)
    task_file = get_daily_task_file_path(tasks_dir, for_date)
    
    # Get relative path for backlink (just the filename without extension)
    source_name = source_note_path.stem
    
    # Build task entries
    task_lines = []
    for task in tasks:
        # Build the checkbox line
        checkbox = f"- [ ] {task.text}"
        
        # Add metadata inline
        meta_parts = []
        if task.due_date:
            meta_parts.append(f"📅 {task.due_date}")
        if task.assignee:
            meta_parts.append(f"👤 {task.assignee}")
        if task.priority == "high":
            meta_parts.append("🔴")
        elif task.priority == "low":
            meta_parts.append("🟢")
        
        if meta_parts:
            checkbox += f" ({', '.join(meta_parts)})"
        
        # Add source backlink
        checkbox += f" [[Inbox/{source_name}|source]]"
        task_lines.append(checkbox)
    
    # Check if file exists
    if task_file.exists():
        # Append to existing file
        content = task_file.read_text(encoding="utf-8")
        
        # Add a section for this source
        new_section = f"\n### From: [[Inbox/{source_name}]]\n\n"
        new_section += "\n".join(task_lines)
        new_section += "\n"
        
        content += new_section
        task_file.write_text(content, encoding="utf-8")
    else:
        # Create new file with header
        target_date = for_date or date.today()
        header = _build_daily_task_header(target_date)
        
        content = header
        content += f"\n## From Voice Notes\n\n"
        content += f"### From: [[Inbox/{source_name}]]\n\n"
        content += "\n".join(task_lines)
        content += "\n"
        
        task_file.write_text(content, encoding="utf-8")
    
    logger.info(f"Added {len(tasks)} tasks to {task_file}")
    return task_file


def _build_daily_task_header(for_date: date) -> str:
    """Build the YAML frontmatter and header for a daily task file."""
    lines = [
        "---",
        "type: daily-tasks",
        f"date: {for_date.isoformat()}",
        f"created: {datetime.now().isoformat()}",
        "---",
        "",
        f"# Tasks: {for_date.strftime('%d_%m_%y')}",
        "",
    ]
    return "\n".join(lines)


# =============================================================================
# TASK AGGREGATION HELPERS
# =============================================================================

def get_tasks_for_date(tasks_dir: Path, for_date: date) -> list[dict]:
    """Read tasks from a daily task file.
    
    Returns list of task dicts with text, completed status, source, etc.
    """
    task_file = get_daily_task_file_path(tasks_dir, for_date)
    
    if not task_file.exists():
        return []
    
    content = task_file.read_text(encoding="utf-8")
    tasks = []
    
    # Parse checkbox lines
    checkbox_pattern = r"- \[([ x])\] (.+)"
    for match in re.finditer(checkbox_pattern, content):
        completed = match.group(1).lower() == "x"
        text = match.group(2)
        
        # Extract source backlink if present
        source_match = re.search(r"\[\[Inbox/([^\]|]+)", text)
        source = source_match.group(1) if source_match else None
        
        # Clean the text (remove metadata and backlink)
        clean_text = re.sub(r"\s*\([^)]+\)\s*\[\[.+?\]\]$", "", text).strip()
        
        tasks.append({
            "text": clean_text,
            "completed": completed,
            "source": source,
            "raw": text,
        })
    
    return tasks


def count_tasks_for_date(tasks_dir: Path, for_date: date) -> dict:
    """Count tasks for a date (total, completed, pending)."""
    tasks = get_tasks_for_date(tasks_dir, for_date)
    
    total = len(tasks)
    completed = sum(1 for t in tasks if t["completed"])
    pending = total - completed
    
    return {
        "total": total,
        "completed": completed,
        "pending": pending,
    }
