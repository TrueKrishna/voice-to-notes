"""
Daily and weekly rollup generation.

Generates summary notes that aggregate recordings, tasks, and insights
from voice notes over a period.
"""

import logging
import re
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


# =============================================================================
# DAILY ROLLUP
# =============================================================================

def generate_daily_rollup(
    daily_dir: Path,
    inbox_dir: Path,
    tasks_dir: Path,
    for_date: Optional[date] = None,
) -> Path:
    """Generate a daily summary file.
    
    Aggregates:
    - All voice notes processed that day
    - Tasks extracted
    - Quick stats
    
    Args:
        daily_dir: Directory for daily summary files
        inbox_dir: Inbox directory to scan for notes
        tasks_dir: Tasks directory to read task counts
        for_date: Date for the summary (default: today)
        
    Returns:
        Path to the generated daily summary file
    """
    target_date = for_date or date.today()
    daily_dir.mkdir(parents=True, exist_ok=True)
    
    daily_file = daily_dir / f"{target_date.isoformat()}.md"
    
    # Find notes processed on this date
    notes = _find_notes_for_date(inbox_dir, target_date)
    
    # Get task stats
    task_stats = _get_task_stats_for_date(tasks_dir, target_date)
    
    # Build content
    content = _build_daily_content(target_date, notes, task_stats)
    
    daily_file.write_text(content, encoding="utf-8")
    logger.info(f"Daily rollup generated: {daily_file}")
    
    return daily_file


def _find_notes_for_date(inbox_dir: Path, target_date: date) -> list[dict]:
    """Find all notes in inbox that match the target date.
    
    Notes are named: DD_MM_YY_slug.md
    """
    notes = []
    date_prefix = target_date.strftime("%d_%m_%y")
    
    if not inbox_dir.exists():
        return notes
    
    for note_path in inbox_dir.glob(f"{date_prefix}_*.md"):
        try:
            content = note_path.read_text(encoding="utf-8")
            
            # Extract title (first # heading)
            title_match = re.search(r"^# (.+)$", content, re.MULTILINE)
            title = title_match.group(1) if title_match else note_path.stem
            
            # Extract mode from frontmatter
            mode_match = re.search(r"^mode:\s*(.+)$", content, re.MULTILINE)
            mode = mode_match.group(1) if mode_match else "unknown"
            
            # Check for tasks
            has_tasks_match = re.search(r"^has_tasks:\s*(.+)$", content, re.MULTILINE)
            has_tasks = has_tasks_match and has_tasks_match.group(1).lower() == "true"
            
            # Extract duration
            duration_match = re.search(r"^duration_min:\s*(\d+)$", content, re.MULTILINE)
            duration_min = int(duration_match.group(1)) if duration_match else 0
            
            notes.append({
                "path": note_path,
                "name": note_path.stem,
                "title": title,
                "mode": mode,
                "has_tasks": has_tasks,
                "duration_min": duration_min,
            })
        except Exception as e:
            logger.warning(f"Could not parse note {note_path}: {e}")
    
    return notes


def _get_task_stats_for_date(tasks_dir: Path, target_date: date) -> dict:
    """Get task statistics for a date."""
    task_file = tasks_dir / f"{target_date.isoformat()}.md"
    
    if not task_file.exists():
        return {"total": 0, "completed": 0, "pending": 0}
    
    content = task_file.read_text(encoding="utf-8")
    
    # Count checkboxes
    total = len(re.findall(r"- \[[ x]\]", content))
    completed = len(re.findall(r"- \[x\]", content, re.IGNORECASE))
    pending = total - completed
    
    return {"total": total, "completed": completed, "pending": pending}


