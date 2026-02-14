"""
Core transcription and processing logic.
"""

import os
import subprocess
import tempfile
import time
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, Tuple

from google import genai
from google.genai import types
from sqlalchemy.orm import Session

from .database import Recording
from .api_keys import APIKeyManager


# ============================================================================
# LOGGING
# ============================================================================

logger = logging.getLogger(__name__)


# ============================================================================
# RATE LIMIT HANDLING
# ============================================================================

class RateLimitHandler:
    """Handles rate limit with status updates to database."""
    
    def __init__(self, db, recording, base_delay: float = 90.0):
        self.db = db
        self.recording = recording
        self.base_delay = base_delay
    
    def wait(self, attempt: int) -> float:
        """Wait for rate limit with exponential backoff, updating DB status."""
        # For free tier (10 RPM), we need ~90s between request bursts
        # Each recording = 2 requests (transcribe + breakdown)
        delay = self.base_delay * (1.5 ** attempt)
        max_delay = 300  # Cap at 5 minutes
        actual_delay = min(delay, max_delay)
        
        # Update status in database so UI shows what's happening
        self.recording.processing_message = f"Rate limited (Free tier: 10 RPM). Waiting {int(actual_delay)}s... (attempt {attempt + 1})"
        self.db.commit()
        
        print(f"⏳ Rate limited. Waiting {actual_delay:.0f}s before retry (attempt {attempt + 1})...")
        
        # Wait in chunks so we can update the countdown and check for abort
        remaining = actual_delay
        while remaining > 0:
            # Check if user aborted
            self.db.refresh(self.recording)
            if self.recording.status == "failed" and "Aborted" in (self.recording.error_message or ""):
                raise Exception("Processing aborted by user")
            
            time.sleep(min(5, remaining))
            remaining -= 5
            if remaining > 0:
                self.recording.processing_message = f"Rate limited. Waiting {int(remaining)}s... (You can abort)"
                self.db.commit()
        
        self.recording.processing_message = "Retrying..."
        self.db.commit()
        
        return actual_delay


# ============================================================================
# PROMPTS
# ============================================================================

TRANSCRIPTION_PROMPT = """You are a professional transcription assistant. Transcribe the following audio EXACTLY as spoken.

CRITICAL INSTRUCTIONS:
1. **Language**: Transcribe in the EXACT language spoken
   - If Hindi is spoken, write it in Roman/Latin script (Devanagari is NOT allowed)
   - If English is spoken, write it in English
   - If it's Hinglish (mix), write exactly what you hear in Roman script
   - DO NOT translate anything - this is a transcript, not a translation

2. **Speaker Identification**: 
   - Identify and label different speakers (Speaker 1, Speaker 2, etc.)

3. **CRITICAL - Avoid Repetition**:
   - If you encounter silence or unclear audio, write "[silence]" or "[inaudible]" instead of repeating previous text
   - DO NOT loop or repeat the same phrase multiple times
   - If audio quality degrades, indicate it with "[audio quality issues]" rather than guessing or repeating
   - Move forward through the audio - never repeat the same sentence more than once unless the speaker actually repeated it
   - Start a NEW PARAGRAPH for each speaker change
   - Format: **Speaker 1:** [their dialogue]

3. **Timestamps**:
   - Add timestamps every 1-2 minutes using format [MM:SS]
   - Place timestamps at natural break points (between sentences)

4. **Formatting** (CRITICAL - READ CAREFULLY):
   - ALWAYS use paragraph breaks - NEVER write continuous text
   - Add a blank line (double newline) after EVERY 2-3 sentences
   - When speaker continues talking, break into multiple paragraphs at logical points
   - After each timestamp, start a new paragraph
   - Each speaker turn = new paragraph with blank line before it
   - Use proper punctuation and capitalization
   - Preserve emphasis and tone where apparent
   - Keep filler words if they're frequent/meaningful, but clean up excessive repetition
   
   IMPORTANT: The output should look like separate paragraphs with visible spacing, NOT a continuous block of text.

5. **Content Quality**:
   - Transcribe verbatim - what they said, not what they meant to say
   - Maintain the speaker's exact words and phrasing
   - For technical terms, write them as heard

Example format (notice the blank lines between paragraphs):

[00:00] **Speaker 1:** Aaj hum platform architecture discuss karenge. Main focus scalability par hai.

Humne pichle quarter mein dekha ki traffic badh raha hai aur hume infrastructure upgrade karna padega. Yeh bahut important hai hamare future growth ke liye.

[00:45] **Speaker 2:** I agree completely. Database design se start karte hain aur concurrent users ko kaise handle karte hain.

Mere hisaab se PostgreSQL ya MongoDB dono options explore karne chahiye. Dono ke apne advantages hain.

Output the transcription directly without any preamble. Remember: PARAGRAPHS WITH BLANK LINES, not continuous text."""

