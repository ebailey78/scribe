"""
Scribe - Real-time audio transcription and meeting synthesis tool.

A professional tool for capturing system audio, transcribing it using Whisper,
and generating AI-powered meeting summaries with intelligent segmentation.
"""

import warnings

# Suppress pkg_resources deprecation warning from ctranslate2 BEFORE any imports
# Filter by message content as module filtering can be flaky during import
warnings.filterwarnings("ignore", message=".*pkg_resources is deprecated.*")
warnings.filterwarnings("ignore", category=UserWarning, module="ctranslate2")
warnings.filterwarnings("ignore", category=DeprecationWarning)

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
