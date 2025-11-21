"""Logging configuration for Scribe."""

import logging
from datetime import datetime
from scribe.utils.paths import get_logs_dir


def setup_logging():
    """Configure logging to file in Scribe directory.
    
    Returns:
        logging.Logger: Configured logger instance
    """
    log_dir = get_logs_dir()
    log_dir.mkdir(parents=True, exist_ok=True)
    
    log_file = log_dir / f"scribe_{datetime.now().strftime('%Y-%m-%d')}.log"
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()  # Minimal console output
        ]
    )
    return logging.getLogger(__name__)
