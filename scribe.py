import os
import sys
import argparse

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

import soundcard as sc
import numpy as np
import queue
import threading
import time
import traceback
import soundfile as sf
import requests
import json
import re
import shutil

from datetime import datetime
from colorama import init, Fore, Style
from faster_whisper import WhisperModel
from tqdm import tqdm
import warnings
import scipy.signal

# Suppress pkg_resources deprecation warning from ctranslate2
warnings.filterwarnings("ignore", category=UserWarning, module="ctranslate2")
warnings.filterwarnings("ignore", category=DeprecationWarning)

# Initialize colorama
init(autoreset=True)

# Configuration: Logseq Graph Path
# Set this to your Logseq pages folder, e.g., r"C:\Users\YourName\Logseq\pages"
LOGSEQ_GRAPH_PATH = r"C:\Users\idemr\Logseq\pages"  # Update this path!

class SessionManager:
    def __init__(self):
        self.session_id = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self.base_dir = os.path.join("sessions", self.session_id)
        self.audio_dir = os.path.join(self.base_dir, "audio_chunks")
        self.transcript_raw = os.path.join(self.base_dir, "transcript_full.txt")
        self.transcript_logseq = os.path.join(self.base_dir, "notes_logseq.md")
        
        # Create directories
        os.makedirs(self.audio_dir, exist_ok=True)
        
        print(f"{Fore.MAGENTA}=== Session Started: {self.session_id} ==={Style.RESET_ALL}")
        print(f"{Fore.CYAN}Session Directory: {self.base_dir}{Style.RESET_ALL}")
        print(f"{Fore.CYAN}Audio Storage: {self.audio_dir}{Style.RESET_ALL}")

class AudioRecorder:
    def __init__(self):
        self.q = queue.Queue()
        self.target_sample_rate = 16000
        self.native_sample_rate = 48000 # Default, will be updated
        self.channels = 1
        self.mic = None
        self.running = False

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
        try:
            with self.mic.recorder(samplerate=self.native_sample_rate, channels=self.channels) as recorder:
                print(f"{Fore.GREEN}Recording started at {self.native_sample_rate} Hz...{Style.RESET_ALL}")
                while self.running:
                    data = recorder.record(numframes=4800)
                    self.q.put(data)
        except Exception as e:
            print(f"{Fore.RED}Recording error: {e}{Style.RESET_ALL}")
            traceback.print_exc()
            self.running = False

    def start_recording(self):
        self.running = True
        self.thread = threading.Thread(target=self.record_loop, daemon=True)
        self.thread.start()

    def stop_recording(self):
        self.running = False
        if hasattr(self, 'thread'):
            self.thread.join(timeout=1)

