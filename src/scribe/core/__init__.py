"""
Core recording and transcription functionality for Scribe.

This package contains the core classes for audio recording, transcription,
and session management.
"""

import os
import sys
import warnings
from colorama import init

# Add NVIDIA cuDNN and cuBLAS to PATH for CUDA support
# This must be done BEFORE importing ctranslate2 or faster_whisper
try:
    import nvidia.cudnn
    import nvidia.cublas
    
    libs = [nvidia.cudnn, nvidia.cublas]
    
    for lib in libs:
        lib_path = list(lib.__path__)[0]
        bin_path = os.path.join(lib_path, 'bin')
        if os.path.exists(bin_path):
            # Add to DLL search path (for Python 3.8+)
            os.add_dll_directory(bin_path)
            # Add to PATH environment variable (for legacy/other dependencies)
            os.environ['PATH'] = bin_path + os.pathsep + os.environ['PATH']
            
except (ImportError, AttributeError, OSError, IndexError):
    pass  # CUDA libraries not available, will fall back to CPU

# Suppress pkg_resources deprecation warning from ctranslate2
warnings.filterwarnings("ignore", category=UserWarning, module="ctranslate2")
warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", message=".*pkg_resources.*")

# Initialize colorama
init(autoreset=True)

# Import soundcard after CUDA setup
import soundcard as sc

# Export core classes
from .session import SessionManager
from .recorder import AudioRecorder
from .transcriber import Transcriber

__all__ = ['SessionManager', 'AudioRecorder', 'Transcriber']
