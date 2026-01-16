# 📜 Voice to Notes - Development Timeline

> The story of how this project evolved from a simple idea to a full-featured voice transcription application.

---

## 🌱 The Beginning

### Day 1: The Problem
I had a simple problem: I record a lot of voice memos on my iPhone—meeting notes, random ideas, thoughts while walking—but they just sit there, never listened to again. I needed a way to turn these audio files into structured, searchable notes.

### Initial Concept
- Upload voice memos
- Transcribe using AI
- Get organized markdown notes
- That's it. Simple.

---

## 🏗️ Phase 1: Foundation

### Core Architecture
Built the foundation with:
- **FastAPI** for the web framework (fast, modern, great docs)
- **SQLAlchemy** for database models
- **SQLite** for simplicity (Docker-ready)
- **Jinja2** templates for server-side rendering

### First Working Version
```python
# The heart of it all
class Recording(Base):
    id = Column(Integer, primary_key=True)
    original_filename = Column(String)
    transcript = Column(Text)
    breakdown = Column(Text)
    status = Column(String)  # pending, processing, completed, failed
```

### Key Files Created
- `app/main.py` - FastAPI routes
- `app/database.py` - SQLAlchemy models
- `app/processor.py` - Transcription logic
- `app/templates/` - HTML templates

---

## 🎵 Phase 2: Audio Compression

### The Problem
iPhone voice memos can be huge (50MB+ for a 30-min recording). Uploading and processing these was slow and expensive.

### The Solution: FFmpeg + Opus
```python
# Compress audio using FFmpeg
subprocess.run([
    'ffmpeg', '-i', input_path,
    '-c:a', 'libopus',  # Opus codec - excellent for speech
    '-b:a', '32k',       # 32kbps - good quality, small size
    '-ar', '16000',      # 16kHz sample rate
    output_path
])
```

### Results
- **10x compression** typical (50MB → 5MB)
- Quality preserved for speech
- Processing time reduced significantly

### Added Features
- Compression statistics display
- "Compress Only" mode for when you just want smaller files
- Original vs compressed size comparison

---

## 🔑 Phase 3: API Key Management

### The Problem
Gemini has rate limits. Free tier = 10 RPM. One recording uses 2 requests (transcribe + breakdown). Hitting limits was frustrating.

### The Solution: Multi-Key Rotation
```python
class APIKeyManager:
    def get_next_available_key(self):
        # Find a key that isn't exhausted
        # Automatic rotation on quota errors
        pass
    
    def handle_error(self, error, key):
        if self.is_quota_error(error):
            self.mark_key_exhausted(key)
            return True  # Signal to retry with new key
```

### Features Added
- Add/remove multiple API keys via UI
- Automatic failover when one key hits quota
- Reset exhausted keys when quota refreshes
- Key status dashboard

---

## 🌙 Phase 4: Dark Mode & UX Polish

### User Experience Improvements
The app was functional but ugly. Time to make it beautiful.

### Added
- **Dark mode** with smooth transitions
- **Real-time progress** indicators
- **Step-by-step visualization** (Upload → Compress → Transcribe → Analyze)
- **Drag & drop** file upload
- **Beautiful typography** with Tailwind CSS

### Processing Pipeline Visual
```
📤 Upload → 🗜️ FFmpeg → 🎙️ Transcribe → 🧠 Analyze
   ✓         ✓ 5.2MB      ⏳ Working...
```

---

## 🎧 Phase 5: Audio Player

### The Request
"Can I listen to the recording while reading the transcript?"

### The Solution
```html
<audio controls preload="metadata" class="w-full">
    <source src="/recording/{{ id }}/audio/stream" type="audio/mpeg">
</audio>
```

### Implementation
- Added `/recording/{id}/audio/stream` endpoint
- Proper MIME type detection
- Range request support for seeking
- Dark mode styled audio controls

---

## 🔄 Phase 6: The Looping Bug

### The Problem
Transcripts were repeating the same phrase 50+ times. Example:
> "And then I said... And then I said... And then I said..."

This was catastrophic for usability.

### Investigation
Research into Google's documentation revealed:

> **"When using Gemini models, we STRONGLY recommend keeping temperature at 1.0. Changing the temperature (setting it below 1.0) may lead to unexpected behavior, such as looping."**

### The Fix
```python
# WRONG (causes looping)
temperature=0.1

# CORRECT (Google's recommendation)
generation_config=genai.GenerationConfig(
    temperature=1.0,  # CRITICAL: Must be 1.0
    top_p=0.95,
    top_k=40,
)
```

### Additional Prompt Engineering
Added explicit anti-looping instructions:
```
CRITICAL - Avoid Repetition:
- If you encounter silence, write "[silence]" instead of repeating
- DO NOT loop or repeat the same phrase
- Move forward through the audio
```

---

## 🚀 Phase 7: Model Upgrade

### The Opportunity
Gemini 3.0 Flash was released with better performance.

### The Challenge
Model naming was confusing. Tried:
- `gemini-3.0-flash` ❌ 404 error
- `gemini-3-flash` ❌ Not found
- Used `genai.list_models()` to discover: `gemini-3-flash-preview` ✅