class Transcriber:
    def __init__(self, recorder_queue, native_sample_rate, session_manager):
        self.queue = recorder_queue
        self.model = None
        self.buffer = np.array([], dtype='float32')
        
        # Smart Segmentation Parameters
        self.min_duration = 60  # Don't cut before this (~1 min target)
        self.max_duration = 90  # Force cut if no silence found
        self.silence_threshold = 0.01  # RMS amplitude threshold
        self.silence_duration = 0.25  # How long silence must last
        
        self.native_sample_rate = native_sample_rate
        self.target_sample_rate = 16000
        self.session = session_manager
        self.chunk_counter = 0
        self.load_model()

    def load_model(self):
        print(f"{Fore.CYAN}Loading Whisper model...{Style.RESET_ALL}")
        try:
            # Try CUDA first
            self.model = WhisperModel("small.en", device="cuda", compute_type="float16")
            print(f"{Fore.GREEN}Model loaded on GPU (CUDA).{Style.RESET_ALL}")
        except Exception as e:
            print(f"{Fore.YELLOW}CUDA failed ({e}), falling back to CPU...{Style.RESET_ALL}")
            try:
                self.model = WhisperModel("small.en", device="cpu", compute_type="int8")
                print(f"{Fore.GREEN}Model loaded on CPU.{Style.RESET_ALL}")
            except Exception as e2:
                print(f"{Fore.RED}Critical Error: Could not load model: {e2}{Style.RESET_ALL}")
                sys.exit(1)

    def calculate_rms(self, audio_chunk):
        """Calculate RMS (Root Mean Square) amplitude of audio chunk."""
        return np.sqrt(np.mean(audio_chunk**2))

    def detect_silence(self):
        """Check if the last silence_duration seconds of buffer are silent."""
        silence_samples = int(self.silence_duration * self.native_sample_rate)
        
        if len(self.buffer) < silence_samples:
            return False
        
        tail = self.buffer[-silence_samples:]
        rms = self.calculate_rms(tail)
        return rms < self.silence_threshold

    def process_audio(self):
        print(f"{Fore.CYAN}Transcriber started. Waiting for audio...{Style.RESET_ALL}")
        while True:
            try:
                data = self.queue.get(timeout=1)
                data = data.flatten()
                self.buffer = np.concatenate((self.buffer, data))
                
                current_duration = len(self.buffer) / self.native_sample_rate
                
                # Smart Segmentation Logic
                if current_duration < self.min_duration:
                    # Keep buffering
                    continue
                elif current_duration >= self.min_duration and current_duration < self.max_duration:
                    # Hunt for silence
                    if self.detect_silence():
                        print(f"{Fore.CYAN}[Smart Cut] Silence detected at {current_duration:.1f}s{Style.RESET_ALL}")
                        self.transcribe_buffer()
                else:
                    # Force cut at max_duration
                    print(f"{Fore.YELLOW}[Force Cut] Max duration reached at {current_duration:.1f}s{Style.RESET_ALL}")
                    self.transcribe_buffer()
                    
            except queue.Empty:
                continue
            except Exception as e:
                print(f"{Fore.RED}Error in processing loop: {e}{Style.RESET_ALL}")
                traceback.print_exc()

    def save_audio_chunk(self, audio_data):
        """Save the current audio buffer to a WAV file."""
        filename = os.path.join(self.session.audio_dir, f"chunk_{self.chunk_counter:03d}.wav")
        # soundfile expects float32 in [-1, 1] range, which is what we have
        sf.write(filename, audio_data, self.native_sample_rate)
        self.chunk_counter += 1

    def transcribe_buffer(self):
        if len(self.buffer) == 0:
            return

        max_amp = np.max(np.abs(self.buffer))
        print(f"{Fore.YELLOW}Processing {len(self.buffer)/self.native_sample_rate:.1f}s of audio... (Max Amp: {max_amp:.4f}){Style.RESET_ALL}")

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

