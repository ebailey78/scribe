"""Instance management utilities for Scribe."""

import os
import sys
import psutil
from scribe.utils.paths import get_lock_file


def is_process_running(pid):
    """Check if a process with the given PID is currently running.
    
    Args:
        pid (int): Process ID to check.
        
    Returns:
        bool: True if the process is running, False otherwise.
    """
    try:
        # Use psutil for cross-platform process checking
        process = psutil.Process(pid)
        return process.is_running() and process.status() != psutil.STATUS_ZOMBIE
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
        return False


def check_instance_running():
    """Check if another instance of Scribe is already running.
    
    Returns:
        bool: True if another instance is running, False otherwise.
    """
    lock_file = get_lock_file()
    
    if not lock_file.exists():
        return False
        
    try:
        with open(lock_file, 'r') as f:
            pid = int(f.read().strip())
            
        if is_process_running(pid):
            return True
        else:
            # Stale lock file
            try:
                os.remove(lock_file)
            except OSError:
                pass
            return False
            
    except (ValueError, OSError):
        # Invalid lock file content or read error
        return False


def acquire_lock():
    """Acquire the instance lock by writing current PID to lock file.
    
    Returns:
        bool: True if lock acquired, False if failed.
    """
    lock_file = get_lock_file()
    
    try:
        # Ensure directory exists
        lock_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(lock_file, 'w') as f:
            f.write(str(os.getpid()))
        return True
    except OSError:
        return False


def release_lock():
    """Release the instance lock by removing the lock file."""
    lock_file = get_lock_file()
    
    try:
        if lock_file.exists():
            # Only remove if it contains our PID (avoid removing someone else's lock)
            with open(lock_file, 'r') as f:
                pid = int(f.read().strip())
            
            if pid == os.getpid():
                os.remove(lock_file)
    except (ValueError, OSError):
        pass
