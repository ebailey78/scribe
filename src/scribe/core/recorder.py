"""
Audio recording functionality for Scribe.

Handles system audio recording using soundcard WASAPI loopback.
"""

import sys
import queue
import threading
import traceback
from colorama import Fore, Style

# Import soundcard - must be imported after CUDA setup in __init__.py
import soundcard as sc


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
