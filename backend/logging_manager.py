"""
Logging Manager - Implements a three-tier logging system using loguru
"""
import os
import sys
import json
import time
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
from loguru import logger

# Import from utils to avoid circular import
from utils import get_aihub_dirs

# Get directories
dirs = get_aihub_dirs()
logs_dir = dirs["logs"]

# Ensure logs directory exists
os.makedirs(logs_dir, exist_ok=True)

# Log levels configuration
LOG_LEVELS = {
    "INFO": {
        "name": "INFO",
        "level": 20,
        "color": "<green>",
        "icon": "✅",
        "description": "User-friendly information"
    },
    "DEBUG": {
        "name": "DEBUG", 
        "level": 10,
        "color": "<blue>",
        "icon": "🔵",
        "description": "Developer information"
    },
    "VERBOSE": {
        "name": "VERBOSE",
        "level": 5,
        "color": "<cyan>",
        "icon": "📝",
        "description": "Detailed technical information"
    },
    "WARNING": {
        "name": "WARNING",
        "level": 30,
        "color": "<yellow>",
        "icon": "⚠️",
        "description": "Warnings that require attention"
    },
    "ERROR": {
        "name": "ERROR",
        "level": 40,
        "color": "<red>",
        "icon": "❌",
        "description": "Errors that need fixing"
    }
}

# Add custom log levels to loguru
logger.level("VERBOSE", no=LOG_LEVELS["VERBOSE"]["level"], color=LOG_LEVELS["VERBOSE"]["color"])

# Current log level (default to INFO)
current_log_level = "INFO"

def setup_logging(level: str = "INFO"):
    """
    Set up the logging system with the specified level
    
    Args:
        level: Log level (INFO, DEBUG, VERBOSE)
    """
    global current_log_level
    
    # Validate log level
    if level not in LOG_LEVELS:
        level = "INFO"
    
    current_log_level = level
    min_level = LOG_LEVELS[level]["level"]
    
    # Remove all existing handlers
    logger.remove()
    
    # Console handler (with colors)
    logger.add(
        sys.stderr,
        format="<green>{time:HH:mm:ss}</green> <level>{level.icon}</level> <level>{message}</level>",
        level=min_level,
        colorize=True,
        backtrace=True,
        diagnose=True
    )
    
    # File handler (with rotation)
    log_path = os.path.join(logs_dir, "app.log")
    logger.add(
        log_path,
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} [{level}] [{extra[category]}] {message}",
        level=min_level,
        rotation="10 MB",
        retention="7 days",
        compression="zip",
        backtrace=True,
        diagnose=True,
        enqueue=True
    )
    
    # Log setup completion
    logger.bind(category="app").info(f"Logging system initialized at {level} level")
    return logger

# Helper functions to log with categories
def log_info(message: str, category: str = "app", **kwargs):
    """Log at INFO level with category"""
    logger.bind(category=category).info(message, **kwargs)

def log_debug(message: str, category: str = "app", **kwargs):
    """Log at DEBUG level with category"""
    logger.bind(category=category).debug(message, **kwargs)

def log_verbose(message: str, category: str = "app", **kwargs):
    """Log at VERBOSE level with category"""
    logger.bind(category=category).log("VERBOSE", message, **kwargs)

def log_warning(message: str, category: str = "app", **kwargs):
    """Log at WARNING level with category"""
    logger.bind(category=category).warning(message, **kwargs)

def log_error(message: str, category: str = "app", **kwargs):
    """Log at ERROR level with category"""
    logger.bind(category=category).error(message, **kwargs)

# API call logging (will show in chat)
class APICallLogger:
    """Logger specifically for API calls that should appear in chat"""
    
    def __init__(self):
        self.api_calls = []
        self.last_update_time = time.time()
    
    def log_api_call(self, 
                    bot_name: str, 
                    api_key: str, 
                    request_data: Dict[str, Any], 
                    response_data: Dict[str, Any], 
                    duration_ms: int,
                    tokens: int = 0):
        """
        Log an API call from an external bot
        
        Args:
            bot_name: Name of the bot making the call
            api_key: API key used (will be masked)
            request_data: Request data
            response_data: Response data
            duration_ms: Request duration in milliseconds
            tokens: Number of tokens generated
        """
        # Mask API key
        if api_key:
            if len(api_key) > 10:
                masked_key = f"{api_key[:5]}***{api_key[-3:]}"
            else:
                masked_key = f"***{api_key[-3:]}" if len(api_key) > 3 else "***"
        else:
            masked_key = "none"
        
        # Extract message from request
        message = "No message"
        if request_data and "messages" in request_data:
            messages = request_data["messages"]
            if messages and isinstance(messages, list) and len(messages) > 0:
                last_message = messages[-1]
                if isinstance(last_message, dict) and "content" in last_message:
                    message = last_message["content"]
                elif hasattr(last_message, 'content'):
                    message = last_message.content
                    
                if isinstance(message, str) and len(message) > 50:
                    message = message[:47] + "..."
        
        # Extract response text
        response_text = "No response"
        if response_data:
            if "response" in response_data:
                response_text = str(response_data["response"])
            elif "content" in response_data:
                response_text = str(response_data["content"])
                
            # Truncate long responses
            if isinstance(response_text, str) and len(response_text) > 50:
                response_text = response_text[:47] + "..."
        
        # Create log entry
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "bot_name": bot_name,
            "masked_api_key": masked_key,
            "request": message,
            "response": response_text,
            "duration_ms": duration_ms,
            "tokens": tokens,
        }
        
        # Add to history
        self.api_calls.append(log_entry)
        
        # Keep only the last 100 API calls
        if len(self.api_calls) > 100:
            self.api_calls.pop(0)
        
        # Log to the standard logger at DEBUG level
        log_debug(
            f'API call from bot "{bot_name}"\n'
            f'→ Request: "{message}"\n'
            f'→ Response: "{response_text}"\n'
            f'→ Duration: {duration_ms}ms, Tokens: {tokens}, Key: {masked_key}',
            category="api"
        )
        
        # Also log details at VERBOSE level
        log_verbose(
            f"HTTP API Request from {bot_name}\n"
            f"Headers: X-API-Key: {masked_key}\n"
            f"Body: {json.dumps(request_data, indent=2)}\n"
            f"Response: {json.dumps(response_data, indent=2)}",
            category="api"
        )
        
        return log_entry
    
    def get_recent_calls(self, limit: int = 20):
        """Get recent API calls, newest first"""
        return list(reversed(self.api_calls[-limit:]))

# Initialize API call logger
api_call_logger = APICallLogger()

# Initial setup with default level
setup_logging("INFO")

def get_current_log_level():
    """Get the current log level"""
    return current_log_level

def set_log_level(level: str):
    """Change the log level"""
    if level in LOG_LEVELS:
        setup_logging(level)
        return True
    return False

def get_log_levels():
    """Get information about available log levels"""
    return LOG_LEVELS

