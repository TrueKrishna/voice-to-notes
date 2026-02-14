"""
Audio compression and metadata extraction using FFmpeg/ffprobe.
No database or web framework dependency — pure utility module.
"""

import json
import logging
import subprocess
import tempfile
from pathlib import Path
from typing import Optional, Tuple

from .models import AudioMetadata

logger = logging.getLogger(__name__)


def check_ffmpeg() -> bool:
    """Check if FFmpeg is installed and accessible."""
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def get_audio_metadata(file_path: Path) -> AudioMetadata:
    """Extract comprehensive audio metadata using ffprobe.

    Returns an AudioMetadata dataclass. Fields that can't be extracted
    are left as None.
    """
    metadata = AudioMetadata()

    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "quiet",
                "-print_format", "json",
                "-show_format", "-show_streams",
                str(file_path),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        data = json.loads(result.stdout)

        # Format-level info
        if "format" in data:
            fmt = data["format"]
            if fmt.get("duration"):
                metadata.duration = float(fmt["duration"])
            if fmt.get("bit_rate"):
                metadata.bit_rate = int(float(fmt["bit_rate"]) / 1000)

            # Try to extract recording timestamp from tags
            tags = fmt.get("tags", {})
            for key in ("creation_time", "date", "IDIT", "DateTimeOriginal"):
                if key in tags:
                    try:
                        from dateutil import parser as dateutil_parser
                        metadata.recorded_at = dateutil_parser.parse(tags[key])
                        break
                    except Exception:
                        pass

        # Audio stream info
        if "streams" in data:
            for stream in data["streams"]:
                if stream.get("codec_type") == "audio":
                    if stream.get("sample_rate"):
                        metadata.sample_rate = int(stream["sample_rate"])
                    metadata.channels = stream.get("channels")
                    metadata.codec = stream.get("codec_name")
                    break

    except Exception as e:
        logger.warning(f"Could not extract full audio metadata: {e}")
        # Fallback: try to get at least the duration
        metadata.duration = _get_duration_fallback(file_path)

    return metadata


def _get_duration_fallback(file_path: Path) -> Optional[float]:
    """Get just the audio duration as a fallback."""
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "quiet",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(file_path),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        return float(result.stdout.strip())
    except Exception:
        return None


def compress_audio(
    file_path: Path,
    bitrate: str = "48k",
) -> Tuple[Path, float, float]:
    """Compress audio to Opus format optimized for speech.

    Args:
        file_path: Path to the input audio file.
        bitrate: Target bitrate (default "48k" — excellent for speech).

    Returns:
        Tuple of (output_path, original_size_mb, compressed_size_mb).
        If compression fails, returns the original file path with identical sizes.
    """
    original_size = file_path.stat().st_size / (1024 * 1024)

    temp_file = tempfile.NamedTemporaryFile(suffix=".opus", delete=False)
    output_path = Path(temp_file.name)
    temp_file.close()

    try:
        subprocess.run(
            [
                "ffmpeg", "-y", "-i", str(file_path),
                "-vn",             # No video
                "-c:a", "libopus", # Opus codec
                "-b:a", bitrate,   # Target bitrate
                "-ar", "16000",    # 16kHz — sufficient for speech
                "-ac", "1",        # Mono
                str(output_path),
            ],
            capture_output=True,
            check=True,
        )

        compressed_size = output_path.stat().st_size / (1024 * 1024)
        reduction = (1 - compressed_size / original_size) * 100 if original_size > 0 else 0
        logger.info(
            f"Compressed: {original_size:.2f} MB → {compressed_size:.2f} MB "
            f"({reduction:.0f}% reduction)"
        )
        return output_path, original_size, compressed_size

    except subprocess.CalledProcessError as e:
        logger.warning(f"Compression failed, using original: {e}")
        output_path.unlink(missing_ok=True)
        return file_path, original_size, original_size