def _build_daily_content(target_date: date, notes: list[dict], task_stats: dict) -> str:
    """Build the daily summary markdown content."""
    date_str = target_date.strftime("%d_%m_%y")
    iso_date = target_date.isoformat()
    
    lines = [
        "---",
        "type: daily-summary",
        f"date: {iso_date}",
        f"generated: {datetime.now().isoformat()}",
        f"note_count: {len(notes)}",
        f"task_count: {task_stats['total']}",
        "---",
        "",
        f"# Daily Summary: {date_str}",
        "",
        "## 📊 Quick Stats",
        "",
        f"- **Voice Notes**: {len(notes)}",
        f"- **Total Duration**: {sum(n['duration_min'] for n in notes)} min",
        f"- **Tasks Extracted**: {task_stats['total']}",
        f"- **Tasks Completed**: {task_stats['completed']}",
        f"- **Tasks Pending**: {task_stats['pending']}",
        "",
    ]
    
    if notes:
        lines.extend([
            "## 📝 Voice Notes",
            "",
        ])
        
        for note in notes:
            status = "✅" if not note["has_tasks"] else "📋"
            lines.append(f"- {status} [[Inbox/{note['name']}|{note['title']}]] ({note['mode']}, {note['duration_min']}min)")
        
        lines.append("")
    
    if task_stats["pending"] > 0:
        lines.extend([
            "## ✅ Open Tasks",
            "",
            f"See [[Tasks/{iso_date}|Today's Tasks]] for the full list.",
            "",
        ])
    
    lines.extend([
        "---",
        "",
        "*Generated automatically by Voice-to-Notes Engine*",
    ])
    
    return "\n".join(lines)


# =============================================================================
# WEEKLY ROLLUP
# =============================================================================

def generate_weekly_rollup(
    weekly_dir: Path,
    inbox_dir: Path,
    tasks_dir: Path,
    for_date: Optional[date] = None,
) -> Path:
    """Generate a weekly summary file.
    
    Aggregates all notes and tasks from a week.
    
    Args:
        weekly_dir: Directory for weekly summary files
        inbox_dir: Inbox directory to scan for notes
        tasks_dir: Tasks directory to read task counts
        for_date: Any date within the target week (default: today)
        
    Returns:
        Path to the generated weekly summary file
    """
    target_date = for_date or date.today()
    weekly_dir.mkdir(parents=True, exist_ok=True)
    
    # Get ISO week number
    year, week_num, _ = target_date.isocalendar()
    weekly_file = weekly_dir / f"{year}-W{week_num:02d}.md"
    
    # Calculate week boundaries (Monday to Sunday)
    week_start = target_date - timedelta(days=target_date.weekday())
    week_end = week_start + timedelta(days=6)
    
    # Collect notes and tasks for the entire week
    all_notes = []
    total_tasks = {"total": 0, "completed": 0, "pending": 0}
    daily_stats = []
    
    for i in range(7):
        day = week_start + timedelta(days=i)
        
        # Notes for this day
        day_notes = _find_notes_for_date(inbox_dir, day)
        all_notes.extend(day_notes)
        
        # Task stats for this day
        day_tasks = _get_task_stats_for_date(tasks_dir, day)
        total_tasks["total"] += day_tasks["total"]
        total_tasks["completed"] += day_tasks["completed"]
        total_tasks["pending"] += day_tasks["pending"]
        
        if day_notes or day_tasks["total"] > 0:
            daily_stats.append({
                "date": day,
                "notes": len(day_notes),
                "tasks": day_tasks["total"],
            })
    
    # Build content
    content = _build_weekly_content(
        year, week_num, week_start, week_end,
        all_notes, total_tasks, daily_stats
    )
    
    weekly_file.write_text(content, encoding="utf-8")
    logger.info(f"Weekly rollup generated: {weekly_file}")
    
    return weekly_file


