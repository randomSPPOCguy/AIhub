"""
Utility functions for AI Hub
"""
import os
from pathlib import Path
from typing import Dict


def get_aihub_dirs() -> Dict[str, Path]:
    """
    Get standard directory paths for the AI Hub app
    
    Returns:
        Dict with paths for base, models, config, logs, and cache directories
    """
    user_home = Path(os.path.expanduser("~"))
    aihub_dir = user_home / ".aihub"
    
    dirs = {
        "base": aihub_dir,
        "models": aihub_dir / "models",
        "config": aihub_dir / "config",
        "logs": aihub_dir / "logs",
        "cache": aihub_dir / "cache",
    }
    
    # Ensure all directories exist
    for dir_path in dirs.values():
        os.makedirs(dir_path, exist_ok=True)
    
    return dirs