BREAKDOWN_PROMPT = """You are an expert analyst and note-taker. Create a COMPREHENSIVE, DETAILED breakdown of the following transcript.

Your goal: Extract ALL meaningful information and organize it into a clear, scannable structure.

# STRUCTURE (Use this exact format):

## 📊 Executive Overview
- **Duration**: [Calculate from timestamps]
- **Participants**: [List all speakers]
- **Main Purpose**: [1-2 sentences describing the primary purpose of this recording]
- **Key Outcome**: [What was decided, concluded, or achieved]

---

## 🎯 Detailed Topic Breakdown

For EACH major topic discussed, create a separate section with:

### [Topic Name] [Timestamp Range: MM:SS - MM:SS]

**Context & Background:**
- Why this topic came up
- Any background information provided
- How it relates to previous discussions

**Key Points Discussed:**
1. [First main point with details]
   - Supporting details or examples
   - Any data/numbers mentioned
2. [Second main point]
   - Elaboration
   - Context or implications
3. [Continue for all points]

**Decisions & Conclusions:**
- What was decided or concluded
- Any consensus reached
- Open questions or disagreements

**Action Items:**
- [ ] [Specific task] - [Who] - [Deadline if mentioned]
- [ ] [Next task]

**Technical Details:** (if applicable)
- Specific technologies, tools, or methodologies mentioned
- Technical specifications or requirements
- Code, architecture, or design discussions

**Important Quotes:**
> "[Any notable or significant statements]"
> - Speaker [N]

---

## 💡 Key Insights & Observations

**Strategic Insights:**
- [High-level insights or strategic observations]
- [Patterns or trends identified]

**Concerns Raised:**
- [Any concerns, risks, or challenges mentioned]
- [Potential blockers or issues]

**Opportunities Identified:**
- [New opportunities or possibilities discussed]
- [Areas for improvement or growth]

---

## ✅ Action Items Summary

| Task | Owner | Priority | Deadline | Status |
|------|-------|----------|----------|--------|
| [Task] | [Name] | [High/Med/Low] | [Date] | Pending |

---

## 🔍 Additional Context

**People & Organizations Mentioned:**
- [Names of people mentioned]
- [Companies, clients, or organizations referenced]

**Resources & References:**
- [Documents, links, or resources mentioned]
- [Tools or platforms discussed]
- [Previous meetings or related discussions referenced]

**Numbers & Data Points:**
- [Any specific numbers, metrics, or statistics]
- [Budget figures, timelines, or quantities]

**Timeline & Deadlines:**
- [Chronological list of all dates and deadlines mentioned]

---

## 📝 Follow-up Required

- [ ] [What needs to be done next]
- [ ] [Information that needs to be gathered]
- [ ] [People who need to be contacted]
- [ ] [Decisions that need to be made]

---

# INSTRUCTIONS:

1. **Be EXTREMELY thorough** - include ALL details, not just highlights
2. **Organize by topics** - group related discussions together
3. **Use timestamps** - reference when each topic was discussed
4. **Extract everything** - action items, decisions, technical details, concerns, ideas
5. **Maintain context** - explain WHY things were discussed, not just WHAT
6. **Format clearly** - use markdown, bullet points, tables for easy scanning
7. **Quote important statements** - preserve exact wording for key decisions or insights
8. **Be objective** - report what was said, not your interpretation
9. **Include nuance** - capture disagreements, uncertainties, and multiple viewpoints
10. **Make it actionable** - clearly separate decisions from discussions

---

Here is the transcript to analyze:

---
{transcript}
---

Create the comprehensive breakdown:"""


