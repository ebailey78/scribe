"""
Scribe CLI - Main entry point with subcommands

Usage:
    scribe          - Launch the GUI (default)
    scribe gui      - Launch the GUI
    scribe record   - Start CLI recording
"""

import argparse
import threading
import time


def gui_command(args):
    """Launch the GUI."""
    from scribe.utils.instance import check_instance_running
    
    if check_instance_running():
        print("⚠️  Scribe GUI is already running. Please close the existing instance first.")
        return

    if args.blocking:
        from scribe.gui.app_pro import ScribeProGUI
        app = ScribeProGUI()
        app.run()
    else:
        # Launch detached subprocess
        import subprocess
        import sys
        import os
        
        # Use pythonw.exe on Windows to avoid console window
        python_exe = sys.executable
        if sys.platform == "win32":
            pythonw = os.path.join(os.path.dirname(sys.executable), 'pythonw.exe')
            if os.path.exists(pythonw):
                python_exe = pythonw

        cmd = [python_exe, "-m", "scribe.gui.app_pro"]
        
        kwargs = {}
        if sys.platform == "win32":
            # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW
            # 0x00000008 | 0x00000200 | 0x08000000
            kwargs.update(creationflags=0x00000008 | 0x00000200 | 0x08000000)
            
        subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            close_fds=True,
            **kwargs
        )
        print("Scribe GUI launched in background.")


def record_command(args):
    """Start CLI recording."""
    from scribe.core import SessionManager, AudioRecorder, Transcriber
    from scribe.synthesis import MeetingSynthesizer
    from colorama import Fore, Style
    
    print(f"{Fore.MAGENTA}=== Scribe Recording ==={Style.RESET_ALL}")
    
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
        time.sleep(1)
        
        print(f"\n{Fore.CYAN}🧠 Starting AI Synthesis with Qwen3:8b...{Style.RESET_ALL}")
        synthesizer = MeetingSynthesizer(session.base_dir)
        synthesizer.run()
        
        print(f"\n{Fore.GREEN}✅ DONE!{Style.RESET_ALL}")


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Scribe - Real-time audio transcription and meeting synthesis",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # GUI command
    gui_parser = subparsers.add_parser('gui', help='Launch the GUI')
    gui_parser.add_argument('--blocking', action='store_true', help='Run in current terminal (blocking)')
    gui_parser.set_defaults(func=gui_command)
    
    # Record command (CLI mode)
    record_parser = subparsers.add_parser('record', help='Start CLI recording')
    record_parser.add_argument('--manual', action='store_true', 
                              help='Force manual device selection')
    record_parser.set_defaults(func=record_command)
    
    args = parser.parse_args()
    
    # If no command specified, default to GUI
    if not args.command:
        gui_command(args)
    else:
        args.func(args)


if __name__ == "__main__":
    main()
