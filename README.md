# 🎨 AI Model Generator MVP

Generate hyper-realistic AI models with face generation, video animation, and lip sync capabilities.

![AI Model Generator](https://img.shields.io/badge/version-1.0.0-blue)
![Python](https://img.shields.io/badge/python-3.10+-green)
![FastAPI](https://img.shields.io/badge/FastAPI-0.109-teal)

## ✨ Features

- **Face Generation** - Create realistic AI faces using Nano Banana Pro
- **Video Generation** - Animate faces with natural motion using Kling 2.6 Motion Control
- **Lip Sync** - Add realistic voice and lip sync using ElevenLabs/Sync Labs/D-ID

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Frontend (HTML/CSS/JS)                  │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐        │
│  │  Image  │  │  Video  │  │ LipSync │  │ Results │        │
│  │  Panel  │  │  Panel  │  │  Panel  │  │  Panel  │        │
│  └────┬────┘  └────┬────┘  └────┬────┘  └────┬────┘        │
└───────┼────────────┼────────────┼────────────┼──────────────┘
        │            │            │            │
        ▼            ▼            ▼            ▼
┌─────────────────────────────────────────────────────────────┐
│                    FastAPI Backend                           │
│  ┌──────────────────────────────────────────────────────┐   │
│  │                    API Routes                         │   │
│  │  /api/face/generate  │ /api/video/generate           │   │
│  │  /api/lipsync/generate │ /api/jobs/{id}              │   │
│  └──────────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────────┐   │
│  │                    Services                           │   │
│  │  ┌────────────┐ ┌────────────┐ ┌────────────────┐   │   │
│  │  │   Face     │ │   Video    │ │    LipSync     │   │   │
│  │  │ Generator  │ │ Generator  │ │   Generator    │   │   │
│  │  └─────┬──────┘ └─────┬──────┘ └───────┬────────┘   │   │
│  └────────┼──────────────┼────────────────┼─────────────┘   │
└───────────┼──────────────┼────────────────┼─────────────────┘
            │              │                │
            ▼              ▼                ▼
     ┌────────────┐ ┌────────────┐ ┌────────────────┐
     │ Nano Banana│ │ Kling 2.6  │ │ ElevenLabs /   │
     │    Pro     │ │   Motion   │ │ Sync Labs /    │
     │            │ │  Control   │ │    D-ID        │
     └────────────┘ └────────────┘ └────────────────┘
```

## 🚀 Quick Start

### Prerequisites

- Python 3.10+
- Node.js (optional, for serving frontend)

### Backend Setup

```bash
# Navigate to backend
cd backend

# Create virtual environment
python -m venv venv

# Activate (Windows)
venv\Scripts\activate
# Activate (Linux/Mac)
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy and configure environment
copy env.example.txt .env
# Edit .env with your API keys

# Run server
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend Setup

```bash
# Option 1: Simple HTTP server (Python)
cd frontend
python -m http.server 3000

# Option 2: Open directly in browser
# Just open frontend/index.html in your browser
```

### Access

- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs

## ⚙️ Configuration

Create a `.env` file in the `backend` directory:

```env
# Nano Banana Pro (Face Generation)
NANO_BANANA_API_KEY=your_key_here
NANO_BANANA_BASE_URL=https://api.nanobanana.com/v1

# Kling 2.6 (Video Generation)
KLING_API_KEY=your_key_here
KLING_BASE_URL=https://api.kling.ai/v1

# Lip Sync Provider (choose one: elevenlabs, sync_labs, d-id)
LIPSYNC_PROVIDER=elevenlabs

# ElevenLabs
ELEVENLABS_API_KEY=your_key_here

# Sync Labs (recommended for lip sync)
SYNC_LABS_API_KEY=your_key_here

# D-ID
DID_API_KEY=your_key_here

# Server
DEBUG=true
```

## 📡 API Endpoints

### Face Generation

```http
POST /api/face/generate
Content-Type: multipart/form-data

prompt: string (required)
mode: string (nano-banana, realistic, artistic)
aspect_ratio: string (auto, 1:1, 9:16, 16:9)
strength: float (0.0-1.0)
images: File[] (optional, max 4)
```

### Video Generation

```http
POST /api/video/generate
Content-Type: multipart/form-data

image: File (required)
motion_type: string (natural, dynamic, subtle, talking)
duration_seconds: int (2-10)
motion_prompt: string (optional)
aspect_ratio: string (9:16, 1:1, 16:9)
```

### Lip Sync Generation

```http
POST /api/lipsync/generate
Content-Type: multipart/form-data

video: File (required)
text: string (required, max 5000 chars)
voice_type: string (female_young, female_mature, female_soft, male_young, male_deep)
language: string (en, it, es, fr, de, pt, ja, ko, zh)
```

### Job Status

```http
GET /api/jobs/{job_id}

Response:
{
  "job_id": "uuid",
  "job_type": "face|video|lipsync",
  "status": "pending|processing|completed|failed",
  "progress": 0-100,
  "message": "Status message",
  "result_url": "/storage/faces/uuid.png",
  "error": null
}
```

## 📁 Project Structure

```
MODEL AI/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py           # FastAPI application
│   │   ├── config.py         # Settings & configuration
│   │   ├── models.py         # Pydantic models
│   │   ├── routes/
│   │   │   ├── face.py       # Face generation endpoints
│   │   │   ├── video.py      # Video generation endpoints
│   │   │   └── lipsync.py    # Lip sync endpoints
│   │   └── services/
│   │       ├── job_manager.py      # Job tracking
│   │       ├── face_generator.py   # Nano Banana integration
│   │       ├── video_generator.py  # Kling integration
│   │       └── lipsync_generator.py # Voice & lip sync
│   ├── storage/              # Generated files
│   │   ├── faces/
│   │   ├── videos/
│   │   ├── lipsync/
│   │   └── uploads/
│   ├── requirements.txt
│   └── env.example.txt
├── frontend/
│   ├── index.html
│   ├── styles.css
│   └── app.js
└── README.md
```

## 🔄 Workflow

1. **Generate Face**
   - Upload reference images (optional)
   - Write a prompt describing the desired face
   - Click "Generate" and wait for completion

2. **Create Video**
   - Use the generated face or upload a new one
   - Select motion type and duration
   - Click "Generate Video"

3. **Add Lip Sync**
   - Use the generated video
   - Enter the text to speak
   - Select voice type and language
   - Click "Apply Lip Sync"

## 🎨 Customization

### Voice Types

| Type | Description |
|------|-------------|
| `female_young` | Youthful, energetic female voice |
| `female_mature` | Confident, professional female voice |
| `female_soft` | Gentle, soothing female voice |
| `male_young` | Youthful, friendly male voice |
| `male_deep` | Deep, authoritative male voice |

### Motion Types

| Type | Description |
|------|-------------|
| `natural` | Subtle head movements, blinking, breathing |
| `dynamic` | More expressive, head turns, gestures |
| `subtle` | Minimal movement, calm expression |
| `talking` | Mouth movements as if speaking |

## ⚠️ Important Notes

- **API Keys Required**: You need valid API keys for each provider
- **Costs**: Each generation has associated credit costs
- **Processing Time**: Video and lip sync can take 30-60+ seconds
- **File Limits**: Max 10MB for images, 50MB for videos

## 🛠️ Troubleshooting

### CORS Issues
If running frontend and backend on different ports, ensure CORS is configured in `main.py`.

### API Timeouts
Increase `JOB_TIMEOUT_SECONDS` in `.env` for longer generations.

### Missing Dependencies
```bash
pip install -r requirements.txt --upgrade
```

## 📄 License

MIT License - Feel free to use and modify for your projects.

---

Built with ❤️ using FastAPI, Python, and vanilla JavaScript.

