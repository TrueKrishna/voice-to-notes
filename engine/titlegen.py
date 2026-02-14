"""
Title generation and slug creation for Obsidian-compatible filenames.

Parses AI-generated TITLE: lines and creates filesystem-safe slugs.
"""

import re
import unicodedata
from typing import Tuple


def parse_title_and_content(ai_output: str) -> Tuple[str, str]:
    """Parse the TITLE: line from AI output.

    The AI is instructed to output its first line as:
        TITLE: <concise descriptive title>

    Returns:
        Tuple of (title, remaining_content).
        If no TITLE: line is found, returns ("", full_output).
    """
    lines = ai_output.strip().split("\n")

    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.upper().startswith("TITLE:"):
            title = stripped[6:].strip()
            # Remove wrapping quotes if present
            title = title.strip('"').strip("'")
            # Remove markdown bold if present
            title = title.strip("*")
            # Get remaining content (skip blank lines after title)
            remaining_lines = lines[i + 1 :]
            # Skip leading blank lines
            while remaining_lines and not remaining_lines[0].strip():
                remaining_lines = remaining_lines[1:]
            remaining = "\n".join(remaining_lines).strip()
            return title, remaining

    # No TITLE: found
    return "", ai_output.strip()


def fallback_title(transcript: str, max_words: int = 6) -> str:
    """Generate a fallback title from the first meaningful words of a transcript.

    Used when the AI doesn't produce a TITLE: line.
    """
    # Remove timestamps like [00:00], [12:34]
    clean = re.sub(r"\[[\d:]+\]", "", transcript)
    # Remove speaker labels like **Speaker 1:**
    clean = re.sub(r"\*\*Speaker \d+:\*\*", "", clean)
    clean = clean.strip()

    words = clean.split()[:max_words]
    if not words:
        return "Untitled Voice Note"

    title = " ".join(words)
    if len(clean.split()) > max_words:
        title += "..."
    return title


def slugify(text: str, max_length: int = 60) -> str:
    """Convert text to a filesystem-safe slug.

    Examples:
        "Building Voice Infrastructure" → "building-voice-infrastructure"
        "Meeting: Q1 Planning (v2)"     → "meeting-q1-planning-v2"
    """
    # Normalize unicode characters
    text = unicodedata.normalize("NFKD", text)
    # Convert to ASCII, dropping non-ASCII chars
    text = text.encode("ascii", "ignore").decode("ascii")
    # Lowercase
    text = text.lower()
    # Replace any non-alphanumeric character with hyphens
    text = re.sub(r"[^a-z0-9]+", "-", text)
    # Remove leading/trailing hyphens
    text = text.strip("-")
    # Truncate at word boundary
    if len(text) > max_length:
        text = text[:max_length].rsplit("-", 1)[0]

    return text or "untitled"