# ============================================================================
# AUDIO PROCESSING
# ============================================================================

AUDIO_BITRATE = "48k"
SUPPORTED_FORMATS = {'.mp3', '.m4a', '.wav', '.ogg', '.flac', '.webm', '.aac', '.3gp', '.opus'}


def check_ffmpeg() -> bool:
    """Check if FFmpeg is installed."""
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def get_audio_duration(file_path: Path) -> Optional[float]:
    """Get audio duration in seconds using ffprobe."""
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "quiet",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(file_path)
            ],
            capture_output=True,
            text=True,
            check=True
        )
        return float(result.stdout.strip())
    except:
        return None


def get_audio_metadata(file_path: Path) -> dict:
    """Extract comprehensive audio metadata using ffprobe."""
    metadata = {
        'duration': None,
        'sample_rate': None,
        'bit_rate': None,
        'channels': None,
        'codec': None,
        'recorded_at': None
    }
    
    try:
        # Get format and stream info
        result = subprocess.run(
            [
                "ffprobe", "-v", "quiet",
                "-print_format", "json",
                "-show_format",
                "-show_streams",
                str(file_path)
            ],
            capture_output=True,
            text=True,
            check=True
        )
        
        import json
        data = json.loads(result.stdout)
        
        # Extract format info
        if 'format' in data:
            fmt = data['format']
            metadata['duration'] = float(fmt.get('duration', 0)) if fmt.get('duration') else None
            metadata['bit_rate'] = int(float(fmt.get('bit_rate', 0)) / 1000) if fmt.get('bit_rate') else None
            
            # Try to extract recording timestamp from tags
            tags = fmt.get('tags', {})
            for key in ['creation_time', 'date', 'IDIT', 'DateTimeOriginal']:
                if key in tags:
                    try:
                        from dateutil import parser
                        metadata['recorded_at'] = parser.parse(tags[key])
                        break
                    except:
                        pass
        
        # Extract audio stream info
        if 'streams' in data:
            for stream in data['streams']:
                if stream.get('codec_type') == 'audio':
                    metadata['sample_rate'] = int(stream.get('sample_rate', 0)) if stream.get('sample_rate') else None
                    metadata['channels'] = stream.get('channels')
                    metadata['codec'] = stream.get('codec_name')
                    break
        
        return metadata
        
    except Exception as e:
        print(f"⚠️  Could not extract full audio metadata: {e}")
        # Fallback to basic duration
        metadata['duration'] = get_audio_duration(file_path)
        return metadata


def compress_audio(input_path: Path) -> Tuple[Path, float, float]:
    """
    Compress audio to opus format for optimal size/quality.
    Returns (output_path, original_size_mb, compressed_size_mb)
    """
    original_size = input_path.stat().st_size / (1024 * 1024)
    
    # Create temp file for compressed audio
    temp_file = tempfile.NamedTemporaryFile(suffix=".opus", delete=False)
    output_path = Path(temp_file.name)
    temp_file.close()
    
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
        
        compressed_size = output_path.stat().st_size / (1024 * 1024)
        compression_ratio = (1 - compressed_size / original_size) * 100 if original_size > 0 else 0
        logger.info(f"✅ Compression complete | {original_size:.2f} MB → {compressed_size:.2f} MB ({compression_ratio:.1f}% reduction)")
        return output_path, original_size, compressed_size
        
    except subprocess.CalledProcessError as e:
        logger.warning(f"⚠️  Compression failed, using original file | Error: {e}")
        # If compression fails, return original
        output_path.unlink(missing_ok=True)
        return input_path, original_size, original_size


