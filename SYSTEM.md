# Voice-to-Notes System Documentation

> Last Updated: 14 February 2026  
> Engine Version: 2.1.0

## Overview

Voice-to-Notes is a self-hosted audio transcription and note processing system. It watches a Google Drive folder for audio files (voice memos), transcribes them using Google's Gemini AI, structures the content, and outputs Obsidian-compatible markdown notes.

### Core Capabilities

- **Audio Transcription** — Converts voice memos to text using Gemini AI
- **Content Structuring** — AI-powered extraction of key points, action items, and summaries
- **Obsidian Integration** — Native markdown with YAML frontmatter and wikilinks
- **Dual Output System** — Separates raw transcripts from structured notes
- **Task Extraction** — Automatically identifies and aggregates actionable items
- **Tag-Based Routing** — Copy notes to project folders based on tags
- **Daily/Weekly Rollups** — Automated summary generation

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Docker Compose Stack                         │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│   ┌─────────────┐    ┌─────────────┐    ┌─────────────────────┐   │
│   │    Web UI   │    │   Watcher   │    │     Rclone Sync     │   │
│   │  (FastAPI)  │    │  (V2 Engine)│    │   (Google Drive)    │   │
│   │   Port 8000 │    │  Auto-proc  │    │   5-min interval    │   │
│   └──────┬──────┘    └──────┬──────┘    └──────────┬──────────┘   │
│          │                  │                       │              │
│          │                  │                       │              │
│          ▼                  ▼                       ▼              │
│   ┌─────────────────────────────────────────────────────────────┐  │
│   │                    Shared Volume: /data/gdrive               │  │
│   │                                                              │  │
│   │   📁 VoiceMemos/           ← Input: Audio files from phone  │  │
│   │   📁 Obsidian/Workspace/   ← Output: Obsidian vault         │  │
│   │       └─ VoiceNotes/                                        │  │
│   │           ├─ Inbox/        ← Structured notes (source)      │  │
│   │           ├─ Transcripts/  ← Raw transcripts                │  │
│   │           ├─ Tasks/        ← Daily task aggregations        │  │
│   │           ├─ Daily/        ← Daily summaries                │  │
│   │           ├─ Weekly/       ← Weekly rollups                 │  │
│   │           └─ Projects/     ← Tag-routed copies              │  │
│   └─────────────────────────────────────────────────────────────┘  │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Components

### 1. V2 Processing Engine (`/engine/`)

The standalone processing pipeline. No web framework dependencies.

| File | Purpose |
|------|---------|
| `__init__.py` | Package exports, version 2.1.0 |
| `core.py` | Main `process_audio()` orchestrator — 6-step pipeline |
| `models.py` | Data classes: `ProcessingResult`, `AudioMetadata`, `ExtractedTask`, `NoteStatus` |
| `config.py` | Environment-driven configuration with DB override support |
| `ai.py` | `GeminiClient` for transcription and structuring |
| `audio.py` | FFmpeg-based compression and metadata extraction |
| `prompts.py` | AI prompt templates for all processing modes |
| `markdown.py` | Obsidian markdown generation with dual output |
| `titlegen.py` | AI-powered title generation |
| `registry.py` | SQLite tracking of processed files |
| `watcher.py` | Folder watcher daemon for auto-processing |
| `tasks.py` | Task extraction and daily aggregation |
| `rollups.py` | Daily/weekly summary generation |
| `routing.py` | Tag-based routing and project folder copying |

#### Processing Pipeline (6 Steps)

```
1. Metadata Extraction  → Get duration, format, bitrate from audio
2. Audio Compression    → FFmpeg compress to 48k for API efficiency
3. AI Transcription     → Gemini transcribes audio to text
4. Content Structuring  → Gemini extracts summary, key points, actions
5. Task Extraction      → Parse TASK: markers, aggregate to daily file
6. Dual Output Save     → Write to both Transcripts/ and Inbox/
```

### 2. Web UI (`/app/`)

FastAPI-based web interface for manual control and configuration.

| File | Purpose |
|------|---------|
| `main.py` | FastAPI app with routes for upload, playback, settings |
| `processor.py` | Wrapper connecting web UI to V2 engine |
| `database.py` | SQLite models: Recording, Settings, ApiUsage |
| `api_keys.py` | API key management with round-robin rotation |
| `templates/` | Jinja2 HTML templates |

#### Current Routes

| Route | Method | Description |
|-------|--------|-------------|
| `/` | GET | Dashboard with recent recordings |
| `/upload` | POST | Manual file upload (uses V2 engine) |
| `/recording/{id}` | GET | View processed recording |
| `/keys` | GET | API key management page |
| `/storage` | GET | Storage statistics |
| `/activity` | GET | API usage activity log |
| `/settings` | GET/POST | System settings |

### 3. Shared Module (`/shared/`)

Cross-component utilities shared between web and engine.

| File | Purpose |
|------|---------|
| `api_keys.py` | Centralized API key loading and model configuration |

### 4. Docker Services

| Service | Purpose | Port |
|---------|---------|------|
| `web` | FastAPI web interface | 8000 |
| `watcher` | Auto-processing daemon | — |
| `rclone` | Google Drive sync (5-min) | — |

---

## Configuration

### Environment Variables (`.env`)

