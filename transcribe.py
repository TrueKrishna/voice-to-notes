#!/usr/bin/env python3
"""
Voice Memo to Notes Converter
Converts audio recordings to optimized format, transcribes using Gemini,
and generates structured markdown notes.
"""

import os
import sys
import subprocess
import argparse
import tempfile
from pathlib import Path
from datetime import datetime

import google.generativeai as genai


# ============================================================================
# CONFIGURATION
# ============================================================================

GEMINI_MODEL = "gemini-2.0-flash"  # Fast and excellent for transcription
AUDIO_BITRATE = "48k"  # Good quality at small size for speech
OUTPUT_FORMAT = "opus"  # Excellent compression for voice

TRANSCRIPTION_PROMPT = """You are a transcription assistant. Transcribe the following audio exactly as spoken.

Instructions:
- Transcribe verbatim, capturing every word
- Preserve the natural flow including filler words (um, uh, like, you know)
- For Hindi/Hinglish parts, transliterate to Roman script (not Devanagari)
- Use proper punctuation and paragraph breaks for readability
- If multiple speakers are clearly distinguishable, label them (Speaker 1, Speaker 2, etc.)
- Preserve any emphasized words or phrases

Output the transcription directly without any preamble or commentary."""

BREAKDOWN_PROMPT = """You are an expert note-taker. Analyze the following transcript and create a comprehensive, well-structured breakdown.

Create a detailed markdown document with:

## 📋 Summary
A 2-3 sentence executive summary of the entire recording.

## 🎯 Key Topics
For each major topic/section discussed:

### Topic Name
- **Context**: Brief context of this section
- **Key Points**: Bullet points of main ideas
- **Details**: Important details, examples, or explanations mentioned
- **Quotes**: Any notable quotes or statements (if relevant)

## ✅ Action Items
- List any tasks, to-dos, or follow-ups mentioned
- Include who is responsible (if mentioned)
- Include deadlines (if mentioned)

## 💡 Key Insights
- Important insights, decisions, or conclusions
- Any "aha moments" or notable realizations

## 📝 Additional Notes
- Any other relevant information
- References, names, or resources mentioned

---

Guidelines:
- Be thorough but concise
- Use clear, scannable formatting
- Preserve important details and nuances
- For Hindi/Hinglish content, keep it in Roman transliteration
- Group related ideas logically
- Use emoji sparingly for visual organization

Here is the transcript to analyze:

---
{transcript}
---

Create the structured breakdown:"""


# ============================================================================
# AUDIO PROCESSING
# ============================================================================

def check_ffmpeg():
    """Check if FFmpeg is installed."""
    try:
        subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True,
            check=True
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def get_audio_info(input_path: Path) -> dict:
    """Get audio file information using ffprobe."""
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "quiet",
                "-print_format", "json",
                "-show_format", "-show_streams",
                str(input_path)
            ],
            capture_output=True,
            text=True,
            check=True
        )
        import json
        return json.loads(result.stdout)
    except Exception as e:
        print(f"⚠️  Could not get audio info: {e}")
        return {}


def compress_audio(input_path: Path, output_path: Path) -> bool:
    """Compress audio to opus format for optimal size/quality."""
    print(f"🔄 Compressing audio...")
    
    original_size = input_path.stat().st_size / (1024 * 1024)  # MB
    
    try:
        subprocess.run(
            [
                "ffmpeg", "-y", "-i", str(input_path),
                "-vn",  # No video
                "-c:a", "libopus",
                "-b:a", AUDIO_BITRATE,
                "-ar", "16000",  # 16kHz is enough for speech
                "-ac", "1",  # Mono
                str(output_path)
            ],
            capture_output=True,
            check=True
        )
        
        compressed_size = output_path.stat().st_size / (1024 * 1024)  # MB
        ratio = original_size / compressed_size if compressed_size > 0 else 0
        
        print(f"   Original: {original_size:.2f} MB")
        print(f"   Compressed: {compressed_size:.2f} MB")
        print(f"   Compression ratio: {ratio:.1f}x")
        
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Compression failed: {e.stderr.decode()}")
        return False


# ============================================================================
# GEMINI TRANSCRIPTION & ANALYSIS
# ============================================================================

def setup_gemini(api_key: str):
    """Configure Gemini API."""
    genai.configure(api_key=api_key)
    return genai.GenerativeModel(GEMINI_MODEL)


def transcribe_audio(model, audio_path: Path) -> str:
    """Transcribe audio using Gemini."""
    print(f"🎙️  Transcribing with Gemini ({GEMINI_MODEL})...")
    
    # Upload the audio file
    audio_file = genai.upload_file(str(audio_path))
    
    # Generate transcription
    response = model.generate_content(
        [TRANSCRIPTION_PROMPT, audio_file],
        generation_config=genai.GenerationConfig(
            temperature=0.1,  # Low temperature for accuracy
            max_output_tokens=8192,
        )
    )
    
    # Clean up uploaded file
    try:
        audio_file.delete()
    except:
        pass
    
    return response.text


