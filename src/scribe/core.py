"""
Core recording and transcription functionality for Scribe.

This module contains the core classes for audio recording, transcription,
and session management.
"""

import os
import sys
import queue
import threading
import time
import traceback
import numpy as np
import soundfile as sf
import scipy.signal
import warnings
from datetime import datetime
from colorama import init, Fore, Style
from faster_whisper import WhisperModel

# Import utilities
from scribe.utils.paths import get_scribe_dir, get_sessions_dir
from scribe.utils.logging import setup_logging

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

# Setup logger
logger = setup_logging()

# Import soundcard after CUDA setup
import soundcard as sc


class SessionManager:
    """Manages recording session directories and files."""
    
    def __init__(self):
        self.session_id = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        
        # Use Documents/Scribe/sessions
        sessions_root = get_sessions_dir()
        
        self.base_dir = str(sessions_root / self.session_id)
        self.audio_dir = os.path.join(self.base_dir, "audio_chunks")
        self.transcript_raw = os.path.join(self.base_dir, "transcript_full.txt")
        self.transcript_logseq = os.path.join(self.base_dir, "notes_logseq.md")
        
        # Create directories
        os.makedirs(self.audio_dir, exist_ok=True)
        
        # Log to file
        logger.info(f"Session Started: {self.session_id}")
        logger.info(f"Session Directory: {self.base_dir}")
        logger.info(f"Audio Storage: {self.audio_dir}")
        
        # Minimal console output
        print(f"{Fore.MAGENTA}=== Session Started: {self.session_id} ==={Style.RESET_ALL}")
        print(f"{Fore.CYAN}Session Directory: {self.base_dir}{Style.RESET_ALL}")
        print(f"{Fore.CYAN}Audio Storage: {self.audio_dir}{Style.RESET_ALL}")


class AudioRecorder:
    """Records system audio using soundcard WASAPI loopback."""
    
    def __init__(self):
        self.q = queue.Queue()
        self.target_sample_rate = 16000
        self.native_sample_rate = 48000  # Default, will be updated
        self.channels = 1
        self.mic = None
        self.running = False
        self.paused = False  # Soft pause state
        
    def pause(self):
        """Pause recording (keeps stream alive)."""
        self.paused = True
    
    def resume(self):
        """Resume recording."""
        self.paused = False

    def find_default_loopback(self, mics):
        """Try to find the loopback device corresponding to the system default speaker."""
        try:
            default_speaker = sc.default_speaker()
            for idx, mic in enumerate(mics):
                if mic.isloopback and default_speaker.name in mic.name:
                    return idx, mic
        except Exception:
            pass
        return None, None

    def select_device(self, manual_mode=False):
        """Select audio device (auto or manual)."""
        print(f"{Fore.CYAN}Searching for Audio Input devices (including Loopback)...{Style.RESET_ALL}")
        try:
            mics = sc.all_microphones(include_loopback=True)
        except Exception as e:
            print(f"{Fore.RED}Error listing devices: {e}{Style.RESET_ALL}")
            sys.exit(1)

        if not mics:
            print(f"{Fore.RED}No devices found.{Style.RESET_ALL}")
            sys.exit(1)

        # Auto-selection logic
        if not manual_mode:
            idx, default_mic = self.find_default_loopback(mics)
            if default_mic:
                print(f"{Fore.GREEN}Auto-selected default device:{Style.RESET_ALL} [{idx}] {default_mic.name}")
                self.mic = default_mic
                return

        print(f"{Fore.GREEN}Found the following devices:{Style.RESET_ALL}")
        for idx, mic in enumerate(mics):
            loopback_str = f"{Fore.YELLOW}(Loopback){Style.RESET_ALL}" if mic.isloopback else ""
            print(f"[{idx}] {mic.name} {loopback_str}")

        while True:
            try:
                selection = int(input(f"{Fore.YELLOW}Select device index [0-{len(mics)-1}]: {Style.RESET_ALL}"))
                if 0 <= selection < len(mics):
                    self.mic = mics[selection]
                    print(f"Selected: {self.mic.name}")
                    break
                else:
                    print("Invalid selection.")
            except ValueError:
                print("Please enter a number.")

    def record_loop(self):
        """Main recording loop."""
        try:
            with self.mic.recorder(samplerate=self.native_sample_rate, channels=self.channels) as recorder:
                print(f"{Fore.GREEN}Recording started at {self.native_sample_rate} Hz...{Style.RESET_ALL}")
                while self.running:
                    data = recorder.record(numframes=4800)
                    # Soft pause: skip processing but keep stream alive
                    if not self.paused:
                        self.q.put(data)
        except Exception as e:
            print(f"{Fore.RED}Recording error: {e}{Style.RESET_ALL}")
            traceback.print_exc()
            self.running = False

    def start_recording(self):
        """Start recording in background thread."""
        self.running = True
        self.thread = threading.Thread(target=self.record_loop, daemon=True)
        self.thread.start()

    def stop_recording(self):
        """Stop recording."""
        self.running = False
        if hasattr(self, 'thread'):
            self.thread.join(timeout=1)


from scribe.utils.config import ConfigManager

