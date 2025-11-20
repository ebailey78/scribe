# Scribe 🎙️

A real-time system audio transcription tool for Windows, powered by `faster-whisper` and NVIDIA CUDA.

## Features

- **System Audio Capture**: Records audio from any output device (speakers, headphones) using WASAPI Loopback.
- **Real-time Transcription**: Uses OpenAI's Whisper model (via `faster-whisper`) to transcribe speech to text.
- **GPU Acceleration**: Fully optimized for NVIDIA GPUs using CUDA 12 & cuDNN 9.
- **Markdown Output**: Saves transcriptions with timestamps to `meeting_notes.md`.
- **Smart Resampling**: Automatically handles device sample rates (e.g., 48kHz) for Whisper compatibility.

## Prerequisites

- Windows 10/11
- Python 3.12+
- NVIDIA GPU (Recommended for speed)
- [uv](https://github.com/astral-sh/uv) (for dependency management)

## Installation

1. Clone the repository:
   ```powershell
   git clone <your-repo-url>
   cd scribe
   ```

2. Install dependencies:
   ```powershell
   uv sync
   ```

## Usage

1. Run the tool:
   ```powershell
   uv run python scribe.py
   ```

2. Select your audio output device from the list (look for `(Loopback)`).

3. The tool will start recording. Any audio playing through that device (meetings, videos, etc.) will be transcribed.

4. View the output in real-time in the console or open `meeting_notes.md`.

5. Press `Ctrl+C` to stop.

## Troubleshooting

- **CUDA Errors**: Ensure you have the latest NVIDIA drivers installed. The project automatically handles cuDNN DLL paths.
- **No Audio**: Make sure you select the correct Loopback device that matches your active speakers/headphones.

## License

MIT