# ============================================================================
# TRANSCRIPTION
# ============================================================================

def transcribe_audio(
    client: genai.Client,
    model_name: str,
    audio_path: Path,
    api_key_manager: APIKeyManager = None,
    current_key = None
) -> str:
    """Transcribe audio using Gemini."""
    logger.info(f"🎙️  Transcribing audio | File: {audio_path.name} | Size: {audio_path.stat().st_size / (1024*1024):.2f} MB")
    
    # Upload the audio file
    logger.debug(f"📤 Uploading audio to Gemini...")
    audio_file = client.files.upload(file=str(audio_path))
    logger.debug(f"✅ Audio uploaded successfully | File ID: {audio_file.name if hasattr(audio_file, 'name') else 'unknown'}")
    
    try:
        # Generate transcription
        response = client.models.generate_content(
            model=model_name,
            contents=[TRANSCRIPTION_PROMPT, audio_file],
            config=types.GenerateContentConfig(
                temperature=1.0,  # Google STRONGLY recommends 1.0 - anything lower causes looping!
                top_p=0.95,  # Nucleus sampling for diversity
                top_k=40,  # Top-k sampling for variety
                max_output_tokens=65536,  # High limit for long recordings
                candidate_count=1,
            ),
        )
        
        # Validate response before accessing text
        if not response:
            raise Exception("Empty response from Gemini API")
        
        # Check if content was blocked
        if hasattr(response, 'prompt_feedback') and response.prompt_feedback:
            block_reason = getattr(response.prompt_feedback, 'block_reason', None)
            if block_reason and str(block_reason) not in ("BLOCK_REASON_UNSPECIFIED", "0", "None"):
                raise Exception(f"Content blocked by safety filters: {block_reason}")
        
        # Check if we have candidates
        if not hasattr(response, 'candidates') or not response.candidates:
            raise Exception("No response candidates from Gemini API")
        
        # Check finish reason
        candidate = response.candidates[0]
        finish_reason = getattr(candidate, 'finish_reason', None)
        finish_str = str(finish_reason) if finish_reason else ""
        if "MAX_TOKENS" in finish_str:
            logger.warning("⚠️  Transcription hit max token limit")
            text = response.text if hasattr(response, 'text') else ""
            if text and text.strip():
                logger.warning(f"⚠️  Warning: Transcription exceeded max tokens")
                return text + "\n\n---\n\n**[Note: Transcription was cut off due to length limit. For complete transcription of 2+ hour audio, please split into shorter segments or use a paid tier with higher limits.]**"
            raise Exception("Transcription exceeded maximum length. For 2+ hour audio, please split into shorter segments.")
        elif finish_reason and finish_str not in ("STOP", "FinishReason.STOP", "UNSPECIFIED", "FinishReason.UNSPECIFIED", "0", "1"):
            logger.error(f"❌ Generation stopped abnormally: finish_reason={finish_reason}")
            raise Exception(f"Generation stopped abnormally: finish_reason={finish_reason}")
        
        # Try to get text
        if not response.text or not response.text.strip():
            raise Exception("Empty transcription received from Gemini")
        
        if api_key_manager and current_key:
            api_key_manager.mark_key_used(current_key, success=True)
        
        return response.text
        
    except AttributeError as e:
        # Handle cases where response.text throws AttributeError
        raise Exception(f"Invalid response structure from Gemini: {e}")
    except Exception as e:
        # Re-raise with more context
        if "text" in str(e).lower() and "attribute" in str(e).lower():
            raise Exception("Gemini returned invalid response (no text attribute)")
        raise
    finally:
        # Clean up uploaded file
        try:
            client.files.delete(name=audio_file.name)
        except:
            pass


