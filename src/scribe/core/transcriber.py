"""
Audio transcription functionality for Scribe.

Handles real-time audio transcription using Whisper with smart segmentation.
"""

import os
import sys
import time
import logging
import traceback
import numpy as np
import soundfile as sf
import scipy.signal
from datetime import datetime
from colorama import Fore, Style
from faster_whisper import WhisperModel

from scribe.utils.config import ConfigManager
from scribe.utils.paths import get_config_dir


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


    def save_audio_chunk(self, audio_data):
        """Save raw audio chunk to disk for debugging/backup purposes."""
        try:
            self.chunk_counter += 1
            chunk_filename = f"chunk_{self.chunk_counter:04d}.wav"
            chunk_path = os.path.join(self.session.audio_dir, chunk_filename)
            
            # Save as WAV file
            sf.write(chunk_path, audio_data, self.native_sample_rate)
            logging.debug(f"Saved audio chunk: {chunk_filename}")
        except Exception as e:
            logging.error(f"Error saving audio chunk: {e}")

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

        # Load custom jargon for Whisper prompt
        initial_prompt = self.load_jargon()
        if not initial_prompt:
            # Fallback to simple prompt if no jargon configured
            initial_prompt = "Meeting transcript."
        
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

    def process_audio(self):
        """Main processing loop for transcription with smart pause detection."""
        logging.info("Transcriber.process_audio loop started")
        
        while True:
            try:
                # Move data from queue to buffer
                while not self.queue.empty():
                    data = self.queue.get_nowait()
                    # Ensure data is flat
                    if len(data.shape) > 1:
                        data = data.flatten()
                    self.buffer = np.concatenate((self.buffer, data))
                
                # Calculate current buffer duration
                buffer_duration = len(self.buffer) / self.native_sample_rate
                
                # Smart segmentation logic
                if buffer_duration >= self.min_duration:
                    # We have minimum duration, now check for silence or max duration
                    
                    # Force transcription if we've reached max duration
                    if buffer_duration >= self.max_duration:
                        logging.info(f"Max duration ({self.max_duration}s) reached, forcing transcription")
                        self.transcribe_buffer()
                    else:
                        # Look for silence in recent audio to find natural pause
                        # Check last N seconds of audio for silence
                        silence_check_samples = int(self.silence_duration * self.native_sample_rate)
                        
                        if len(self.buffer) >= silence_check_samples:
                            recent_audio = self.buffer[-silence_check_samples:]
                            recent_max_amp = np.max(np.abs(recent_audio))
                            
                            # If recent audio is silent (below threshold), transcribe now
                            if recent_max_amp < self.silence_threshold:
                                logging.info(f"Silence detected after {buffer_duration:.1f}s, transcribing at natural pause")
                                self.transcribe_buffer()
                
                time.sleep(0.1)
                
            except Exception as e:
                logging.error(f"Error in process_audio loop: {e}")
                traceback.print_exc()
                time.sleep(1)