```bash
# Required
GEMINI_API_KEYS=key1,key2,key3           # Comma-separated API keys

# Google Drive Paths (inside container)
AUDIO_INPUT_DIR=/data/gdrive/VoiceMemos
OBSIDIAN_VAULT_DIR=/data/gdrive/Obsidian/Workspace

# Optional Overrides
OBSIDIAN_NOTE_SUBDIR=VoiceNotes          # Base folder for all output
GEMINI_MODEL=gemini-2.0-flash            # Default AI model

# Watcher Tuning
STABILITY_SECONDS=10                      # Wait before processing
SCAN_INTERVAL_SECONDS=5                   # Polling frequency
```

### Folder Structure Configuration

All subdirectories are configurable via `EngineConfig`:

```python
inbox_subdir: str = "Inbox"              # Structured notes
transcripts_subdir: str = "Transcripts"  # Raw transcripts
tasks_subdir: str = "Tasks"              # Daily task files
daily_subdir: str = "Daily"              # Daily summaries
weekly_subdir: str = "Weekly"            # Weekly rollups
projects_subdir: str = "Projects"        # Tag-routed copies
```

---

## Output Format

### File Naming Convention

```
DD_MM_YY_slug-title.md

Example: 14_02_26_brief-inquiry-regarding-clusters.md
```

### Inbox Note (Structured)

```markdown
---
type: voice-note
title: "Brief Inquiry Regarding Clusters"
date: 2026-02-14
source_file: "20260214_120000.m4a"
duration: "1m 23s"
mode: personal_note
status: inbox
has_tasks: false
transcript: "[[Transcripts/14_02_26_brief-inquiry-regarding-clusters]]"
tags: []
---

## Summary
AI-generated summary of the voice memo content.

## Key Points
- Main point extracted from audio
- Another important point

## Action Items
- [ ] Task identified from the recording

## Details
Extended content and context from the memo.
```

### Transcript Note (Raw)

```markdown
---
type: transcript
title: "Brief Inquiry Regarding Clusters"
date: 2026-02-14
source_file: "20260214_120000.m4a"
duration: "1m 23s"
note: "[[Inbox/14_02_26_brief-inquiry-regarding-clusters]]"
---

## Transcript

Full verbatim transcription of the audio recording...
```

### Daily Tasks File

```markdown
---
type: task-rollup
date: 2026-02-14
---

## Tasks for 14 February 2026

### From: Brief Inquiry Regarding Clusters
- [ ] Task extracted from this note

### From: Another Voice Memo
- [ ] Another task
```

---

## Key Design Decisions

### 1. Inbox as Source of Truth
The Inbox folder is permanent and never modified after creation. It serves as the canonical record of all processed voice memos.

### 2. Copy, Don't Move
When routing notes to project folders, files are **copied**, not moved. The Inbox always retains the original.

### 3. Dual Output
Every audio file produces two markdown files:
- **Transcripts/** — Raw transcription for reference
- **Inbox/** — Structured note for daily use

Cross-linked via Obsidian wikilinks in frontmatter.

### 4. Environment-First Configuration
No hardcoded paths. All directories and settings come from environment variables, with optional database overrides for runtime changes.

### 5. API Key Rotation
Multiple Gemini API keys are supported with automatic round-robin rotation and usage tracking per key.

---

## Database Schema

### Web UI Database (`/data/web/recordings.db`)

**recordings** — Processed file records
- `id`, `filename`, `original_path`, `duration`, `transcription`, `structured_content`, `status`, `created_at`, `processed_at`

**settings** — Key-value configuration store
- `key`, `value`, `created_at`, `updated_at`

**api_usage** — Per-key usage tracking
- `id`, `api_key_masked`, `model_used`, `input_tokens`, `output_tokens`, `total_tokens`, `operation`, `success`, `error_message`, `created_at`

### Engine Registry (`/data/engine/registry.db`)

**processed_files** — Watcher state tracking
- `id`, `file_path`, `file_hash`, `status`, `note_path`, `transcript_path`, `has_tasks`, `error`, `created_at`, `processed_at`

---

## API Usage

### GeminiClient Operations

| Operation | Model | Prompt |
|-----------|-------|--------|
| `transcribe()` | gemini-2.0-flash | Audio → text transcription |
| `structure()` | gemini-2.0-flash | Text → structured note |
| `generate_title()` | gemini-2.0-flash | Generate slug-friendly title |
| `extract_tasks()` | gemini-2.0-flash | Extract TASK: markers |

---

## Running the System

### Start All Services

```bash
docker compose up -d
```

### View Logs

```bash
# All services
docker compose logs -f

# Watcher only
docker compose logs -f watcher
```

### Force Reprocess a File

```bash
# Delete from registry
docker exec voice-to-notes-watcher python -c "
from engine.registry import FileRegistry
r = FileRegistry()
r._execute('DELETE FROM processed_files WHERE file_path LIKE ?', ('%filename%',))
"

# Restart watcher
docker compose restart watcher
```

### Manual Upload

Visit `http://localhost:8000/` and use the upload form.

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 2.1.0 | 2026-02-14 | Dual output system, task extraction, rollups, routing |
| 2.0.0 | 2026-02-13 | V2 engine with standalone pipeline, watcher service |
| 1.0.0 | 2026-02-12 | Initial release with web UI and manual processing |

---

## Future Enhancements (Planned)

- **V2 Dashboard** — New frontend for Inbox management, tagging, and task views
- **Webhook Integration** — Notify external services on new notes
- **Multi-Vault Support** — Route to different Obsidian vaults
- **Voice Command Detection** — Inline commands like "remind me" or "add to project X"