def generate_breakdown(
    client: genai.Client,
    model_name: str,
    transcript: str,
    api_key_manager: APIKeyManager = None,
    current_key = None
) -> str:
    """Generate structured breakdown using Gemini."""
    
    prompt = BREAKDOWN_PROMPT.format(transcript=transcript)
    
    try:
        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=1.0,  # Google strongly recommends keeping at 1.0
                top_p=0.95,  # Nucleus sampling
                top_k=40,  # Top-k sampling
                max_output_tokens=65536,  # High limit for detailed breakdowns
                candidate_count=1,
            ),
        )
        
        # Validate response before accessing text
        if not response:
            raise Exception("Empty response from Gemini API")
        
        # Check if content was blocked
        if hasattr(response, 'prompt_feedback') and response.prompt_feedback:
            block_reason = getattr(response.prompt_feedback, 'block_reason', None)
            if block_reason and str(block_reason) not in ("BLOCK_REASON_UNSPECIFIED", "0", "None"):
                raise Exception(f"Content blocked by safety filters: {block_reason}")
        
        # Check if we have candidates
        if not hasattr(response, 'candidates') or not response.candidates:
            raise Exception("No response candidates from Gemini API")
        
        # Check finish reason
        candidate = response.candidates[0]
        finish_reason = getattr(candidate, 'finish_reason', None)
        finish_str = str(finish_reason) if finish_reason else ""
        if "MAX_TOKENS" in finish_str:
            # Still return partial content with warning
            text = response.text if hasattr(response, 'text') else ""
            if text and text.strip():
                print(f"⚠️  Warning: Breakdown exceeded max tokens, returning partial content")
                return text + "\n\n[Note: Breakdown was cut off due to length.]"
            raise Exception("Breakdown exceeded maximum length (MAX_TOKENS) and no partial content available")
        elif finish_reason and finish_str not in ("STOP", "FinishReason.STOP", "UNSPECIFIED", "FinishReason.UNSPECIFIED", "0", "1"):
            raise Exception(f"Generation stopped abnormally: finish_reason={finish_reason}")
        
        # Try to get text
        if not response.text or not response.text.strip():
            raise Exception("Empty breakdown received from Gemini")
        
        if api_key_manager and current_key:
            api_key_manager.mark_key_used(current_key, success=True)
        
        return response.text
        
    except AttributeError as e:
        raise Exception(f"Invalid response structure from Gemini: {e}")
    except Exception as e:
        if "text" in str(e).lower() and "attribute" in str(e).lower():
            raise Exception("Gemini returned invalid response (no text attribute)")
        raise


# ============================================================================
# MAIN PROCESSOR
# ============================================================================