class Transcriber:
    """Transcribes audio in real-time using Whisper with smart segmentation."""
    
    def __init__(self, recorder_queue, native_sample_rate, session_manager, auto_stop_callback=None):
        self.queue = recorder_queue
        self.model = None
        self.buffer = np.array([], dtype='float32')
        
        # Load configuration
        self.config_manager = ConfigManager()
        self.vad_config = self.config_manager.config.get("transcription", {})
        
        # Smart Segmentation Parameters (from config)
        self.min_duration = self.vad_config.get("min_duration", 60)
        self.max_duration = self.vad_config.get("max_duration", 90)
        self.silence_threshold = self.vad_config.get("silence_threshold", 0.01)
        self.silence_duration = self.vad_config.get("silence_duration", 0.5)
        
        # Auto-stop detection
        self.auto_stop_callback = auto_stop_callback
        self.silent_chunks_count = 0
        self.silence_chunk_threshold = self.vad_config.get("silence_chunk_threshold", 0.005)
        self.max_silent_chunks = self.vad_config.get("max_silent_chunks", 1)
        
        self.native_sample_rate = native_sample_rate
        self.target_sample_rate = 16000
        self.session = session_manager
        self.chunk_counter = 0
        self.load_model()

    def load_model(self):
        """Load Whisper model (CUDA first, then CPU fallback)."""
        print(f"{Fore.CYAN}Loading Whisper model...{Style.RESET_ALL}")
        try:
            # Try CUDA first
            self.model = WhisperModel("medium.en", device="cuda", compute_type="float16")
            print(f"{Fore.GREEN}Model loaded on GPU (CUDA).{Style.RESET_ALL}")
        except Exception as e:
            print(f"{Fore.YELLOW}CUDA failed ({e}), falling back to CPU...{Style.RESET_ALL}")
            try:
                self.model = WhisperModel("medium.en", device="cpu", compute_type="int8")
                print(f"{Fore.GREEN}Model loaded on CPU.{Style.RESET_ALL}")
            except Exception as e2:
                print(f"{Fore.RED}Critical Error: Could not load model: {e2}{Style.RESET_ALL}")
                sys.exit(1)

    def load_jargon(self):
        """Load custom jargon from config file."""
        try:
            config_dir = get_config_dir()
            jargon_file = config_dir / "jargon.txt"
            
            if not jargon_file.exists():
                return ""
                
            with open(jargon_file, "r", encoding="utf-8") as f:
                lines = [line.strip() for line in f.readlines()]
            
            # Filter comments and empty lines
            terms = [line for line in lines if line and not line.startswith("#")]
            
            if not terms:
                return ""
                
            jargon_string = ", ".join(terms)
            print(f"Loaded jargon: {jargon_string}")
            return f"Context: Business meeting. Custom Vocabulary: {jargon_string}."
            
        except Exception as e:
            print(f"Error loading jargon: {e}")
            return ""

    def transcribe_buffer(self):
        """Transcribe the current audio buffer."""
        if len(self.buffer) == 0:
            return

        max_amp = np.max(np.abs(self.buffer))
        print(f"{Fore.YELLOW}Processing {len(self.buffer)/self.native_sample_rate:.1f}s of audio... (Max Amp: {max_amp:.4f}){Style.RESET_ALL}")

        # Check if entire chunk is silent (meeting ended)
        if max_amp < self.silence_chunk_threshold:
            self.silent_chunks_count += 1
            print(f"{Fore.YELLOW}⚠️  Silent chunk detected ({self.silent_chunks_count}/{self.max_silent_chunks}){Style.RESET_ALL}")
            
            if self.silent_chunks_count >= self.max_silent_chunks:
                print(f"{Fore.CYAN}🔚 Auto-stop: Detected end of meeting (silent audio){Style.RESET_ALL}")
                # Clear buffer and trigger callback
                self.buffer = np.array([], dtype='float32')
                if self.auto_stop_callback:
                    self.auto_stop_callback()
                return
        else:
            # Reset counter if we get audio
            self.silent_chunks_count = 0

        # Save audio chunk before processing
        self.save_audio_chunk(self.buffer)

        audio_to_transcribe = self.buffer
        if self.native_sample_rate != self.target_sample_rate:
            num_samples = int(len(self.buffer) * self.target_sample_rate / self.native_sample_rate)
            audio_to_transcribe = scipy.signal.resample(self.buffer, num_samples)

        initial_prompt = "Healthcare finance meeting. Keywords: EBITDA, HEDIS, EHR, ICD-10, Oncology, Utilization Review, CPT-88305, ROI, YoY."
        
        try:
            segments, info = self.model.transcribe(
                audio_to_transcribe, 
                beam_size=5, 
                initial_prompt=initial_prompt,
                vad_filter=True
            )
            
            text_accumulated = ""
            for segment in segments:
                text_accumulated += segment.text + " "
            
            text_accumulated = text_accumulated.strip()
            
            if text_accumulated:
                timestamp = datetime.now().strftime("%H:%M:%S")
                
                # Dual-Stream Output
                
                # 1. Raw Transcript
                raw_line = f"[{timestamp}] {text_accumulated}\n"
                with open(self.session.transcript_raw, "a", encoding="utf-8") as f:
                    f.write(raw_line)
                    f.flush()
                    os.fsync(f.fileno())

                # 2. Logseq Output
                logseq_line = f"\n## [{timestamp}] {text_accumulated}"
                with open(self.session.transcript_logseq, "a", encoding="utf-8") as f:
                    f.write(logseq_line)
                    f.flush()
                    os.fsync(f.fileno())
                
                print(f"{Fore.BLUE}[{timestamp}]{Style.RESET_ALL} {text_accumulated}")

        except Exception as e:
            print(f"{Fore.RED}Transcription error: {e}{Style.RESET_ALL}")
            traceback.print_exc()
        
        self.buffer = np.array([], dtype='float32')
