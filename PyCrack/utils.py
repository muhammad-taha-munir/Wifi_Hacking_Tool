import logging
import os

def setup_logger():
    """Configures the logger for the application."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )
    return logging.getLogger("PyCrack")

def load_wordlist(filepath):
    """Loads passwords from a wordlist file."""
    if not os.path.exists(filepath):
        return []
    
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            return [line.strip() for line in f if line.strip()]
    except Exception as e:
        print(f"Error loading wordlist: {e}")
        return []
