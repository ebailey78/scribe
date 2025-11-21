# Scribe 🎙️

A professional real-time system audio transcription tool for Windows with AI-powered meeting synthesis. Features a sleek LCD-style interface, GPU-accelerated transcription, and intelligent audio processing.

## ✨ Features

### 🎨 Professional GUI
- **LCD-Style Interface**: Compact 800x50px horizontal bar with cyan backlit aesthetic
- **Real-Time Waveform**: Animated 60-bar spectrum analyzer showing audio levels
- **Seven-Segment Timer**: Retro digital display with Courier New monospace font
- **Intuitive Controls**: Play/pause/stop buttons with hamburger menu
- **System Tray Integration**: Minimize to tray with green recording indicator
- **Always Visible**: Shows in both taskbar and system tray

### 🎙️ Audio Capture & Transcription
- **Session Management**: Organized folders in `Documents/Scribe/sessions/`
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
   - Edit `src/scribe/synthesis.py` and set `LOGSEQ_GRAPH_PATH` to your Logseq graph directory
   - Example: `LOGSEQ_GRAPH_PATH = r"C:\Users\YourName\Documents\Logseq\YourGraph\pages"`

## 💻 Usage

### GUI Mode (Recommended)

**Launch the app**:
```powershell
scribe
# OR
scribe gui
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

### CLI Mode

**For headless or scripted use**:
```powershell
scribe record
# OR
scribe record --manual
```

1. Select your audio output device from the list (look for `(Loopback)`)
2. Recording starts automatically
3. View real-time transcription in console
4. Press `Ctrl+C` to stop and trigger synthesis
5. Find output in `Documents/Scribe/sessions/{timestamp}/`

## 📁 Output Structure

Your sessions are saved to your Documents folder:
```
Documents/
└── Scribe/
    ├── logs/
    │   └── scribe_2025-11-20.log
    └── sessions/
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

Scribe uses a YAML configuration file located at `Documents/Scribe/config/config.yaml`. This file is automatically created when you first open the settings.

### Accessing Settings
1.  Click the **Settings (Cog)** icon in the app.
2.  Choose **Edit Config (YAML)** to open the configuration file.
3.  Choose **Edit Jargon List** to manage custom vocabulary.
4.  Choose **Edit Context (Markdown)** to provide background information for the AI.

### Configuration Options (`config.yaml`)

```yaml
transcription:
  min_duration: 60          # Minimum chunk duration (seconds)
  max_duration: 90          # Maximum chunk duration (seconds)
  silence_threshold: 0.01   # Volume threshold (lower = more sensitive)
  silence_duration: 0.5     # Seconds of silence required to cut
  max_silent_chunks: 1      # Stop after N silent chunks
  silence_chunk_threshold: 0.005

synthesis:
  ollama_model: "qwen3:8b"  # LLM model to use (must be pulled in Ollama)
  logseq_graph_path: ""     # Path to Logseq pages folder (optional)
```

### Microphone Mixing (optional)
Enable mic+system audio mixing in `config.yaml` to capture your voice even when it is not played through speakers:
```yaml
audio:
  mix_mic: true           # Turn on mic+loopback mixing
  mic_device: null        # Use default mic; set to an exact device name to override
  mic_gain: 1.0           # Adjust mic level if needed
  loopback_gain: 1.0      # Adjust system audio level if needed
```
CLI overrides: `scribe record --mix-mic --mic-device "<name>" --mic-gain 1.2 --loopback-gain 0.8`. If the mic is unavailable, Scribe falls back to loopback-only and continues recording.

### Context Configuration (`context.md`)
You can provide free-form context to help the AI understand your environment. This file is located at `Documents/Scribe/config/context.md`.
Use it to list:
- Team members and roles
- Current project names and descriptions
- Specific acronyms or terminology definitions
- Meeting goals or preferences

### Logseq Integration
To enable Logseq export, set the path in `config.yaml`:
```yaml
synthesis:
  logseq_graph_path: "C:/Users/YourName/Documents/Logseq/pages"
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
├── src/scribe/          # Main package
│   ├── core.py          # SessionManager, AudioRecorder, Transcriber
│   ├── synthesis.py     # MeetingSynthesizer AI logic
│   ├── gui/app_pro.py   # Professional GUI
│   └── utils/           # paths.py, logging.py
├── scripts/             # Launcher scripts
├── pyproject.toml       # Dependencies & Entry Points
└── README.md           # This file
```

### Key Components
- **SessionManager**: Creates and manages session directories
- **AudioRecorder**: WASAPI loopback capture with pause/resume
- **Transcriber**: Whisper transcription with VAD and smart chunking
- **MeetingSynthesizer**: AI-powered summary and note generation

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
