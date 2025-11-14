#!/usr/bin/env python3
"""
Quick Start - AI Hub Backend
One command to get everything running
"""
import sys
import os
import subprocess
from pathlib import Path

# Colors
GREEN = '\033[92m'
BLUE = '\033[94m'
YELLOW = '\033[93m'
RED = '\033[91m'
BOLD = '\033[1m'
END = '\033[0m'

def print_step(step, total, message):
    """Print a step"""
    print(f"\n{BOLD}{BLUE}[{step}/{total}]{END} {message}")

def print_success(message):
    """Print success"""
    print(f"{GREEN}✓{END} {message}")

def print_error(message):
    """Print error"""
    print(f"{RED}✗{END} {message}")

def print_warning(message):
    """Print warning"""
    print(f"{YELLOW}⚠{END} {message}")

def main():
    """Quick start the backend"""
    
    print(f"\n{BOLD}{BLUE}{'='*60}{END}")
    print(f"{BOLD}{BLUE}AI Hub Backend - Quick Start{END}".center(60 + len(BOLD) + len(END)))
    print(f"{BOLD}{BLUE}{'='*60}{END}\n")
    
    backend_dir = Path(__file__).parent / "backend"
    
    # Step 1: Check Python version
    print_step(1, 5, "Checking Python version...")
    if sys.version_info < (3, 8):
        print_error("Python 3.8 or higher is required")
        sys.exit(1)
    print_success(f"Python {sys.version_info.major}.{sys.version_info.minor}")
    
    # Step 2: Check if backend directory exists
    print_step(2, 5, "Checking backend directory...")
    if not backend_dir.exists():
        print_error(f"Backend directory not found: {backend_dir}")
        sys.exit(1)
    print_success(f"Found: {backend_dir}")
    
    # Step 3: Install dependencies
    print_step(3, 5, "Installing dependencies...")
    print_warning("This may take a few minutes...")
    
    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "-r", "requirements.txt", "--break-system-packages"],
            cwd=backend_dir,
            check=True,
            capture_output=True
        )
        print_success("Dependencies installed")
    except subprocess.CalledProcessError as e:
        print_warning("Some dependencies may have failed to install")
        print_warning("This is often okay - the backend may still work")
    
    # Step 4: Generate API key
    print_step(4, 5, "Generating API key...")
    
    sys.path.insert(0, str(backend_dir))
    from generate_api_key import generate_api_key
    
    api_key = generate_api_key()
    print_success(f"Generated: {api_key}")
    
    # Save to .env
    env_file = backend_dir / ".env"
    env_content = {}
    
    if env_file.exists():
        with open(env_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    env_content[key.strip()] = value.strip()
    
    env_content['BOT_API_KEY'] = api_key
    
    with open(env_file, 'w') as f:
        f.write("# AI Hub Configuration\n")
        f.write(f"# Generated: {api_key}\n\n")
        for key, value in env_content.items():
            f.write(f"{key}={value}\n")
    
    print_success(f"Saved to: {env_file}")
    
    # Step 5: Start server
    print_step(5, 5, "Starting backend server...")
    print()
    print(f"{BOLD}Server will start on: {BLUE}http://localhost:8000{END}")
    print(f"{BOLD}API Docs: {BLUE}http://localhost:8000/docs{END}")
    print(f"{BOLD}Your API Key: {GREEN}{api_key}{END}")
    print()
    print(f"{YELLOW}Press Ctrl+C to stop the server{END}")
    print()
    
    try:
        subprocess.run(
            [sys.executable, "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"],
            cwd=backend_dir
        )
    except KeyboardInterrupt:
        print()
        print_success("Server stopped")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print()
        print_success("Exiting...")
        sys.exit(0)
