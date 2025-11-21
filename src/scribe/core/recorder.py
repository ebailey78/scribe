"""
Audio recording functionality for Scribe.

Handles system audio recording using soundcard WASAPI loopback.
"""

import sys
import queue
import threading
import traceback
import logging
import contextlib
from colorama import Fore, Style
import numpy as np

# Import soundcard - must be imported after CUDA setup in __init__.py
import soundcard as sc
from scribe.utils.config import ConfigManager


class AudioRecorder:
    """Records system audio using soundcard WASAPI loopback."""
    
    def __init__(self, mix_mic=None, mic_device=None, mic_gain=None, loopback_gain=None):
        self.q = queue.Queue()
        self.target_sample_rate = 16000
        self.native_sample_rate = 48000  # Default, will be updated
        self.channels = 1
        self.loopback_device = None
        self.mic_device = None
        self.running = False
        self.paused = False  # Soft pause state
        self.latest_level = 0.0  # Track recent audio level for UI
        self.config_manager = ConfigManager()
        audio_config = self.config_manager.config.get("audio", {})
        self.mix_mic = audio_config.get("mix_mic", False) if mix_mic is None else mix_mic
        self.mic_device_name = mic_device if mic_device is not None else audio_config.get("mic_device")
        raw_mic_gain = mic_gain if mic_gain is not None else audio_config.get("mic_gain", 1.0)
        raw_loop_gain = loopback_gain if loopback_gain is not None else audio_config.get("loopback_gain", 1.0)
        self.mic_gain = float(raw_mic_gain or 1.0)
        self.loopback_gain = float(raw_loop_gain or 1.0)
    
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

    def find_default_capture(self, microphones):
        """Select the default (non-loopback) microphone."""
        try:
            default_mic = sc.default_microphone()
            if default_mic:
                for mic in microphones:
                    if not mic.isloopback and mic.name == default_mic.name:
                        return mic
        except Exception:
            pass
        for mic in microphones:
            if not mic.isloopback:
                return mic
        return None

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
                self.loopback_device = default_mic
        if self.loopback_device is None:
            print(f"{Fore.GREEN}Found the following devices:{Style.RESET_ALL}")
            for idx, mic in enumerate(mics):
                loopback_str = f"{Fore.YELLOW}(Loopback){Style.RESET_ALL}" if mic.isloopback else ""
                print(f"[{idx}] {mic.name} {loopback_str}")

            while True:
                try:
                    selection = int(input(f"{Fore.YELLOW}Select device index [0-{len(mics)-1}]: {Style.RESET_ALL}"))
                    if 0 <= selection < len(mics):
                        self.loopback_device = mics[selection]
                        print(f"Selected loopback device: {self.loopback_device.name}")
                        break
                    else:
                        print("Invalid selection.")
                except ValueError:
                    print("Please enter a number.")

        # Mic selection for mixing
        if self.mix_mic:
            selected_mic = None
            if self.mic_device_name:
                for mic in mics:
                    if mic.isloopback:
                        continue
                    if mic.name.lower() == str(self.mic_device_name).lower():
                        selected_mic = mic
                        print(f"{Fore.GREEN}Mic override matched:{Style.RESET_ALL} {mic.name}")
                        break
            if selected_mic is None:
                selected_mic = self.find_default_capture(mics)
                if selected_mic:
                    print(f"{Fore.GREEN}Auto-selected default mic:{Style.RESET_ALL} {selected_mic.name}")
            self.mic_device = selected_mic
            if self.mic_device is None:
                print(f"{Fore.YELLOW}Mic mixing enabled but no microphone found. Falling back to loopback-only.{Style.RESET_ALL}")
                self.mix_mic = False

        # Preserve legacy attribute for downstream callers
        self.mic = self.loopback_device

    def record_loop(self):
        """Main recording loop."""
        try:
            if not self.loopback_device:
                print(f"{Fore.RED}No loopback device selected. Cannot start recording.{Style.RESET_ALL}")
                return

            mic_context = (
                self.mic_device.recorder(samplerate=self.native_sample_rate, channels=self.channels)
                if self.mix_mic and self.mic_device else contextlib.nullcontext(None)
            )

            with self.loopback_device.recorder(samplerate=self.native_sample_rate, channels=self.channels) as loop_recorder:
                with mic_context as mic_recorder:
                    if self.mix_mic and mic_recorder is None:
                        print(f"{Fore.YELLOW}Mic recorder unavailable. Falling back to loopback-only.{Style.RESET_ALL}")
                        self.mix_mic = False

                    print(f"{Fore.GREEN}Recording started at {self.native_sample_rate} Hz...{Style.RESET_ALL}")
                    if self.mix_mic and mic_recorder:
                        print(f"{Fore.GREEN}Mixing loopback ({self.loopback_device.name}) + mic ({self.mic_device.name}).{Style.RESET_ALL}")
                    while self.running:
                        loop_data = loop_recorder.record(numframes=4800)
                        payload = self._to_mono(loop_data)
                        if self.mix_mic and mic_recorder:
                            try:
                                mic_data = mic_recorder.record(numframes=loop_data.shape[0])
                                payload = self._mix_sources(loop_data, mic_data)
                            except Exception as mix_error:
                                logging.warning("Mic stream error, disabling mix: %s", mix_error)
                                self.mix_mic = False
                        # Update latest level for UI display
                        if payload.size > 0:
                            self.latest_level = float(np.max(np.abs(payload)))
                        if not self.paused:
                            self.q.put(payload)
        except Exception as e:
            print(f"{Fore.RED}Recording error: {e}{Style.RESET_ALL}")
            traceback.print_exc()
            self.running = False

    def _to_mono(self, data):
        """Ensure mono float32 data."""
        if data is None:
            return np.array([], dtype="float32")
        if len(data.shape) > 1:
            data = data.mean(axis=1)
        return data.astype("float32", copy=False)

    def _mix_sources(self, loop_data, mic_data):
        """Apply gains and mix loopback + mic safely."""
        loop_mono = self._to_mono(loop_data) * self.loopback_gain
        mic_mono = self._to_mono(mic_data) * self.mic_gain
        if len(loop_mono) == 0:
            return mic_mono
        if len(mic_mono) == 0:
            return loop_mono
        min_len = min(len(loop_mono), len(mic_mono))
        mixed = loop_mono[:min_len] + mic_mono[:min_len]
        # Simple normalization to reduce clipping risk
        mixed = mixed / 2.0
        return np.clip(mixed, -1.0, 1.0)

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
