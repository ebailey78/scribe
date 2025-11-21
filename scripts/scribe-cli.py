"""
Scribe CLI Launcher

Launches the command-line interface for Scribe.
"""

import sys
import os
import argparse
import threading
import time

# Add src to path to enable imports (handle both direct run and installed)
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)  # Go up from scripts/ to project root
src_dir = os.path.join(project_root, 'src')
sys.path.insert(0, src_dir)

from scribe.core import SessionManager, AudioRecorder, Transcriber
from scribe.synthesis import MeetingSynthesizer
from colorama import Fore, Style


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
        
        print(f"\n{Fore.GREEN}✅ DONE! Open this in Logseq:{Style.RESET_ALL}")
        print(f"{Fore.CYAN}{session.base_dir}/notes_logseq.md{Style.RESET_ALL}")


if __name__ == "__main__":
    main()
