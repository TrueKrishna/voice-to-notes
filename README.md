# 🎙️ Voice to Notes

> Transform voice memos into structured, actionable markdown notes using Gemini AI

A powerful web application that converts voice recordings (iPhone, Android, or any device) into beautifully formatted markdown documents. Built with FastAPI, Google's Gemini AI, and Docker for seamless deployment.

![Python](https://img.shields.io/badge/Python-3.11-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.109-green)
![Gemini](https://img.shields.io/badge/Gemini-3--Flash--Preview-orange)
![Docker](https://img.shields.io/badge/Docker-Ready-blue)
![License](https://img.shields.io/badge/License-MIT-green)

---

## ✨ Features

### 🎵 Audio Processing
- **Multi-format Support**: MP3, M4A, WAV, OGG, FLAC, WebM, AAC
- **Intelligent Compression**: Reduces file size up to 10x using FFmpeg (Opus codec)
- **Compress-Only Mode**: Just compress audio without transcription
- **Audio Player**: Built-in player on recording pages for playback

### 🤖 AI Transcription
- **Gemini 3 Flash Preview**: Latest model for fast, accurate transcription
- **Hindi/Hinglish Support**: Excellent code-switching between Hindi and English
- **Speaker Identification**: Distinguishes and labels multiple speakers
- **Timestamped Output**: Automatic timestamps every 1-2 minutes

### 🔑 Smart API Key Management
- **Key Rotation**: Add multiple Gemini keys with automatic failover
- **Load Balancing**: Capacity-aware distribution across keys (5 RPM per key)
- **Race Condition Prevention**: Key locking for parallel processing
- **Queue Visibility**: See your position in the processing queue

### 📊 Processing Pipeline
1. **Upload** → Audio file received and validated
2. **Compress** → FFmpeg reduces file size (Opus codec @ 32kbps)
3. **Transcribe** → Gemini AI generates verbatim transcript
4. **Analyze** → Structured breakdown with topics, action items, insights

### 🌙 User Experience
- **Dark Mode**: Beautiful dark theme for comfortable viewing
- **Real-time Progress**: Step-by-step processing status with visual indicators
- **Drag & Drop**: Easy file upload interface
- **Download Options**: Export transcripts and breakdowns as markdown

---

## 📦 Output

For each audio file, generates two markdown files:

| File | Contents |
|------|----------|
| `*_transcript.md` | Raw verbatim transcription with timestamps and speaker labels |
| `*_breakdown.md` | Structured breakdown with topics, action items, key insights |

### Breakdown Structure
- **Summary**: Quick overview of the recording
- **Topics Discussed**: Main subjects covered with details
- **Action Items**: Tasks and follow-ups mentioned
- **Key Insights**: Important takeaways and decisions
- **Questions/Open Items**: Unresolved points for follow-up

---

## 🚀 Quick Start

### Option 1: Docker (Recommended)

```bash
# Clone the repository
git clone https://github.com/yourusername/voice-to-notes.git
cd voice-to-notes

# Start the application
docker-compose up -d

# Open in browser
open http://localhost:9123
```

### Option 2: Local Development

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Install FFmpeg (for audio compression)
brew install ffmpeg  # macOS
# or: apt-get install ffmpeg  # Ubuntu

# Run the app
uvicorn app.main:app --reload --port 8000

# Open in browser
open http://localhost:8000
```

---

## 🔑 Setup API Keys

1. Open the app at `http://localhost:9123`
2. Click **"API Keys"** in the navigation
3. Add your Gemini API key from [AI Studio](https://aistudio.google.com/apikey)
4. (Optional) Add multiple keys for higher throughput

### API Key Limits (Free Tier)
- **5 RPM** (requests per minute) per key
- **250K TPM** (tokens per minute) per key
- Adding 2 keys = 10 RPM = ~5 parallel recordings

---

## 🖥️ Usage

### Basic Workflow
1. **Upload**: Drag & drop or select your audio file
2. **Choose Mode**: 
   - *Process* - Full transcription + breakdown
   - *Compress Only* - Just reduce file size
3. **Wait**: Processing takes 1-5 minutes depending on length
4. **View**: See the structured breakdown and raw transcript
5. **Download**: Export as markdown files

### Tips
- **Long recordings**: Handles files up to ~2 hours
- **Multiple speakers**: Automatically distinguishes voices
- **Background noise**: Works well, but quieter is better
- **File size**: 50MB+ typically compresses to 2-5MB

---

## 🔄 Smart API Key Rotation

### Features
- **Capacity Tracking**: Monitors requests per minute per key
- **Load Balancing**: Distributes load across available keys
- **Auto-Failover**: Switches to next key on quota exhaustion
- **Key Locking**: Prevents race conditions in parallel processing

### Queue System
- See your position in the processing queue
- Estimated wait time displayed
- API capacity status visible during processing

---

## 🐳 Docker Deployment

### Volumes
Data is persisted in Docker volumes:
```yaml
volumes:
  voice_notes_data:  # SQLite DB + uploaded files
```

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | Database connection string | `sqlite:///./data/voice_notes.db` |
| `GEMINI_API_KEY` | Pre-set API key (optional) | - |

### View Logs
```bash
docker-compose logs -f
```

### Rebuild After Changes
```bash
docker-compose up --build -d
```

---

## 📁 Project Structure

```
voice-to-notes/
├── app/
│   ├── __init__.py
│   ├── main.py          # FastAPI routes & endpoints
│   ├── database.py      # SQLAlchemy models (Recording, APIKey, Settings)
│   ├── api_keys.py      # Key rotation & load balancing logic
│   ├── processor.py     # Audio compression & AI transcription
│   └── templates/
│       ├── index.html   # Dashboard with recording list
│       ├── recording.html # Recording detail view
│       ├── keys.html    # API key management
│       └── storage.html # Storage management
├── data/                # SQLite DB + uploads (Docker volume)
├── transcribe.py        # Standalone CLI tool
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── TIMELINE.md          # Project development story
└── README.md
```

---

## 🔧 Technical Details

### Stack
- **Backend**: FastAPI (Python 3.11)
- **AI**: Google Gemini 3 Flash Preview
- **Database**: SQLite (PostgreSQL optional)
- **Audio**: FFmpeg with Opus codec
- **Frontend**: Jinja2 templates + Alpine.js + Tailwind CSS

### Key Technical Decisions
- **Temperature 1.0**: Google's recommendation to prevent AI looping
- **Opus @ 32kbps**: Optimal balance of compression and quality
- **15-second key locks**: Prevents parallel processing race conditions
- **90-second rate limit waits**: Handles free tier limits gracefully

---

## 💰 Cost Estimate

Gemini 3 Flash Preview pricing (approximate):
- Audio processing: ~$0.00025 per second
- Text generation: Generous free tier limits
- **Typical 30-min recording: ~$0.45**

Free tier is sufficient for personal use.

---

## 🛠️ Troubleshooting

### "No API keys available"
Add a key via: `http://localhost:9123/keys`

### "All keys at capacity"
- Wait 60 seconds for rate limit reset
- Add more API keys for higher throughput

### "FFmpeg not found" (local only)
```bash
brew install ffmpeg  # macOS
apt-get install ffmpeg  # Ubuntu
```

### Container Issues
```bash
# View logs
docker-compose logs -f

# Rebuild
docker-compose up --build -d

# Reset everything
docker-compose down -v
docker-compose up --build -d
```

### Transcription Looping
Fixed with temperature=1.0 (Google's strong recommendation)

---

## 📄 License

MIT License - see [LICENSE](LICENSE) for details.

---

## 🙏 Acknowledgments

- [Google Gemini AI](https://ai.google.dev/) for powerful multimodal AI
- [FastAPI](https://fastapi.tiangolo.com/) for the excellent web framework
- [FFmpeg](https://ffmpeg.org/) for audio processing
- [Tailwind CSS](https://tailwindcss.com/) for beautiful styling

---

Made with ❤️ for turning thoughts into organized notes.
