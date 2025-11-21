# Scribe 🎙️

A professional real-time system audio transcription tool for Windows with AI-powered meeting synthesis. Features a sleek LCD-style interface, GPU-accelerated transcription, and intelligent audio processing.

## ✨ Features

### 🎨 Professional GUI (`app_pro.py`)
- **LCD-Style Interface**: Compact 800x50px horizontal bar with cyan backlit aesthetic
- **Real-Time Waveform**: Animated 60-bar spectrum analyzer showing audio levels
- **Seven-Segment Timer**: Retro digital display with Courier New monospace font
- **Intuitive Controls**: Play/pause/stop buttons with hamburger menu
- **System Tray Integration**: Minimize to tray with green recording indicator
- **Always Visible**: Shows in both taskbar and system tray

### 🎙️ Audio Capture & Transcription
- **WASAPI Loopback**: Captures system audio from any output device (speakers, headphones)
- **GPU Acceleration**: Fully optimized for NVIDIA GPUs using CUDA 12 & cuDNN 9
- **Smart Segmentation**: VAD-based chunking with ~60-second intervals for optimal transcription
- **Auto-Stop Detection**: Automatically ends recording after prolonged silence
- **Native Sample Rate Support**: Handles any device sample rate (44.1kHz, 48kHz, etc.)

### 🤖 AI-Powered Synthesis
- **Executive Summary**: Concise overview of meeting content
- **Dynamic Titles**: AI-generated meeting titles based on content
- **Time-Based Notes**: Detailed notes with timestamp headers for each discussion segment
- **Logseq Export**: Automatic export to Logseq knowledge base (if configured)
- **Markdown Output**: Clean, organized markdown files with proper formatting

### ⚡ Smart Features
- **Soft Pause**: Pause/resume recording without stopping transcription
- **Progress Tracking**: Visual progress bar for synthesis stages
- **Auto-Open**: Automatically opens completed notes in your default markdown editor
- **Session Management**: Organized folders with timestamps (`sessions/YYYY-MM-DD_HH-MM-SS/`)
- **Audio Archival**: Saves audio chunks for reference

## 📋 Prerequisites