class AudioProcessor:
    """Main processor for audio files."""
    
    MAX_RETRIES = 5  # Increased for rate limit handling
    
    def __init__(self, db: Session):
        self.db = db
        self.key_manager = APIKeyManager(db)
    
    def process(self, file_path: Path, recording_id: int) -> Recording:
        """
        Process an audio file: compress, transcribe, and generate breakdown.
        Updates the Recording in the database with step-by-step status.
        Always saves compressed file for download even if transcription fails.
        """
        import shutil
        
        # Get recording from database
        recording = self.db.query(Recording).filter(Recording.id == recording_id).first()
        if not recording:
            raise Exception(f"Recording {recording_id} not found")
        
        recording.status = "processing"
        recording.processing_step = "starting"
        self.db.commit()
        
        compressed_path = None
        saved_compressed_path = None
        
        try:
            # Step 1: Get audio info & compress
            recording.processing_step = "compressing"
            self.db.commit()
            
            # Extract comprehensive audio metadata
            print(f"📊 Extracting audio metadata...")
            metadata = get_audio_metadata(file_path)
            
            if metadata['duration']:
                recording.duration_seconds = metadata['duration']
            recording.sample_rate = metadata['sample_rate']
            recording.bit_rate = metadata['bit_rate']
            recording.channels = metadata['channels']
            recording.codec = metadata['codec']
            recording.recorded_at = metadata['recorded_at']
            
            print(f"   Duration: {metadata['duration']:.1f}s" if metadata['duration'] else "   Duration: unknown")
            print(f"   Sample Rate: {metadata['sample_rate']} Hz" if metadata['sample_rate'] else "")
            print(f"   Bit Rate: {metadata['bit_rate']} kbps" if metadata['bit_rate'] else "")
            print(f"   Channels: {metadata['channels']} ({'mono' if metadata['channels'] == 1 else 'stereo' if metadata['channels'] == 2 else 'multi'})" if metadata['channels'] else "")
            print(f"   Codec: {metadata['codec']}" if metadata['codec'] else "")
            print(f"   Recorded: {metadata['recorded_at']}" if metadata['recorded_at'] else "")
            
            # Compress audio with FFmpeg
            if check_ffmpeg():
                compressed_path, original_size, compressed_size = compress_audio(file_path)
                recording.original_size_mb = original_size
                recording.compressed_size_mb = compressed_size
                audio_to_use = compressed_path
                
                # ALWAYS save compressed file permanently for download
                output_dir = Path("data/compressed")
                output_dir.mkdir(parents=True, exist_ok=True)
                base_name = Path(recording.original_filename).stem
                
                # Add recording timestamp to filename if available
                if recording.recorded_at:
                    timestamp = recording.recorded_at.strftime("%m-%d-%Y_%I-%M%p")
                    saved_compressed_path = output_dir / f"{recording_id}_{base_name}_{timestamp}.opus"
                else:
                    saved_compressed_path = output_dir / f"{recording_id}_{base_name}.opus"
                    
                shutil.copy2(str(compressed_path), str(saved_compressed_path))
                recording.compressed_file_path = str(saved_compressed_path)
            else:
                recording.original_size_mb = file_path.stat().st_size / (1024 * 1024)
                recording.compressed_size_mb = recording.original_size_mb
                audio_to_use = file_path
                
                # Save original as "compressed" if no FFmpeg
                output_dir = Path("data/compressed")
                output_dir.mkdir(parents=True, exist_ok=True)
                
                # Add recording timestamp to filename if available
                if recording.recorded_at:
                    timestamp = recording.recorded_at.strftime("%m-%d-%Y_%I-%M%p")
                    base_name = Path(file_path.name).stem
                    ext = Path(file_path.name).suffix
                    saved_compressed_path = output_dir / f"{recording_id}_{base_name}_{timestamp}{ext}"
                else:
                    saved_compressed_path = output_dir / f"{recording_id}_{file_path.name}"
                    
                shutil.copy2(str(file_path), str(saved_compressed_path))
                recording.compressed_file_path = str(saved_compressed_path)
            
            self.db.commit()
            
            # Step 2: Transcribe with Gemini
            recording.processing_step = "transcribing"
            recording.processing_message = "Preparing to transcribe..."
            self.db.commit()
            
            transcript = self._transcribe_with_retry(audio_to_use, recording)
            recording.transcript = transcript
            recording.processing_message = "Transcription complete!"
            self.db.commit()
            
            # Step 3: Generate breakdown with Gemini
            recording.processing_step = "analyzing"
            recording.processing_message = "Preparing breakdown..."
            self.db.commit()
            
            breakdown = self._breakdown_with_retry(transcript, recording)
            recording.breakdown = breakdown
            
            # Mark complete
            recording.status = "completed"
            recording.processing_step = "done"
            recording.processed_at = datetime.utcnow()
            self.db.commit()
            
            return recording
            
        except Exception as e:
            recording.status = "failed"
            recording.error_message = str(e)
            self.db.commit()
            raise
            
        finally:
            # Cleanup temp compressed file (the permanent copy is already saved)
            if compressed_path and compressed_path != file_path and saved_compressed_path:
                try:
                    if str(compressed_path) != str(saved_compressed_path):
                        compressed_path.unlink(missing_ok=True)
                except:
                    pass
    
    def _transcribe_with_retry(self, audio_path: Path, recording) -> str:
        """Transcribe with automatic key rotation and rate limit handling."""
        logger.info(f"🔁 Starting transcription with retry logic | Recording ID: {recording.id}")
        last_error = None
        
        for attempt in range(self.MAX_RETRIES):
            try:
                recording.processing_message = "Uploading audio to Gemini..."
                self.db.commit()
                
                client, model_name, current_key = self.key_manager.get_model()
                
                # Track which API key is being used
                recording.api_key_id = current_key.id
                recording.api_key_name = current_key.name
                recording.processing_message = f"Transcribing with Gemini AI (using key: {current_key.name})"
                self.db.commit()
                logger.info(f"🔑 Using API key: {current_key.name} | Attempt {attempt + 1}/{self.MAX_RETRIES}")
                
                result = transcribe_audio(client, model_name, audio_path, self.key_manager, current_key)
                
                # Mark successful use
                self.key_manager.mark_key_used(current_key, success=True)
                logger.info(f"✅ Transcription successful | Key: {current_key.name} | Length: {len(result)} chars")
                return result
                
            except Exception as e:
                last_error = e
                error_str = str(e).lower()
                
                # Check if it's a rate limit/quota error (429 Too Many Requests)
                if "429" in error_str or "too many requests" in error_str or "quota" in error_str or "resource exhausted" in error_str:
                    # Mark this key as exhausted and try next key immediately
                    self.key_manager.mark_key_exhausted(current_key, str(e))
                    recording.processing_message = f"Rate limit hit on {current_key.name}, switching to next key..."
                    self.db.commit()
                    
                    # Check if we have another key available
                    if not self.key_manager.get_next_available_key():
                        raise Exception(f"All API keys are exhausted. Please add a new key or wait for quotas to reset.")
                    
                    # Continue to next attempt with a new key
                    continue
                
                # Check if it's a network error (broken pipe, connection reset, timeout)
                # These happen within seconds, not minutes - retry with increasing delays
                if any(err in error_str for err in ["broken pipe", "errno 32", "connection", "reset", "timeout"]):
                    wait_time = min(5 * (2 ** attempt), 30)  # 5s, 10s, 20s, 30s max
                    logger.warning(f"🔌 Network error detected | Retrying in {wait_time}s... | Attempt {attempt + 1}/{self.MAX_RETRIES}")
                    recording.processing_message = f"Network error (broken pipe), retrying in {wait_time}s... (attempt {attempt + 1}/{self.MAX_RETRIES})"
                    self.db.commit()
                    time.sleep(wait_time)
                    continue
                
                # For other errors, mark as failed use and retry
                self.key_manager.mark_key_used(current_key, success=False)
                
                if attempt >= self.MAX_RETRIES - 1:
                    raise Exception(f"Transcription failed: {e}")
        
        raise Exception(f"Transcription failed after {self.MAX_RETRIES} attempts: {last_error}")
    
    def _breakdown_with_retry(self, transcript: str, recording) -> str:
        """Generate breakdown with automatic key rotation and rate limit handling."""
        last_error = None
        
        for attempt in range(self.MAX_RETRIES):
            try:
                recording.processing_message = "Analyzing transcript..."
                self.db.commit()
                
                # Use gemini-3.0-flash for breakdown
                client, model_name, current_key = self.key_manager.get_model()
                
                # Update which key is being used
                recording.api_key_id = current_key.id
                recording.api_key_name = current_key.name
                recording.processing_message = f"Generating structured breakdown with Gemini (using key: {current_key.name})"
                self.db.commit()
                logger.info(f"📣 Using {model_name} for breakdown | Key: {current_key.name}")
                
                result = generate_breakdown(client, model_name, transcript, self.key_manager, current_key)
                
                # Mark successful use
                self.key_manager.mark_key_used(current_key, success=True)
                return result
                
            except Exception as e:
                last_error = e
                error_str = str(e).lower()
                
                # Check if it's a rate limit/quota error (429 Too Many Requests)
                if "429" in error_str or "too many requests" in error_str or "quota" in error_str or "resource exhausted" in error_str:
                    # Mark this key as exhausted and try next key immediately
                    self.key_manager.mark_key_exhausted(current_key, str(e))
                    recording.processing_message = f"Rate limit hit on {current_key.name}, switching to next key..."
                    self.db.commit()
                    
                    # Check if we have another key available
                    if not self.key_manager.get_next_available_key():
                        raise Exception(f"All API keys are exhausted. Please add a new key or wait for quotas to reset.")
                    
                    # Continue to next attempt with a new key
                    continue
                
                # For other errors, mark as failed use and retry
                self.key_manager.mark_key_used(current_key, success=False)
                
                if attempt >= self.MAX_RETRIES - 1:
                    raise Exception(f"Breakdown generation failed: {e}")
        
        raise Exception(f"Breakdown failed after {self.MAX_RETRIES} attempts: {last_error}")
    
    def compress_only(self, file_path: Path, recording_id: int) -> Recording:
        """
        Only compress the audio file without transcription.
        Saves compressed file to disk for download.
        """
        import shutil
        
        recording = self.db.query(Recording).filter(Recording.id == recording_id).first()
        if not recording:
            raise Exception(f"Recording {recording_id} not found")
        
        recording.status = "processing"
        recording.processing_step = "compressing"
        recording.is_compress_only = True
        self.db.commit()
        
        try:
            # Get audio duration
            duration = get_audio_duration(file_path)
            if duration:
                recording.duration_seconds = duration
            
            # Compress audio
            if check_ffmpeg():
                compressed_path, original_size, compressed_size = compress_audio(file_path)
                recording.original_size_mb = original_size
                recording.compressed_size_mb = compressed_size
                
                # Save compressed file to permanent location
                output_dir = Path("data/compressed")
                output_dir.mkdir(parents=True, exist_ok=True)
                
                # Create output filename with timestamp if available
                base_name = Path(recording.original_filename).stem
                if recording.recorded_at:
                    timestamp = recording.recorded_at.strftime("%m-%d-%Y_%I-%M%p")
                    output_file = output_dir / f"{recording_id}_{base_name}_{timestamp}.opus"
                else:
                    output_file = output_dir / f"{recording_id}_{base_name}.opus"
                
                # Move compressed file to permanent location
                if compressed_path != file_path:
                    shutil.move(str(compressed_path), str(output_file))
                else:
                    shutil.copy2(str(file_path), str(output_file))
                
                recording.compressed_file_path = str(output_file)
            else:
                # No FFmpeg - just copy the original
                recording.original_size_mb = file_path.stat().st_size / (1024 * 1024)
                recording.compressed_size_mb = recording.original_size_mb
                
                output_dir = Path("data/compressed")
                output_dir.mkdir(parents=True, exist_ok=True)
                
                # Add timestamp to filename if available
                if recording.recorded_at:
                    timestamp = recording.recorded_at.strftime("%m-%d-%Y_%I-%M%p")
                    base_name = Path(file_path.name).stem
                    ext = Path(file_path.name).suffix
                    output_file = output_dir / f"{recording_id}_{base_name}_{timestamp}{ext}"
                else:
                    output_file = output_dir / f"{recording_id}_{file_path.name}"
                    
                shutil.copy2(str(file_path), str(output_file))
                recording.compressed_file_path = str(output_file)
            
            recording.status = "completed"
            recording.processing_step = "done"
            recording.processed_at = datetime.utcnow()
            self.db.commit()
            
            # Clean up original upload
            try:
                file_path.unlink(missing_ok=True)
            except:
                pass
            
            return recording
            
        except Exception as e:
            recording.status = "failed"
            recording.error_message = str(e)
            self.db.commit()
            raise
