"""Path utilities for Scribe - manages data directories."""

import os
from pathlib import Path


def get_scribe_dir():
    """Get the Scribe data directory in Documents folder.
    
    Returns:
        Path: Path to the Scribe directory (e.g., ~/Documents/Scribe)
    """
    docs = Path.home() / "Documents"
    scribe_dir = docs / "Scribe"
    return scribe_dir


def get_sessions_dir():
    """Get the sessions directory.
    
    Returns:
        Path: Path to~/Documents/Scribe/sessions/
    """
    return get_scribe_dir() / "sessions"


def get_logs_dir():
    """Get the logs directory.
    
    Returns:
        Path: Path to ~/Documents/Scribe/logs/
    """
    return get_scribe_dir() / "logs"


def get_config_dir():
    """Get the config directory.
    
    Returns:
        Path: Path to ~/Documents/Scribe/config/
    """
    return get_scribe_dir() / "config"


def get_lock_file():
    """Get the lock file path.
    
    Returns:
        Path: Path to ~/Documents/Scribe/.lock
    """
    return get_scribe_dir() / ".lock"
