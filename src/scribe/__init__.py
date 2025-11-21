"""
Scribe - Real-time audio transcription and meeting synthesis tool.

A professional tool for capturing system audio, transcribing it using Whisper,
and generating AI-powered meeting summaries with intelligent segmentation.
"""

__version__ = "1.0.0"
__author__ = "Scribe Team"

# Main exports
from scribe.core import SessionManager, AudioRecorder, Transcriber
from scribe.synthesis import MeetingSynthesizer

__all__ = [
    "SessionManager",
    "AudioRecorder",
    "Transcriber",
    "MeetingSynthesizer",
]