def _build_weekly_content(
    year: int,
    week_num: int,
    week_start: date,
    week_end: date,
    notes: list[dict],
    task_stats: dict,
    daily_stats: list[dict],
) -> str:
    """Build the weekly summary markdown content."""
    lines = [
        "---",
        "type: weekly-summary",
        f"year: {year}",
        f"week: {week_num}",
        f"week_start: {week_start.isoformat()}",
        f"week_end: {week_end.isoformat()}",
        f"generated: {datetime.now().isoformat()}",
        f"note_count: {len(notes)}",
        f"task_count: {task_stats['total']}",
        "---",
        "",
        f"# Week {week_num}, {year}",
        f"*{week_start.strftime('%b %d')} - {week_end.strftime('%b %d, %Y')}*",
        "",
        "## 📊 Weekly Stats",
        "",
        f"- **Voice Notes**: {len(notes)}",
        f"- **Total Duration**: {sum(n['duration_min'] for n in notes)} min",
        f"- **Tasks Created**: {task_stats['total']}",
        f"- **Tasks Completed**: {task_stats['completed']}",
        f"- **Completion Rate**: {_calc_percentage(task_stats['completed'], task_stats['total'])}%",
        "",
    ]
    
    # Daily breakdown
    if daily_stats:
        lines.extend([
            "## 📅 Daily Breakdown",
            "",
            "| Day | Notes | Tasks |",
            "|-----|-------|-------|",
        ])
        
        for day_stat in daily_stats:
            day_name = day_stat["date"].strftime("%a %d")
            day_link = f"[[Daily/{day_stat['date'].isoformat()}|{day_name}]]"
            lines.append(f"| {day_link} | {day_stat['notes']} | {day_stat['tasks']} |")
        
        lines.append("")
    
    # Group notes by mode
    notes_by_mode = {}
    for note in notes:
        mode = note["mode"]
        if mode not in notes_by_mode:
            notes_by_mode[mode] = []
        notes_by_mode[mode].append(note)
    
    if notes_by_mode:
        lines.extend([
            "## 📝 Voice Notes by Category",
            "",
        ])
        
        for mode, mode_notes in notes_by_mode.items():
            lines.append(f"### {mode.replace('_', ' ').title()} ({len(mode_notes)})")
            lines.append("")
            for note in mode_notes:
                lines.append(f"- [[Inbox/{note['name']}|{note['title']}]]")
            lines.append("")
    
    # Open tasks
    if task_stats["pending"] > 0:
        lines.extend([
            "## ⏳ Open Tasks",
            "",
            f"**{task_stats['pending']} tasks** still pending from this week.",
            "",
            "```dataview",
            "TASK",
            f"FROM \"Tasks\"",
            f"WHERE !completed AND file.day >= date({week_start.isoformat()}) AND file.day <= date({week_end.isoformat()})",
            "```",
            "",
        ])
    
    lines.extend([
        "---",
        "",
        "*Generated automatically by Voice-to-Notes Engine*",
    ])
    
    return "\n".join(lines)


def _calc_percentage(part: int, total: int) -> int:
    """Calculate percentage, handling division by zero."""
    if total == 0:
        return 0
    return int((part / total) * 100)


# =============================================================================
# ROLLUP SCHEDULER / TRIGGERS
# =============================================================================

def should_generate_daily_rollup(daily_dir: Path, for_date: Optional[date] = None) -> bool:
    """Check if daily rollup should be generated (doesn't exist yet)."""
    target_date = for_date or date.today()
    daily_file = daily_dir / f"{target_date.isoformat()}.md"
    return not daily_file.exists()


def should_generate_weekly_rollup(weekly_dir: Path, for_date: Optional[date] = None) -> bool:
    """Check if weekly rollup should be generated.
    
    Returns True if:
    - It's Sunday (end of week) AND rollup doesn't exist
    - Or rollup doesn't exist and we're past the week
    """
    target_date = for_date or date.today()
    year, week_num, weekday = target_date.isocalendar()
    weekly_file = weekly_dir / f"{year}-W{week_num:02d}.md"
    
    if weekly_file.exists():
        return False
    
    # Generate on Sunday (weekday 7) or if checking a past week
    return weekday == 7