def generate_breakdown(model, transcript: str) -> str:
    """Generate structured breakdown using Gemini."""
    print(f"📝 Generating structured breakdown...")
    
    prompt = BREAKDOWN_PROMPT.format(transcript=transcript)
    
    response = model.generate_content(
        prompt,
        generation_config=genai.GenerationConfig(
            temperature=0.3,  # Slightly creative for better organization
            max_output_tokens=8192,
        )
    )
    
    return response.text


# ============================================================================
# FILE OUTPUT
# ============================================================================

def save_markdown(content: str, output_path: Path, title: str):
    """Save content to markdown file with metadata."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    header = f"""---
title: {title}
created: {timestamp}
generator: voice-to-notes
---

"""
    
    output_path.write_text(header + content, encoding="utf-8")
    print(f"   ✅ Saved: {output_path}")


# ============================================================================
# MAIN WORKFLOW
# ============================================================================

def process_audio(
    input_path: Path,
    output_dir: Path,
    api_key: str,
    skip_compression: bool = False
):
    """Main processing workflow."""
    
    # Validate input
    if not input_path.exists():
        print(f"❌ File not found: {input_path}")
        return False
    
    # Setup output directory
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Base name for output files
    base_name = input_path.stem
    
    print(f"\n{'='*60}")
    print(f"🎵 Processing: {input_path.name}")
    print(f"{'='*60}\n")
    
    # Step 1: Compress audio (optional)
    if skip_compression:
        audio_to_transcribe = input_path
        print("⏭️  Skipping compression (using original file)")
    else:
        if not check_ffmpeg():
            print("⚠️  FFmpeg not found. Install with: brew install ffmpeg")
            print("   Proceeding with original file...")
            audio_to_transcribe = input_path
        else:
            with tempfile.NamedTemporaryFile(suffix=".opus", delete=False) as tmp:
                compressed_path = Path(tmp.name)
            
            if compress_audio(input_path, compressed_path):
                audio_to_transcribe = compressed_path
            else:
                audio_to_transcribe = input_path
                print("   Using original file instead...")
    
    # Step 2: Setup Gemini
    try:
        model = setup_gemini(api_key)
    except Exception as e:
        print(f"❌ Failed to setup Gemini: {e}")
        return False
    
    # Step 3: Transcribe
    try:
        transcript = transcribe_audio(model, audio_to_transcribe)
        print(f"   ✅ Transcription complete ({len(transcript)} characters)")
    except Exception as e:
        print(f"❌ Transcription failed: {e}")
        return False
    
    # Step 4: Generate breakdown
    try:
        breakdown = generate_breakdown(model, transcript)
        print(f"   ✅ Breakdown complete")
    except Exception as e:
        print(f"❌ Breakdown generation failed: {e}")
        breakdown = None
    
    # Step 5: Save outputs
    print(f"\n📁 Saving output files...")
    
    # Raw transcript
    transcript_path = output_dir / f"{base_name}_transcript.md"
    save_markdown(
        f"# Transcript: {base_name}\n\n{transcript}",
        transcript_path,
        f"Transcript - {base_name}"
    )
    
    # Breakdown
    if breakdown:
        breakdown_path = output_dir / f"{base_name}_breakdown.md"
        save_markdown(
            breakdown,
            breakdown_path,
            f"Breakdown - {base_name}"
        )
    
    # Cleanup temp files
    if not skip_compression and audio_to_transcribe != input_path:
        try:
            audio_to_transcribe.unlink()
        except:
            pass
    
    print(f"\n{'='*60}")
    print(f"✅ Processing complete!")
    print(f"{'='*60}\n")
    
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Convert voice memos to structured markdown notes",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s recording.m4a
  %(prog)s recording.mp3 -o ./notes
  %(prog)s meeting.m4a --no-compress
  
Environment:
  Set GEMINI_API_KEY environment variable or use --api-key flag
        """
    )
    
    parser.add_argument(
        "input",
        type=Path,
        help="Input audio file (.m4a, .mp3, .wav, etc.)"
    )
    
    parser.add_argument(
        "-o", "--output",
        type=Path,
        default=None,
        help="Output directory (default: same as input file)"
    )
    
    parser.add_argument(
        "--api-key",
        type=str,
        default=None,
        help="Gemini API key (or set GEMINI_API_KEY env var)"
    )
    
    parser.add_argument(
        "--no-compress",
        action="store_true",
        help="Skip audio compression step"
    )
    
    args = parser.parse_args()
    
    # Get API key
    api_key = args.api_key or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("❌ Error: Gemini API key required")
        print("   Set GEMINI_API_KEY environment variable or use --api-key flag")
        print("   Get your key from: https://aistudio.google.com/apikey")
        sys.exit(1)
    
    # Set output directory
    output_dir = args.output or args.input.parent
    
    # Process
    success = process_audio(
        input_path=args.input,
        output_dir=output_dir,
        api_key=api_key,
        skip_compression=args.no_compress
    )
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
