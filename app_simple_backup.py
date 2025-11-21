import customtkinter as ctk
import threading
import os
from PIL import Image, ImageDraw
import pystray
from pystray import MenuItem as item
import sys

# Import our scribe components
from scribe import SessionManager, AudioRecorder, Transcriber, MeetingSynthesizer

class ScribeGUI:
    def __init__(self):
        # Set appearance mode and color theme
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        
        # Create main window
        self.root = ctk.CTk()
        self.root.title("Scribe - Meeting Recorder")
        self.root.geometry("450x550")
        self.root.resizable(False, False)
        
        # State variables
        self.is_recording = False
        self.session = None
        self.recorder = None
        self.transcriber = None
        self.transcriber_thread = None
        self.final_notes_path = None
        
        # System tray
        self.tray_icon = None
        
        # Setup UI
        self.setup_ui()
        
        # Handle window close
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
    
    def setup_ui(self):
        # Main container with padding
        main_frame = ctk.CTkFrame(self.root, fg_color="transparent")
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Header section
        header_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        header_frame.pack(fill="x", pady=(0, 20))
        
        # Title with icon
        title_label = ctk.CTkLabel(
            header_frame,
            text="🎙️  SCRIBE",
            font=("Segoe UI", 28, "bold"),
            text_color="#4A9EFF"
        )
        title_label.pack()
        
        subtitle_label = ctk.CTkLabel(
            header_frame,
            text="AI-Powered Meeting Transcription",
            font=("Segoe UI", 11),
            text_color="gray"
        )
        subtitle_label.pack(pady=(2, 0))
        
        # Status indicator with circular dot
        status_frame = ctk.CTkFrame(main_frame, fg_color="#1a1a1a", corner_radius=15)
        status_frame.pack(fill="x", pady=(0, 15))
        
        status_inner = ctk.CTkFrame(status_frame, fg_color="transparent")
        status_inner.pack(pady=15)
        
        self.status_dot = ctk.CTkLabel(
            status_inner,
            text="⚫",
            font=("Arial", 16)
        )
        self.status_dot.pack(side="left", padx=(0, 10))
        
        self.status_label = ctk.CTkLabel(
            status_inner,
            text="Ready",
            font=("Segoe UI", 16, "bold")
        )
        self.status_label.pack(side="left")
        
        # Session info
        self.session_label = ctk.CTkLabel(
            status_frame,
            text="",
            font=("Segoe UI", 10),
            text_color="#666666"
        )
        self.session_label.pack(pady=(0, 10))
        
        # Stats panel (hidden initially)
        self.stats_frame = ctk.CTkFrame(main_frame, fg_color="#1a1a1a", corner_radius=15)
        
        stats_title = ctk.CTkLabel(
            self.stats_frame,
            text="📊 Recording Statistics",
            font=("Segoe UI", 12, "bold")
        )
        stats_title.pack(pady=(15, 10))
        
        # Create grid for stats
        stats_grid = ctk.CTkFrame(self.stats_frame, fg_color="transparent")
        stats_grid.pack(pady=(0, 15), padx=20)
        
        # Recording time
        time_frame = ctk.CTkFrame(stats_grid, fg_color="#252525", corner_radius=10)
        time_frame.grid(row=0, column=0, padx=5, pady=5, sticky="ew")
        
        ctk.CTkLabel(
            time_frame,
            text="⏱️ Duration",
            font=("Segoe UI", 10),
            text_color="gray"
        ).pack(pady=(8, 0))
        
        self.time_label = ctk.CTkLabel(
            time_frame,
            text="00:00:00",
            font=("Segoe UI", 18, "bold"),
            text_color="#4A9EFF"
        )
        self.time_label.pack(pady=(2, 8))
        
        # Chunks processed
        chunks_frame = ctk.CTkFrame(stats_grid, fg_color="#252525", corner_radius=10)
        chunks_frame.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        
        ctk.CTkLabel(
            chunks_frame,
            text="📦 Chunks",
            font=("Segoe UI", 10),
            text_color="gray"
        ).pack(pady=(8, 0))
        
        self.chunks_label = ctk.CTkLabel(
            chunks_frame,
            text="0",
            font=("Segoe UI", 18, "bold"),
            text_color="#4A9EFF"
        )
        self.chunks_label.pack(pady=(2, 8))
        
        stats_grid.columnconfigure(0, weight=1)
        stats_grid.columnconfigure(1, weight=1)
        
        # Control button
        self.control_button = ctk.CTkButton(
            main_frame,
            text="START RECORDING",
            command=self.toggle_recording,
            width=250,
            height=55,
            font=("Segoe UI", 15, "bold"),
            fg_color="#28a745",
            hover_color="#218838",
            corner_radius=12
        )
        self.control_button.pack(pady=15)
        
        # Progress section (hidden initially)
        self.progress_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        
        self.progress_label = ctk.CTkLabel(
            self.progress_frame,
            text="",
            font=("Segoe UI", 11),
            text_color="gray"
        )
        self.progress_label.pack(pady=(0, 8))
        
        self.progress_bar = ctk.CTkProgressBar(
            self.progress_frame,
            width=300,
            height=8,
            corner_radius=4
        )
        self.progress_bar.pack()
        self.progress_bar.set(0)
        
        # Open file button (hidden initially)
        self.open_button = ctk.CTkButton(
            main_frame,
            text="📄 Open Notes in Logseq",
            command=self.open_notes_file,
            width=220,
            height=45,
            font=("Segoe UI", 13),
            fg_color="#007bff",
            hover_color="#0056b3",
            corner_radius=10
        )
        
        # Minimize to tray button
        minimize_button = ctk.CTkButton(
            main_frame,
            text="Minimize to Tray",
            command=self.minimize_to_tray,
            width=140,
            height=32,
            font=("Segoe UI", 10),
            fg_color="#404040",
            hover_color="#505050",
            corner_radius=8,
            border_width=1,
            border_color="#606060"
        )
        minimize_button.pack(side="bottom", pady=(10, 0))
        
        # Initialize stats tracking
        self.recording_start_time = None
        self.chunks_processed = 0
        self.timer_running = False
    
    def toggle_recording(self):
        if not self.is_recording:
            self.start_recording()
        else:
            self.stop_recording()
    
    def start_recording(self):
        """Start the recording session."""
        try:
            # Create session
            self.session = SessionManager()
            self.session_label.configure(text=f"Session: {self.session.session_id}")
            
            # Create recorder and find default device
            self.recorder = AudioRecorder()
            mics = __import__('soundcard').all_microphones(include_loopback=True)
            idx, default_mic = self.recorder.find_default_loopback(mics)
            
            if default_mic:
                self.recorder.mic = default_mic
                print(f"Auto-selected: {default_mic.name}")
            else:
                # Fallback to first loopback device
                for mic in mics:
                    if mic.isloopback:
                        self.recorder.mic = mic
                        break
            
            if not self.recorder.mic:
                self.update_status("❌ No loopback device found!")
                return
            
            # Create transcriber with auto-stop callback
            self.transcriber = Transcriber(
                self.recorder.q, 
                self.recorder.native_sample_rate, 
                self.session,
                auto_stop_callback=self.auto_stop_recording
            )
            
            # Start recording
            self.recorder.start_recording()
            
            # Start transcriber in thread
            self.transcriber_thread = threading.Thread(target=self.transcriber.process_audio, daemon=True)
            self.transcriber_thread.start()
            
            # Update UI
            self.is_recording = True
            self.update_status("🔴 Recording", dot="🔴")
            self.control_button.configure(
                text="STOP RECORDING",
                fg_color="#dc3545",
                hover_color="#c82333"
            )
            
            # Show stats panel and start timer
            self.stats_frame.pack(fill="x", pady=(0, 15))
            self.recording_start_time = __import__('time').time()
            self.chunks_processed = 0
            self.timer_running = True
            self.update_timer()
            
            # Update tray icon if exists
            if self.tray_icon:
                self.tray_icon.icon = self.create_icon("red")
        
        except Exception as e:
            self.update_status(f"❌ Error: {str(e)}")
            print(f"Recording error: {e}")
    
    def update_timer(self):
        """Update the recording timer every second."""
        if self.timer_running and self.recording_start_time:
            elapsed = int(__import__('time').time() - self.recording_start_time)
            hours = elapsed // 3600
            minutes = (elapsed % 3600) // 60
            seconds = elapsed % 60
            
            self.time_label.configure(text=f"{hours:02d}:{minutes:02d}:{seconds:02d}")
            
            # Also update chunks count
            if self.transcriber:
                self.chunks_label.configure(text=str(self.transcriber.chunk_counter))
            
            # Schedule next update
            self.root.after(1000, self.update_timer)
    
    def stop_recording(self):
        """Stop recording and start synthesis."""
        if not self.is_recording:
            return
        
        try:
            # Stop recording and timer
            self.recorder.stop_recording()
            self.is_recording = False
            self.timer_running = False
            
            # Update UI
            self.update_status("🧠 Synthesizing...", dot="🟡")
            self.control_button.configure(state="disabled")
            
            # Hide stats, show progress
            self.stats_frame.pack_forget()
            self.progress_frame.pack(pady=15)
            self.progress_bar.set(0)
            self.progress_label.configure(text="Preparing synthesis...")
            
            # Start synthesis in separate thread
            synthesis_thread = threading.Thread(target=self.run_synthesis, daemon=True)
            synthesis_thread.start()
        
        except Exception as e:
            self.update_status(f"❌ Error: {str(e)}")
            self.control_button.configure(state="normal")
    
    def auto_stop_recording(self):
        """Auto-stop triggered by silence detection."""
        print("🔚 Auto-stop triggered from silence detection")
        # Use root.after to safely call stop_recording from the main thread
        self.root.after(0, self.stop_recording)
    
    def run_synthesis(self):
        """Run the AI synthesis (in background thread)."""
        try:
            # Small delay to let transcriber finish
            import time
            time.sleep(1)
            
            # Update progress
            self.root.after(0, lambda: self.progress_bar.set(0.2))
            self.root.after(0, lambda: self.progress_label.configure(text="Reading transcript..."))
            
            # Create synthesizer
            synthesizer = MeetingSynthesizer(self.session.base_dir)
            
            # Update progress
            self.root.after(0, lambda: self.progress_bar.set(0.4))
            self.root.after(0, lambda: self.progress_label.configure(text="Generating summary..."))
            
            # Run synthesis
            transcript = synthesizer.read_transcript()
            if transcript.strip():
                summary = synthesizer.generate_summary(transcript)
                
                self.root.after(0, lambda: self.progress_bar.set(0.6))
                self.root.after(0, lambda: self.progress_label.configure(text="Creating title..."))
                
                title = synthesizer.generate_meeting_title(summary)
                
                # Create file
                date_prefix = os.path.basename(self.session.base_dir).split('_')[0]
                final_filename = f"{date_prefix}_{title}.md"
                self.final_notes_path = os.path.join(self.session.base_dir, final_filename)
                
                # Write header
                with open(synthesizer.output_path, "w", encoding="utf-8") as f:
                    f.write(f"# {title.replace('_', ' ')}\n\n")
                    f.write(f"**Session**: {os.path.basename(self.session.base_dir)}\n\n")
                    f.write(summary)
                    f.write("\n\n---\n\n")
                
                self.root.after(0, lambda: self.progress_bar.set(0.8))
                self.root.after(0, lambda: self.progress_label.configure(text="Processing blocks..."))
                
                # Generate detailed notes
                blocks = synthesizer.split_into_blocks_with_timestamps(transcript)
                with open(synthesizer.output_path, "a", encoding="utf-8") as f:
                    for i, block_data in enumerate(blocks):
                        detailed = synthesizer.generate_detailed_notes(
                            block_data['text'], i+1, block_data['time_range']
                        )
                        f.write(f"\n## {block_data['time_range']} Discussion Segment\n\n")
                        f.write(detailed)
                        f.write("\n\n")
                
                # Rename file
                try:
                    os.rename(synthesizer.output_path, self.final_notes_path)
                except:
                    self.final_notes_path = synthesizer.output_path
                
                # Export to Logseq
                synthesizer.export_to_logseq(self.final_notes_path)
            
            # Complete
            self.root.after(0, lambda: self.progress_bar.set(1.0))
            self.root.after(0, self.synthesis_complete)
        
        except Exception as e:
        
        # Add a border
        border_color = "white" if color == "red" else "darkgray"
        draw.rectangle([0, 0, size-1, size-1], outline=border_color, width=4)
        
        return image
    
    def minimize_to_tray(self):
        """Minimize window to system tray."""
        self.root.withdraw()
        
        if not self.tray_icon:
            icon_color = "red" if self.is_recording else "gray"
            icon_image = self.create_icon(icon_color)
            
            menu = pystray.Menu(
                item('Open', self.show_window),
                item('Start/Stop', self.toggle_recording),
                item('Exit', self.quit_app)
            )
            
            self.tray_icon = pystray.Icon("Scribe", icon_image, "Scribe Recorder", menu)
            
            # Run tray icon in separate thread
            threading.Thread(target=self.tray_icon.run, daemon=True).start()
    
    def show_window(self):
        """Show the window from system tray."""
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()
    
    def on_closing(self):
        """Handle window close event."""
        if self.is_recording:
            # Minimize to tray instead of closing
            self.minimize_to_tray()
        else:
            self.quit_app()
    
    def quit_app(self):
        """Quit the application."""
        if self.is_recording:
            self.recorder.stop_recording()
        
        if self.tray_icon:
            self.tray_icon.stop()
        
        self.root.quit()
        sys.exit(0)
    
    def run(self):
        """Start the GUI application."""
        self.root.mainloop()

if __name__ == "__main__":
    app = ScribeGUI()
    app.run()
