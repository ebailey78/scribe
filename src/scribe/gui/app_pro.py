import customtkinter as ctk
import threading
import os
import math
import random
from PIL import Image, ImageDraw
import pystray
from pystray import MenuItem as item
import sys
import time

# Import our scribe components from the package
from scribe.core import SessionManager, AudioRecorder, Transcriber
from scribe.synthesis import MeetingSynthesizer
from scribe.utils.paths import get_sessions_dir

class ScribeProGUI:
    def __init__(self):
        # Set appearance mode and color theme
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        
        # Create main window
        self.root = ctk.CTk()
        self.root.title("Scribe — System Audio")  # Moved indicator to titlebar
        
        # Compact window size (shows in taskbar)
        self.root.geometry("800x50")
        self.root.configure(fg_color="#1a1a1a")
        self.root.resizable(False, False)
        
        # Center the window on screen initially
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        x = (screen_width - 800) // 2
        y = (screen_height - 100) // 2
        self.root.geometry(f"800x50+{x}+{y}")
        
        # Set window icon (navigate to project root from src/scribe/gui)
        try:
            # Get project root: go up 3 levels from src/scribe/gui to root
            gui_dir = os.path.dirname(os.path.abspath(__file__))
            scribe_dir = os.path.dirname(gui_dir)  # src/scribe
            src_dir = os.path.dirname(scribe_dir)  # src
            project_root = os.path.dirname(src_dir)  # project root
            icon_path = os.path.join(project_root, "favicon.ico")
            if os.path.exists(icon_path):
                self.root.iconbitmap(icon_path)
        except Exception as e:
            print(f"Could not load icon: {e}")
        
        # State variables
        self.is_recording = False
        self.is_paused = False
        self.session = None
        self.recorder = None
        self.transcriber = None
        self.transcriber_thread = None
        self.final_notes_path = None
        self.recording_start_time = None
        self.timer_running = False
        self.audio_level = 0.0
        self.phase = 0.0
        
        # System tray
        self.tray_icon = None
        
        # Setup UI
        self.setup_ui()
        
        # Start waveform animation
        self.animate_waveform()
        
        # Start system tray icon immediately
        self.start_tray_icon()
        
        # Handle window close
        self.root.protocol("WM_DELETE_WINDOW", self.minimize_to_tray)

    def setup_ui(self):
        # Main horizontal container with breathing room
        self.main_frame = ctk.CTkFrame(self.root, fg_color="#1a1a1a", corner_radius=0)
        self.main_frame.pack(fill="both", expand=True, pady=3)
        
        # Waveform Display (full height restored)
        self.waveform_canvas = ctk.CTkCanvas(
            self.main_frame,
            bg="#111111",
            height=36,  # Restored full height
            width=300,
            highlightthickness=0
        )
        self.waveform_canvas.pack(side="left", fill="both", expand=True, padx=(10, 10))
        
        # Time Display with dark frame (LCD display look)
        timer_frame = ctk.CTkFrame(
            self.main_frame,
            fg_color="#111111",
            corner_radius=4,
            border_width=0
        )
        timer_frame.pack(side="left", padx=10, pady=5)
        
        self.timer_label = ctk.CTkLabel(
            timer_frame,
            text="00:00:00",
            font=("Courier New", 26, "bold"),  # LCD-style font
            text_color="#00d9ff",
            width=140
        )
        self.timer_label.pack(padx=8, pady=4)
        
        # Status label below timer
        self.status_label = ctk.CTkLabel(
            self.main_frame,
            text="Ready",
            font=("Arial", 9),
            text_color="#888888",
            width=80
        )
        self.status_label.pack(side="left", padx=(0, 15))
        
        # Controls - Generate larger, more tactile icons
        self.icon_play = self.create_media_icon("play", size=20, color="#00d9ff")  # Increased from 16
        self.icon_pause = self.create_media_icon("pause", size=18, color="#00d9ff")  # Increased from 14
        self.icon_resume = self.create_media_icon("play", size=18, color="#00d9ff")  # Increased from 14
        self.icon_stop = self.create_media_icon("square", size=20, color="#00d9ff")  # Increased from 16
        self.icon_settings = self.create_media_icon("settings", size=18, color="#00d9ff")  # Increased from 16
        
        # Pause Button
        self.pause_button = ctk.CTkButton(
            self.main_frame,
            text="",
            image=self.icon_pause,
            width=36,
            height=36,
            corner_radius=18,
            fg_color="transparent",
            hover_color="#222222",
            state="disabled",
            command=self.toggle_pause
        )
        self.pause_button.pack(side="left", padx=5)
        
        # Record/Stop Button
        self.record_button = ctk.CTkButton(
            self.main_frame,
            text="",
            image=self.icon_play,
            width=40,
            height=40,
            corner_radius=20,
            fg_color="transparent",
            hover_color="#222222",
            command=self.toggle_recording
        )
        self.record_button.pack(side="left", padx=5)
        
        # Settings Button
        self.settings_button = ctk.CTkButton(
            self.main_frame,
            text="",
            image=self.icon_settings,
            width=36,
            height=36,
            corner_radius=18,
            fg_color="transparent",
            hover_color="#333333",
            command=self.open_settings
        )
        self.settings_button.pack(side="left", padx=5)

        # Progress bar (thin line at bottom)
        self.progress_bar = ctk.CTkProgressBar(
            self.root,
            width=800,
            height=2,
            progress_color="#00d9ff",
            fg_color="#1a1a1a"
        )
        self.progress_bar.place(x=0, y=48)
        self.progress_bar.set(0)

    def create_media_icon(self, shape, size=20, color="white"):
        """Create a PIL image for media controls."""
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        
        if shape == "play":
            points = [(size*0.2, 0), (size*0.2, size), (size, size/2)]
            draw.polygon(points, fill=color)
        elif shape == "pause":
            bar_width = size // 3
            draw.rectangle([0, 0, bar_width, size], fill=color)
            draw.rectangle([size - bar_width, 0, size, size], fill=color)
        elif shape == "square":
            draw.rectangle([0, 0, size, size], fill=color)
        elif shape == "settings":
            # Simple 3-line hamburger menu icon
            line_height = size * 0.1
            line_width = size * 0.6
            x_start = (size - line_width) / 2
            spacing = size * 0.25
            
            # Top line
            draw.rectangle([x_start, spacing, x_start + line_width, spacing + line_height], fill=color)
            # Middle line
            draw.rectangle([x_start, size/2 - line_height/2, x_start + line_width, size/2 + line_height/2], fill=color)
            # Bottom line
            draw.rectangle([x_start, size - spacing - line_height, x_start + line_width, size - spacing], fill=color)
            
        return ctk.CTkImage(light_image=img, dark_image=img, size=(size, size))

    def open_settings(self):
        print("Settings clicked")
        pass

    def animate_waveform(self):
        """Draw animated bar-style waveform."""
        try:
            canvas_width = self.waveform_canvas.winfo_width()
            canvas_height = self.waveform_canvas.winfo_height()
            mid_y = canvas_height / 2
            
            if canvas_width <= 1:
                self.root.after(50, self.animate_waveform)
                return
            
            self.waveform_canvas.delete("all")
            
            # Update audio level
            target_level = 0.0
            if self.transcriber and hasattr(self.transcriber, 'buffer') and len(self.transcriber.buffer) > 0:
                recent_samples = self.transcriber.buffer[-4800:]
                if len(recent_samples) > 0:
                    target_level = min(1.0, max(0.0, abs(recent_samples.max()) * 8))
            
            # Faster attack, slower decay for punchy bars
            if target_level > self.audio_level:
                self.audio_level = self.audio_level * 0.6 + target_level * 0.4
            else:
                self.audio_level = self.audio_level * 0.9 + target_level * 0.1
            
            self.phase += 0.15
            
            # Bar parameters with increased spacing
            num_bars = 60
            bar_width = 3
            gap = 4  # Increased from 2 to 4 for less visual density
            total_width = num_bars * (bar_width + gap)
            start_x = (canvas_width - total_width) / 2
            
            # Draw bars
            for i in range(num_bars):
                x = start_x + i * (bar_width + gap)
                
                if not self.is_recording or self.is_paused:
                    # Flat line of small dots when idle
                    h = 2
                else:
                    # Simulate spectrum with moving sine waves
                    norm_x = (i / num_bars) * 2 - 1
                    window = 1 - norm_x**2
                    
                    # Complex wave pattern
                    wave1 = math.sin(i * 0.2 + self.phase)
                    wave2 = math.sin(i * 0.5 - self.phase * 1.5)
                    wave3 = math.sin(i * 0.1 + self.phase * 0.5)
                    
                    wave_h = (wave1 + wave2 + wave3 + 3) / 6
                    noise = random.uniform(0.9, 1.1)
                    
                    h = max(4, wave_h * 40 * self.audio_level * window * noise)
                
                # Color based on state with dimming for inactive
                if self.is_paused:
                    color = "#444444"
                elif not self.is_recording:
                    color = "#111111"  # Much dimmer when idle (was #222222)
                else:
                    color = "#00d9ff"
                
                # Draw vertical bar centered on mid_y
                self.waveform_canvas.create_line(
                    x, mid_y - h/2,
                    x, mid_y + h/2,
                    fill=color,
                    width=bar_width,
                    capstyle="round"
                )
            
            self.root.after(30, self.animate_waveform)
        
        except Exception as e:
            print(f"Waveform error: {e}")
            self.root.after(100, self.animate_waveform)
    
    def update_timer(self):
        if self.timer_running and self.recording_start_time and not self.is_paused:
            elapsed = int(time.time() - self.recording_start_time)
            hours = elapsed // 3600
            minutes = (elapsed % 3600) // 60
            seconds = elapsed % 60
            self.timer_label.configure(text=f"{hours:02d}:{minutes:02d}:{seconds:02d}")
            self.root.after(1000, self.update_timer)
        elif self.is_paused or self.timer_running:
            self.root.after(1000, self.update_timer)

    def toggle_recording(self):
        if not self.is_recording:
            self.start_recording()
        else:
            self.stop_recording()
    
    def toggle_pause(self):
        if self.is_paused:
            self.resume_recording()
        else:
            self.pause_recording()
    
    def start_recording(self):
        try:
            self.status_label.configure(text="Starting...", text_color="#FFA500")
            self.root.update()
            
            self.session = SessionManager()
            self.recorder = AudioRecorder()
            import soundcard as sc
            mics = sc.all_microphones(include_loopback=True)
            idx, default_mic = self.recorder.find_default_loopback(mics)
            
            if default_mic:
                self.recorder.mic = default_mic
            else:
                for mic in mics:
                    if mic.isloopback:
                        self.recorder.mic = mic
                        break
            
            if not self.recorder.mic:
                print("No Device!")
                return
            
            self.transcriber = Transcriber(
                self.recorder.q, 
                self.recorder.native_sample_rate, 
                self.session,
                auto_stop_callback=self.auto_stop_recording
            )
            
            self.recorder.start_recording()
            
            self.transcriber_thread = threading.Thread(target=self.transcriber.process_audio, daemon=True)
            self.transcriber_thread.start()
            
            self.is_recording = True
            self.recording_start_time = time.time()
            self.timer_running = True
            self.update_timer()
            
            self.record_button.configure(
                image=self.icon_stop
            )
            self.pause_button.configure(state="normal")
            
            self.status_label.configure(text="Recording", text_color="#00d9ff")
            
            if self.tray_icon:
                self.tray_icon.icon = self.create_icon("red", show_recording_indicator=True)
        
        except Exception as e:
            print(f"Recording error: {e}")
    
    def pause_recording(self):
        if not self.is_recording or self.is_paused:
            return
        self.is_paused = True
        self.recorder.pause()
        self.pause_button.configure(image=self.icon_resume)
    
    def resume_recording(self):
        if not self.is_recording or not self.is_paused:
            return
        self.is_paused = False
        self.recorder.resume()
        self.pause_button.configure(image=self.icon_pause)
    
    def stop_recording(self):
        if not self.is_recording:
            return
        
        try:
            self.recorder.stop_recording()
            self.is_recording = False
            self.is_paused = False
            self.timer_running = False
            
            self.timer_label.configure(text="Processing...")
            self.status_label.configure(text="Processing", text_color="#FFA500")
            self.record_button.configure(state="disabled")
            self.pause_button.configure(state="disabled")
            
            self.progress_bar.set(0)
            
            synthesis_thread = threading.Thread(target=self.run_synthesis, daemon=True)
            synthesis_thread.start()
        
        except Exception as e:
            self.record_button.configure(state="normal")
    
    def auto_stop_recording(self):
        print("🔚 Auto-stop triggered from silence detection")
        self.root.after(0, self.stop_recording)
    
    def run_synthesis(self):
        try:
            time.sleep(1)
            self.root.after(0, lambda: self.progress_bar.set(0.2))
            
            synthesizer = MeetingSynthesizer(self.session.base_dir)
            
            transcript_path = os.path.join(self.session.base_dir, "transcript_full.txt")
            if not os.path.exists(transcript_path):
                raise FileNotFoundError("No transcript generated")

            self.root.after(0, lambda: self.progress_bar.set(0.4))
            
            transcript = synthesizer.read_transcript()
            if transcript.strip():
                summary = synthesizer.generate_summary(transcript)
                self.root.after(0, lambda: self.progress_bar.set(0.6))
                
                title = synthesizer.generate_meeting_title(summary)
                
                date_prefix = os.path.basename(self.session.base_dir).split('_')[0]
                final_filename = f"{date_prefix}_{title}.md"
                self.final_notes_path = os.path.join(self.session.base_dir, final_filename)
                
                with open(synthesizer.output_path, "w", encoding="utf-8") as f:
                    f.write(f"# {title.replace('_', ' ')}\n\n")
                    f.write(f"**Session**: {os.path.basename(self.session.base_dir)}\n\n")
                    f.write(summary)
                    f.write("\n\n---\n\n")
                
                self.root.after(0, lambda: self.progress_bar.set(0.8))
                
                blocks = synthesizer.split_into_blocks_with_timestamps(transcript)
                with open(synthesizer.output_path, "a", encoding="utf-8") as f:
                    for i, block_data in enumerate(blocks):
                        detailed = synthesizer.generate_detailed_notes(
                            block_data['text'], i+1, block_data['time_range']
                        )
                        f.write(f"\n## {block_data['time_range']} Discussion Segment\n\n")
                        f.write(detailed)
                        f.write("\n\n")
                
                try:
                    os.rename(synthesizer.output_path, self.final_notes_path)
                except:
                    self.final_notes_path = synthesizer.output_path
                
                synthesizer.export_to_logseq(self.final_notes_path)
            
            self.root.after(0, lambda: self.progress_bar.set(1.0))
            self.root.after(0, self.synthesis_complete)
        
        except Exception as e:
            print(f"Synthesis error: {e}")
            self.root.after(2000, self.reset_ui)
    
    def synthesis_complete(self):
        self.timer_label.configure(text="Complete!")
        self.status_label.configure(text="Complete", text_color="#00ff00")
        
        if self.tray_icon:
            self.tray_icon.icon = self.create_icon("gray", show_recording_indicator=False)
        
        self.record_button.configure(
            image=self.icon_play,
            state="normal"
        )
        
        self.open_notes_file()
    
    def reset_ui(self):
        self.timer_label.configure(text="00:00:00")
        self.status_label.configure(text="Ready", text_color="#888888")
        self.record_button.configure(state="normal")
        self.pause_button.configure(state="disabled")
        self.progress_bar.set(0)
        self.timer_running = False
    
    def open_notes_file(self):
        if self.final_notes_path and os.path.exists(self.final_notes_path):
            os.startfile(self.final_notes_path)
    
    def create_icon(self, color="gray", show_recording_indicator=False):
        # Get project root path
        gui_dir = os.path.dirname(os.path.abspath(__file__))
        scribe_dir = os.path.dirname(gui_dir)
        src_dir = os.path.dirname(scribe_dir)
        project_root = os.path.dirname(src_dir)
        icon_path = os.path.join(project_root, "favicon.ico")
        
        try:
            if os.path.exists(icon_path):
                image = Image.open(icon_path)
                # Add recording indicator if needed
                if show_recording_indicator:
                    draw = ImageDraw.Draw(image)
                    # Draw green circle in bottom-right corner
                    indicator_size = 20
                    margin = 4
                    x = image.width - indicator_size - margin
                    y = image.height - indicator_size - margin
                    draw.ellipse([x, y, x + indicator_size, y + indicator_size], 
                               fill="#00ff00", outline="#ffffff", width=2)
                return image
        except:
            pass
        
        size = 64
        image = Image.new('RGB', (size, size), color)
        draw = ImageDraw.Draw(image)
        border_color = "white" if color == "red" else "darkgray"
        draw.rectangle([0, 0, size-1, size-1], outline=border_color, width=4)
        
        # Add recording indicator if needed
        if show_recording_indicator:
            # Draw green circle in bottom-right corner
            indicator_size = 16
            margin = 4
            x = size - indicator_size - margin
            y = size - indicator_size - margin
            draw.ellipse([x, y, x + indicator_size, y + indicator_size], 
                       fill="#00ff00", outline="#ffffff", width=2)
        
        return image
    
    def start_tray_icon(self):
        """Initialize and start the system tray icon."""
        if not self.tray_icon:
            icon_color = "red" if self.is_recording else "gray"
            icon_image = self.create_icon(icon_color, show_recording_indicator=self.is_recording)
            
            menu = pystray.Menu(
                item('Open Scribe', self.show_window),
                item('Open Sessions Folder', self.open_sessions_folder),
                item(
                    lambda text: "Stop Recording" if self.is_recording else "Start Recording",
                    self.toggle_recording
                ),
                item('Quit', self.quit_app)
            )
            
            # Left-click opens the window
            self.tray_icon = pystray.Icon(
                "Scribe", 
                icon_image, 
                "Scribe Recorder", 
                menu,
                on_activate=lambda icon: self.root.after(0, self.show_window)
            )
            threading.Thread(target=self.tray_icon.run, daemon=True).start()

    def open_sessions_folder(self):
        """Open the sessions directory in file explorer."""
        try:
            sessions_dir = get_sessions_dir()
            if not os.path.exists(sessions_dir):
                os.makedirs(sessions_dir)
            os.startfile(sessions_dir)
        except Exception as e:
            print(f"Error opening sessions folder: {e}")
    
    def minimize_to_tray(self):
        """Minimize window to tray (hide it)."""
        self.root.withdraw()
    
    def show_window(self):
        self.root.deiconify()
        self.root.attributes("-topmost", True)
        self.root.lift()
        self.root.focus_force()
        self.root.attributes("-topmost", False)
    
    def quit_app(self):
        """Quit the application safely."""
        def _quit():
            if self.is_recording:
                self.recorder.stop_recording()
            if self.tray_icon:
                self.tray_icon.stop()
            self.root.quit()
            self.root.destroy()
            
        # Ensure quit runs on main thread
        self.root.after(0, _quit)
    
    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    app = ScribeProGUI()
    app.run()