class MeetingSynthesizer:
    """Post-processing engine that transforms raw transcripts into structured Logseq notes using Qwen3:8b."""
    
    def __init__(self, session_dir):
        self.session_dir = session_dir
        self.transcript_path = os.path.join(session_dir, "transcript_full.txt")
        self.output_path = os.path.join(session_dir, "notes_logseq.md")
        self.final_path = None  # Will be set after title generation
        self.ollama_url = "http://localhost:11434/api/generate"
        self.model = "qwen3:8b"
        self.system_prompt = "You are an expert technical secretary. Output strictly in Logseq Markdown format."
    
    def read_transcript(self):
        """Load the raw transcript file."""
        try:
            with open(self.transcript_path, "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            print(f"{Fore.RED}Error: transcript_full.txt not found in {self.session_dir}{Style.RESET_ALL}")
            return ""
    
    def extract_timestamps(self, text):
        """Extract all timestamps from text in format [HH:MM:SS]."""
        pattern = r'\[(\d{2}:\d{2}:\d{2})\]'
        matches = re.findall(pattern, text)
        return matches
    
    def split_into_blocks_with_timestamps(self, text, words_per_block=1000):
        """Split transcript into blocks and extract time ranges."""
        lines = text.split('\n')
        blocks = []
        current_block = []
        current_words = 0
        
        for line in lines:
            words_in_line = len(line.split())
            current_block.append(line)
            current_words += words_in_line
            
            if current_words >= words_per_block:
                block_text = '\n'.join(current_block)
                timestamps = self.extract_timestamps(block_text)
                
                if timestamps:
                    start_time = timestamps[0][:5]  # HH:MM
                    end_time = timestamps[-1][:5]  # HH:MM
                    time_range = f"[{start_time} - {end_time}]"
                else:
                    time_range = "[Unknown Time]"
                
                blocks.append({
                    'text': block_text,
                    'time_range': time_range
                })
                current_block = []
                current_words = 0
        
        # Add remaining lines as final block
        if current_block:
            block_text = '\n'.join(current_block)
            timestamps = self.extract_timestamps(block_text)
            
            if timestamps:
                start_time = timestamps[0][:5]
                end_time = timestamps[-1][:5]
                time_range = f"[{start_time} - {end_time}]"
            else:
                time_range = "[Unknown Time]"
            
            blocks.append({
                'text': block_text,
                'time_range': time_range
            })
        
        return blocks
    
    def call_ollama(self, prompt, context=""):
        """Call Ollama API with qwen3:8b model."""
        payload = {
            "model": self.model,
            "prompt": f"{context}\n\n{prompt}",
            "stream": False,
            "system": self.system_prompt
        }
        
        try:
            response = requests.post(self.ollama_url, json=payload, timeout=120)
            response.raise_for_status()
            result = response.json()
            return result.get("response", "")
        except requests.exceptions.RequestException as e:
            print(f"{Fore.RED}Ollama API Error: {e}{Style.RESET_ALL}")
            return f"[ERROR: Could not generate content - {str(e)}]"
    
    def generate_summary(self, transcript):
        """Generate executive summary and participant list."""
        # Truncate to first 8000 tokens (~6000 words) if too large
        words = transcript.split()
        if len(words) > 6000:
            truncated = " ".join(words[:6000])
            context = truncated + "\n\n[... transcript continues ...]"
        else:
            context = transcript
        
        prompt = """Analyze this meeting transcript and provide:

1. **Executive Summary** (2-3 sentences): What was this meeting about?
2. **Participants** (if identifiable from the text, otherwise write "Unknown")
3. **Key Topics Discussed** (3-5 bullet points)

Format the output in clean Logseq Markdown."""
        
        return self.call_ollama(prompt, context)
    
    def generate_meeting_title(self, summary):
        """Generate a short, filename-safe title based on the summary."""
        prompt = """Based on the summary above, generate a short, memorable, filename-safe title (max 5 words). Use underscores. Example: 'Q3_Budget_Review' or 'Project_Alpha_Kickoff'. Output ONLY the title, no explanation."""
        
        title = self.call_ollama(prompt, summary).strip()
        
        # Clean up: remove any quotes, newlines, or invalid filename chars
        title = re.sub(r'[^\w\s-]', '', title)
        title = re.sub(r'\s+', '_', title)
        title = title[:50]  # Limit length
        
        return title if title else "Meeting_Notes"
    
    def generate_detailed_notes(self, block, block_num, time_range):
        """Generate structured notes for a transcript block."""
        prompt = f"""Summarize this segment of a meeting transcript:

Extract and organize:
- **Key Points** (bullet points)
- **Decisions Made** (if any)
- **Action Items** (if any)
- **Technical Terms / Acronyms** (define if possible)

Output in Logseq Markdown format with proper heading levels."""
        
        return self.call_ollama(prompt, block)
    
    def export_to_logseq(self, final_file_path):
        """Copy the final notes to Logseq graph if path exists."""
        if not os.path.exists(LOGSEQ_GRAPH_PATH):
            print(f"{Fore.YELLOW}⚠️  Logseq path not found. Notes saved to local session folder only.{Style.RESET_ALL}")
            print(f"{Fore.YELLOW}   Configure LOGSEQ_GRAPH_PATH in scribe.py{Style.RESET_ALL}")
            return False
        
        try:
            dest = os.path.join(LOGSEQ_GRAPH_PATH, os.path.basename(final_file_path))
            shutil.copy2(final_file_path, dest)
            print(f"{Fore.GREEN}✅ Exported to Logseq: {dest}{Style.RESET_ALL}")
            return True
        except Exception as e:
            print(f"{Fore.RED}Failed to export to Logseq: {e}{Style.RESET_ALL}")
            return False
    
    def run(self):
        """Execute the full synthesis pipeline."""
        print(f"{Fore.CYAN}📖 Reading transcript...{Style.RESET_ALL}")
        transcript = self.read_transcript()
        
        if not transcript.strip():
            print(f"{Fore.RED}Transcript is empty. Skipping synthesis.{Style.RESET_ALL}")
            return
        
        # Step 1: Generate Executive Summary
        print(f"{Fore.CYAN}🧠 Generating Executive Summary with {self.model}...{Style.RESET_ALL}")
        summary = self.generate_summary(transcript)
        
        # Step 2: Generate Meeting Title
        print(f"{Fore.CYAN}📝 Generating meeting title...{Style.RESET_ALL}")
        title = self.generate_meeting_title(summary)
        
        # Construct final filename
        date_prefix = os.path.basename(self.session_dir).split('_')[0]  # Extract date from session_id
        final_filename = f"{date_prefix}_{title}.md"
        self.final_path = os.path.join(self.session_dir, final_filename)
        
        # Write header to file
        with open(self.output_path, "w", encoding="utf-8") as f:
            f.write(f"# {title.replace('_', ' ')}\n\n")
            f.write(f"**Session**: {os.path.basename(self.session_dir)}\n\n")
            f.write(summary)
            f.write("\n\n---\n\n")
        
        # Step 3: Generate Detailed Notes with time-based headers
        blocks = self.split_into_blocks_with_timestamps(transcript)
        print(f"{Fore.CYAN}📚 Processing {len(blocks)} blocks...{Style.RESET_ALL}")
        
        with open(self.output_path, "a", encoding="utf-8") as f:
            for i, block_data in enumerate(tqdm(blocks, desc="Synthesizing blocks", unit="block", ncols=80)):
                detailed = self.generate_detailed_notes(block_data['text'], i+1, block_data['time_range'])
                f.write(f"\n## {block_data['time_range']} Discussion Segment\n\n")
                f.write(detailed)
                f.write("\n\n")
        
        # Step 4: Rename file
        try:
            os.rename(self.output_path, self.final_path)
            print(f"{Fore.GREEN}✅ Synthesis complete!{Style.RESET_ALL}")
        except Exception as e:
            print(f"{Fore.YELLOW}Could not rename file: {e}{Style.RESET_ALL}")
            self.final_path = self.output_path
        
        # Step 5: Export to Logseq
        self.export_to_logseq(self.final_path)
        
        # Final output
        print(f"\n{Fore.GREEN}📄 Final notes:{Style.RESET_ALL}")
        print(f"{Fore.CYAN}{self.final_path}{Style.RESET_ALL}")

def main():
    parser = argparse.ArgumentParser(description="Scribe: Real-time Audio Transcription")
    parser.add_argument("--manual", action="store_true", help="Force manual device selection")
    args = parser.parse_args()

    print(f"{Fore.MAGENTA}=== Scribe Tool (SoundCard) ==={Style.RESET_ALL}")
    
    # Initialize Session
    session = SessionManager()
    
    recorder = AudioRecorder()
    recorder.select_device(manual_mode=args.manual)
    
    transcriber = Transcriber(recorder.q, recorder.native_sample_rate, session)
    
    recorder.start_recording()
    
    transcriber_thread = threading.Thread(target=transcriber.process_audio, daemon=True)
    transcriber_thread.start()
    
    print(f"{Fore.GREEN}System running. Press Ctrl+C to stop.{Style.RESET_ALL}")
    
    try:
        while True:
            time.sleep(0.1)
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}🛑 Recording Stopped. Saving final bits...{Style.RESET_ALL}")
        recorder.stop_recording()
        time.sleep(1)  # Allow transcriber to process remaining buffer
        
        print(f"\n{Fore.CYAN}🧠 Starting AI Synthesis with Qwen3:8b...{Style.RESET_ALL}")
        synthesizer = MeetingSynthesizer(session.base_dir)
        synthesizer.run()
        
        print(f"\n{Fore.GREEN}✅ DONE! Open this in Logseq:{Style.RESET_ALL}\"")
        print(f"{Fore.CYAN}{session.base_dir}/notes_logseq.md{Style.RESET_ALL}")

if __name__ == "__main__":
    main()
