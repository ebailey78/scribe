"""
Session management for Scribe recordings.

Handles creation and management of recording session directories and files.
"""

import os
from datetime import datetime
from colorama import Fore, Style
from scribe.utils.paths import get_sessions_dir
from scribe.utils.logging import setup_logging

# Setup logger
logger = setup_logging()


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
