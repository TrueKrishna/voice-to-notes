#!/usr/bin/env python3
"""
Voice-to-Notes Engine — Watcher Daemon

Monitors a local Google Drive sync folder for new audio files,
processes them through the AI pipeline, and saves structured
markdown notes to an Obsidian vault.

Architecture:
    ASR Voice Recorder (Android)
        ↓
    Google Drive (Audio Folder)
        ↓
    Local Google Drive Sync (Mac)
        ↓
    This Watcher (you are here)
        ↓
    Processing Engine
        ↓
    Obsidian Vault (also in Google Drive)

Usage:
    python run_watcher.py

Configuration:
    Set environment variables in .env file.
    See .env.example for all options.
"""

import os
import signal
import sys
import logging

from engine.config import load_config_from_db
from engine.watcher import FolderWatcher
from engine.registry import ProcessingRegistry


def main():
    # ── Logging ─────────────────────────────────────────────────────
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logger = logging.getLogger("engine")

    # ── Resolve DB path (shared with V1 web app) ───────────────────
    db_url = os.environ.get("DATABASE_URL", "sqlite:///./data/voice_notes.db")
    if db_url.startswith("sqlite:///"):
        db_path = db_url.replace("sqlite:///", "", 1)
    else:
        db_path = "./data/voice_notes.db"

    # ── Configuration (env vars + DB settings overlay) ─────────────
    logger.info("Loading configuration (env + DB settings)...")
    config = load_config_from_db(db_path)

    logger.info(f"Audio input:  {config.audio_input_dir}")
    logger.info(f"Obsidian out: {config.notes_output_dir}")
    logger.info(f"API keys:     {len(config.gemini_api_keys)} configured")
    logger.info(f"Model:        {config.gemini_model}")
    logger.info(f"Default mode: {config.default_mode}")

    # ── Validate ────────────────────────────────────────────────────
    if not config.audio_input_dir.exists():
        logger.warning(f"Input directory does not exist yet: {config.audio_input_dir}")
        logger.warning("Configure it via the Settings page or wait for Google Drive to sync.")

    # ── Registry ────────────────────────────────────────────────────
    registry = ProcessingRegistry(config.registry_db_path)
    stats = registry.get_stats()
    logger.info(
        f"Registry: {stats['total']} processed "
        f"({stats['success']} ok, {stats['failed']} failed)"
    )

    # ── Watcher ─────────────────────────────────────────────────────
    watcher = FolderWatcher(config, registry)
    watcher._db_path = db_path  # enable hot-reload from DB settings

    # Graceful shutdown on Ctrl+C or kill
    def shutdown(sig, frame):
        logger.info("Received shutdown signal, stopping gracefully...")
        watcher.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    # ── Start ───────────────────────────────────────────────────────
    logger.info("")
    logger.info("╔══════════════════════════════════════════════════════════╗")
    logger.info("║  Voice-to-Notes Engine v{:<30s} ║".format(config.engine_version))
    logger.info("║  Watching for audio files...                            ║")
    logger.info("║  Press Ctrl+C to stop                                   ║")
    logger.info("╚══════════════════════════════════════════════════════════╝")
    logger.info("")

    watcher.run()


if __name__ == "__main__":
    main()
