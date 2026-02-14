#!/usr/bin/env python3
"""Quick verification that all engine modules import correctly."""

from engine.models import ProcessingMode, ProcessingResult, AudioMetadata
print("models OK")

from engine.config import EngineConfig
print("config OK")

from engine.prompts import get_transcription_prompt, get_structuring_prompt
for mode in ProcessingMode:
    p = get_structuring_prompt(mode)
    assert "{transcript}" in p, f"Missing placeholder in {mode}"
print(f"prompts OK — {len(list(ProcessingMode))} modes")

from engine.audio import check_ffmpeg
print(f"audio OK — FFmpeg: {check_ffmpeg()}")

from engine.ai import GeminiClient
print("ai OK")

from engine.titlegen import parse_title_and_content, slugify, fallback_title
title, content = parse_title_and_content("TITLE: Test Title\n\n## Summary\nHello")
assert title == "Test Title", f"Got: {title}"
assert "## Summary" in content
assert slugify("Building Voice Infrastructure!") == "building-voice-infrastructure"
assert fallback_title("") == "Untitled Voice Note"
print("titlegen OK")

from engine.markdown import build_note, get_note_path
print("markdown OK")

from engine.registry import ProcessingRegistry
print("registry OK")

from engine.watcher import FolderWatcher
print("watcher OK")

from engine.core import process_audio
print("core OK")

from engine import process_audio, ProcessingMode, ProcessingResult
print("engine package OK")

print()
print("All imports verified. Engine ready.")