- **OS**: Windows 10/11
- **Python**: 3.12+
- **GPU**: NVIDIA GPU (Recommended for speed, falls back to CPU)
- **Package Manager**: [uv](https://github.com/astral-sh/uv)

## 🚀 Installation

1. **Clone the repository**:
   ```powershell
   git clone <your-repo-url>
   cd scribe
   ```

2. **Install dependencies**:
   ```powershell
   uv sync
   ```

3. **(Optional) Configure Logseq**:
   - Edit `scribe.py` and set `LOGSEQ_GRAPH_PATH` to your Logseq graph directory
   - Example: `LOGSEQ_GRAPH_PATH = r"C:\Users\YourName\Documents\Logseq\YourGraph\pages"`

## 💻 Usage

### GUI Mode - Professional Interface (Recommended)

**Launch the app**:
```powershell
python app_pro.py
```

**Controls**:
- **▶️ Play Button** (Green): Start recording
- **⏸️ Pause Button** (Orange): Pause/resume recording
- **⏹️ Stop Button** (Red): Stop and process recording
- **☰ Menu Button**: Settings (placeholder)
- **× Close**: Minimize to system tray

**Workflow**:
1. Click **Play** to start recording
2. Timer shows `HH:MM:SS`, waveform animates with audio levels
3. Tray icon turns red with green indicator dot
4. Speak or play audio (meetings, videos, podcasts, etc.)
5. Click **Stop** or let auto-stop detect silence
6. Watch progress bar during AI synthesis
7. Notes automatically open when complete

**System Tray**:
- **Left-click**: Show/hide window
- **Right-click**: Menu with "Start/Stop Recording" and "Quit"
- **Recording Indicator**: Green dot appears on icon when recording

### GUI Mode - Simple Interface

**Launch the basic GUI**:
```powershell
python app.py
```

Features a traditional vertical layout with larger buttons and status text.

### CLI Mode

**For headless or scripted use**:
```powershell
python scribe.py
```

1. Select your audio output device from the list (look for `(Loopback)`)
2. Recording starts automatically
3. View real-time transcription in console
4. Press `Ctrl+C` to stop and trigger synthesis
5. Find output in `sessions/{timestamp}/`

## 📁 Output Structure

```
sessions/
└── 2025-11-20_19-30-45/
    ├── 2025-11-20_Project_Planning_Discussion.md  # Final synthesized notes
    ├── transcript_full.txt                         # Raw transcription
    ├── notes_logseq.md                            # Logseq export
    └── audio_chunks/
        ├── chunk_001.wav
        ├── chunk_002.wav
        └── ...
```

## ⚙️ Configuration

### Adjusting Auto-Stop Sensitivity

Edit `scribe.py`, `Transcriber class`, line ~146:
```python
self.silence_threshold = 0.01      # Volume threshold (lower = more sensitive)
self.max_silence_duration = 60.0   # Seconds of silence before auto-stop
```

### VAD & Chunking Parameters

In `Transcriber.__init__()`:
```python
self.min_duration = 50     # Minimum chunk duration (seconds)
self.max_duration = 90     # Maximum chunk duration (seconds)
self.buffer_duration_limit = 30  # Real-time buffer size (seconds)
```

### Logseq Integration

Set your Logseq graph path in `scribe.py`:
```python
LOGSEQ_GRAPH_PATH = r"C:\path\to\your\Logseq\graph\pages"
```

## 🎯 Use Cases

- **Meeting Transcription**: Capture Zoom, Teams, or Google Meet audio
- **Podcast Notes**: Transcribe and summarize podcast episodes
- **Lecture Recording**: Create organized notes from online lectures
- **Interview Processing**: Transcribe interviews with timestamps
- **Video Summaries**: Generate notes from YouTube videos or tutorials

## 🔧 Troubleshooting

### CUDA/GPU Issues
- **Error**: `CUDA not available` or `cuDNN DLL not found`
- **Solution**: Install latest NVIDIA drivers. The app automatically configures cuDNN paths.
- **Fallback**: App will use CPU if GPU unavailable (slower but functional)

### No Audio Detected
- **Check**: Ensure correct loopback device is selected
- **Verify**: Play audio and watch waveform - should animate when receiving audio
- **Windows**: Make sure "Stereo Mix" or similar loopback device is enabled in Sound Settings

### Synthesis Errors
- **Error**: `No transcript generated`
- **Cause**: No speech detected or audio too quiet
- **Solution**: Increase volume, speak clearly, or adjust `silence_threshold`

### "Silent chunk detected" Warnings
- **Normal**: App filters out silent audio to save processing time
- **If excessive**: Lower `silence_threshold` or increase input volume

## 🛠️ Development

### Project Structure
```
scribe/
├── app_pro.py              # Professional LCD-style GUI
├── app.py                  # Simple traditional GUI
├── scribe.py               # Core engine (CLI + backend)
├── pyproject.toml          # Dependencies
├── sessions/               # Output directory
└── README.md              # This file
```

### Key Components
- **SessionManager**: Creates and manages session directories
- **AudioRecorder**: WASAPI loopback capture with pause/resume
- **Transcriber**: Whisper transcription with VAD and smart chunking
- **MeetingSynthesizer**: AI-powered summary and note generation

## 📝 Notes

- **First Run**: Model download (~140MB) happens automatically
- **GPU Memory**: Requires ~2GB VRAM for medium Whisper model
- **CPU Fallback**: Works on CPU-only systems (slower transcription)
- **Privacy**: All processing is local - no cloud services used

## 📄 License

MIT License - See LICENSE file for details

## 🙏 Credits

Built with:
- [faster-whisper](https://github.com/guillaumekln/faster-whisper) - Efficient Whisper implementation
- [customtkinter](https://github.com/TomSchimansky/CustomTkinter) - Modern UI framework
- [soundcard](https://github.com/bastibe/SoundCard) - Cross-platform audio I/O
- [pystray](https://github.com/moses-palmer/pystray) - System tray integration
- [google-generativeai](https://github.com/google/generative-ai-python) - Gemini AI for synthesis

---

**Made with ❤️ for efficient meeting documentation**
