"""
Polling-based folder watcher with file stability checking.

Monitors a local Google Drive sync directory for new audio files.
When a file is stable (size unchanged for N seconds), it's moved to
a processing directory and run through the AI pipeline.

Does NOT use filesystem events (unreliable with cloud sync).
Uses simple polling + size stability for robustness.
"""

import shutil
import time
import logging
from pathlib import Path

from .config import EngineConfig, load_config_from_db
from .models import ProcessingMode
from .registry import ProcessingRegistry

logger = logging.getLogger(__name__)

# Map subfolder names to processing modes
FOLDER_MODE_MAP = {
    "meetings": ProcessingMode.MEETING,
    "meeting": ProcessingMode.MEETING,
    "ideas": ProcessingMode.IDEA,
    "idea": ProcessingMode.IDEA,
    "reflections": ProcessingMode.REFLECTION,
    "reflection": ProcessingMode.REFLECTION,
    "tasks": ProcessingMode.TASK_DUMP,
    "task_dump": ProcessingMode.TASK_DUMP,
    "task-dump": ProcessingMode.TASK_DUMP,
    "personal": ProcessingMode.PERSONAL_NOTE,
    "notes": ProcessingMode.PERSONAL_NOTE,
}


class FolderWatcher:
    """Watches a directory for new audio files and processes them.

    Workflow:
        1. Scan audio_input_dir recursively for supported audio files
        2. Wait until file size is stable (not being synced/written)
        3. Check idempotency registry (skip if already processed)
        4. Move file to processing_temp_dir (atomic, prevents re-processing)
        5. Run through the processing pipeline
        6. On success: record in registry, delete temp file
        7. On failure: move to failed_dir, record failure in registry
    """

    def __init__(self, config: EngineConfig, registry: ProcessingRegistry):
        self.config = config
        self.registry = registry
        self.running = False
        self._file_sizes: dict[Path, int] = {}
        self._file_stable_since: dict[Path, float] = {}
        self._db_path: str | None = None  # set externally for hot-reload

    def _reload_config(self):
        """Hot-reload config from DB settings (if DB path is known)."""
        if self._db_path:
            try:
                self.config = load_config_from_db(self._db_path)
            except Exception as e:
                logger.debug(f"Config reload skipped: {e}")

    def run(self):
        """Start the polling loop. Blocks until stop() is called."""
        self.running = True
        logger.info("=" * 60)
        logger.info(f"  Watching:   {self.config.audio_input_dir}")
        logger.info(f"  Output:     {self.config.notes_output_dir}")
        logger.info(f"  Scan every: {self.config.scan_interval_seconds}s")
        logger.info(f"  Stability:  {self.config.stability_seconds}s")
        logger.info(f"  Mode:       {self.config.default_mode}")
        logger.info("=" * 60)

        while self.running:
            try:
                self._scan()
            except Exception as e:
                logger.error(f"Scan error: {e}", exc_info=True)
                self.registry.update_watcher_status("error", current_step=str(e))
            time.sleep(self.config.scan_interval_seconds)

    def stop(self):
        """Signal the watcher to stop after the current scan."""
        self.running = False
        self.registry.update_watcher_status("stopped")
        logger.info("Watcher stop requested")

    def _scan(self):
        """Scan for new audio files and process stable ones."""
        self._reload_config()
        self.registry.update_watcher_status("scanning")

        if not self.config.audio_input_dir.exists():
            self.registry.update_watcher_status("idle", current_step="Input dir not found")
            return

        # Collect all processable files first
        files_to_process = []
        for file_path in self._find_audio_files():
            try:
                # Wait for file stability (not still being synced)
                if not self._is_stable(file_path):
                    continue

                # Compute content hash for idempotency
                file_hash = ProcessingRegistry.compute_hash(file_path)
                
                # Check if should skip (processed, skipped, or in backoff)
                should_skip, reason = self.registry.should_skip(file_hash)
                if should_skip:
                    if "already_processed" not in reason:
                        logger.debug(f"Skipping {file_path.name}: {reason}")
                    # Clean up tracking state
                    self._file_sizes.pop(file_path, None)
                    self._file_stable_since.pop(file_path, None)
                    continue

                files_to_process.append((file_path, file_hash))

            except Exception as e:
                logger.error(f"Error checking {file_path.name}: {e}", exc_info=True)

        # Update queue count
        queue_size = len(files_to_process)
        if queue_size > 0:
            self.registry.update_watcher_status("processing", files_in_queue=queue_size)
        
        # Process collected files
        for i, (file_path, file_hash) in enumerate(files_to_process):
            try:
                remaining = queue_size - i
                self.registry.update_watcher_status(
                    "processing",
                    current_file=file_path.name,
                    current_step="Starting",
                    files_in_queue=remaining,
                )
                self._process_file(file_path, file_hash)
            except Exception as e:
                logger.error(f"Error processing {file_path.name}: {e}", exc_info=True)

        # Done scanning
        self.registry.update_watcher_status("idle", files_in_queue=0)

    def _find_audio_files(self):
        """Recursively find audio files in the input directory."""
        for path in self.config.audio_input_dir.rglob("*"):
            if path.is_file() and path.suffix.lower() in self.config.supported_formats:
                yield path

    def _is_stable(self, path: Path) -> bool:
        """Check if file size has been unchanged for stability_seconds.

        This prevents processing files that are still being synced by
        Google Drive or written by the recorder app.
        """
        try:
            current_size = path.stat().st_size
        except OSError:
            return False

        # Ignore empty files
        if current_size == 0:
            return False

        # Check if size changed since last scan
        prev_size = self._file_sizes.get(path)
        if prev_size != current_size:
            self._file_sizes[path] = current_size
            self._file_stable_since[path] = time.time()
            return False

        # Size is stable — check how long
        elapsed = time.time() - self._file_stable_since.get(path, time.time())
        return elapsed >= self.config.stability_seconds

    def _detect_mode(self, file_path: Path) -> ProcessingMode:
        """Detect processing mode from the subfolder name.

        If the file is in a subfolder whose name matches a mode, use that mode.
        Otherwise use the default mode from config.

        Examples:
            VoiceInbox/meetings/standup.m4a  → MEETING
            VoiceInbox/ideas/new-app.m4a     → IDEA
            VoiceInbox/recording.m4a         → default_mode
        """
        try:
            relative = file_path.relative_to(self.config.audio_input_dir)
            # Check each parent directory (excluding the filename itself)
            for part in relative.parts[:-1]:
                mode = FOLDER_MODE_MAP.get(part.lower())
                if mode:
                    return mode
        except ValueError:
            pass

        return ProcessingMode(self.config.default_mode)

    def _process_file(self, source_path: Path, file_hash: str):
        """Copy file to processing directory and run the pipeline.

        Uses copy (not move) to avoid deleting files from Google Drive
        during processing. The original is only removed after success.
        """
        # Lazy import to avoid circular dependency
        from .core import process_audio
        from .tasks import append_tasks_to_daily_file

        mode = self._detect_mode(source_path)
        file_size = source_path.stat().st_size

        # Copy to processing directory (preserves original in Drive)
        dest = self.config.processing_temp_dir / source_path.name
        if dest.exists():
            stem = dest.stem
            suffix = dest.suffix
            counter = 1
            while dest.exists():
                dest = self.config.processing_temp_dir / f"{stem}_{counter}{suffix}"
                counter += 1

        logger.info(f"▶ Processing: {source_path.name} | Mode: {mode.value}")
        shutil.copy2(str(source_path), str(dest))

        try:
            # Progress callback to update watcher status
            def on_step(step_num: int, step_name: str):
                self.registry.update_watcher_status(
                    "processing",
                    current_file=source_path.name,
                    current_step=f"Step {step_num}/6 — {step_name}",
                )
            
            result = process_audio(dest, mode=mode.value, config=self.config, on_step=on_step)

            # Record success in registry
            self.registry.record_success(
                filename=source_path.name,
                file_hash=file_hash,
                file_size=file_size,
                mode=mode.value,
                title=result.title,
                note_path=str(result.inbox_path) if result.inbox_path else "",
                transcript_path=str(result.transcript_path) if result.transcript_path else "",
                duration=result.metadata.duration,
                has_tasks=result.has_tasks,
                audio_path=str(result.audio_path) if result.audio_path else "",
            )

            # Append extracted tasks to daily task file
            if result.has_tasks and result.tasks and result.inbox_path:
                try:
                    append_tasks_to_daily_file(
                        tasks=result.tasks,
                        source_note_path=result.inbox_path,
                        tasks_dir=self.config.tasks_dir,
                    )
                except Exception as e:
                    logger.warning(f"Failed to append tasks: {e}")

            # Cleanup: delete the temp processing copy
            dest.unlink(missing_ok=True)

            # Cleanup tracking state
            self._file_sizes.pop(source_path, None)
            self._file_stable_since.pop(source_path, None)

            logger.info(f"✅ Complete: {source_path.name}")
            if result.transcript_path:
                logger.info(f"   Transcript: {result.transcript_path}")
            if result.inbox_path:
                logger.info(f"   Note: {result.inbox_path}")
            if result.has_tasks:
                logger.info(f"   Tasks: {len(result.tasks)} added to daily file")

        except Exception as e:
            logger.error(f"❌ Failed: {source_path.name} — {e}")

            # Move to failed directory for manual inspection
            failed_dest = self.config.failed_dir / source_path.name
            if failed_dest.exists():
                failed_dest = self.config.failed_dir / f"{dest.stem}_failed{dest.suffix}"
            try:
                shutil.move(str(dest), str(failed_dest))
            except Exception:
                pass

            self.registry.record_failure(
                filename=source_path.name,
                file_hash=file_hash,
                file_size=file_size,
                error=str(e),
            )

            # Cleanup tracking state
            self._file_sizes.pop(source_path, None)
            self._file_stable_since.pop(source_path, None)