### The Change
```python
# Updated default model
def get_model(self, model_name: str = "gemini-3-flash-preview"):
    # Now using latest model for both transcription and breakdown
```

---

## ⚡ Phase 8: Smart Parallel Processing

### The Problem
With multiple recordings uploading simultaneously:
1. Race conditions when grabbing API keys
2. No load balancing across keys
3. Users couldn't see their queue position

### The Solution: Capacity-Aware Key Management

#### 1. Key Locking (Prevent Race Conditions)
```python
class APIKey(Base):
    locked_until = Column(DateTime)  # 15-second lock
    requests_this_minute = Column(Integer)
    minute_window_start = Column(DateTime)
```

#### 2. Smart Load Balancing
```python
def get_next_available_key(self):
    # Filter out locked keys
    # Filter out keys at capacity (5 RPM)
    # Select key with MOST remaining capacity
    key_capacities.sort(key=lambda x: x[1], reverse=True)
    return key_capacities[0][0]
```

#### 3. Queue Position Visibility
```python
# Calculate queue position
queue_position = db.query(Recording).filter(
    Recording.status.in_(["pending", "processing"]),
    Recording.created_at < recording.created_at
).count() + 1

# Return in status API
return {
    "queue_position": queue_position,
    "estimated_wait_seconds": estimated_wait,
    "key_status": key_status
}
```

### UI Updates
- Queue position badge: "Position 3 in queue"
- Estimated wait time: "~2 min"
- API capacity indicator

---

## 📊 Phase 9: Logging & Monitoring

### Docker Monitoring
Added rich logging throughout for Docker log visibility:

```python
logger = logging.getLogger(__name__)

# Startup
logger.info("🚀 Voice to Notes starting up...")
logger.info("📊 Initializing database...")

# Upload
logger.info(f"📤 New upload: {filename}")
logger.info(f"🔑 Assigned API key: {key.name}")

# Processing
logger.info(f"🎙️ Transcribing {recording.id}...")
logger.info(f"✅ Completed in {duration}s")
```

### Log Format
```
2026-01-16 10:30:45 | INFO     | app.main | 🚀 Voice to Notes starting up...
2026-01-16 10:30:45 | INFO     | app.main | 📊 Initializing database...
2026-01-16 10:30:46 | INFO     | app.main | ✅ Database ready
```

---

## 📈 Current State (January 2026)

### Features Complete
- ✅ Multi-format audio support (MP3, M4A, WAV, OGG, FLAC, WebM, AAC)
- ✅ FFmpeg compression (Opus @ 32kbps)
- ✅ Gemini 3 Flash transcription
- ✅ Structured breakdown generation
- ✅ Multi-key API rotation with load balancing
- ✅ Dark mode UI
- ✅ Real-time progress tracking
- ✅ Queue position visibility
- ✅ Audio player on recording pages
- ✅ Docker deployment with persistent volumes
- ✅ Comprehensive logging

### Tech Stack
| Component | Technology |
|-----------|------------|
| Backend | FastAPI (Python 3.11) |
| AI | Google Gemini 3 Flash Preview |
| Database | SQLite (SQLAlchemy ORM) |
| Audio | FFmpeg + Opus codec |
| Frontend | Jinja2 + Alpine.js + Tailwind CSS |
| Deployment | Docker + Docker Compose |

### Performance
- **Compression**: 10x reduction typical
- **Processing**: 1-5 minutes per recording
- **Capacity**: 5 recordings/minute per API key
- **Reliability**: Automatic retry with exponential backoff

---

## 🔮 Future Ideas

### Potential Enhancements
- [ ] Batch upload multiple files
- [ ] Search across all transcripts
- [ ] Export to Notion/Obsidian
- [ ] Mobile-responsive redesign
- [ ] Webhook notifications when complete
- [ ] Multi-language support beyond Hindi/English
- [ ] Speaker diarization improvements
- [ ] Audio quality analysis before processing

### Infrastructure
- [ ] PostgreSQL support (for scale)
- [ ] Redis for job queue
- [ ] Kubernetes deployment
- [ ] S3/GCS for audio storage

---

## 📝 Lessons Learned

### 1. AI Temperature Matters
Setting temperature below 1.0 causes looping. Google's documentation is clear but easy to miss.

### 2. Compression is Essential
Audio files are huge. Compressing before AI processing saves time, money, and API quota.

### 3. Rate Limits Need Planning
Free tier limits (10 RPM) require careful key management for any serious usage.

### 4. Real-time Feedback is Critical
Users need to know what's happening. Progress indicators and queue positions reduce anxiety.

### 5. Docker Simplifies Everything
Packaging with Docker made deployment trivial and reproducible.

---

## 🙏 Acknowledgments

This project was built iteratively, solving real problems as they emerged. What started as a simple transcription tool evolved into a full-featured voice memo processing system.

Special thanks to:
- Google's Gemini AI for making this possible
- The FastAPI team for an excellent framework
- FFmpeg for incredible audio processing capabilities

---

*Last updated: January 16, 2026*
