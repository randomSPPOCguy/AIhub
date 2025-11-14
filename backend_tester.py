#!/usr/bin/env python3
"""
AI Hub Backend Tester - Terminal Only
Simple script to test backend functionality without any UI
"""
import sys
import os
import json
import asyncio
import subprocess
from pathlib import Path

# Add the backend directory to Python path
backend_dir = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_dir))

# Import the API key generator
from generate_api_key import generate_api_key, is_valid_api_key


class Colors:
    """Terminal colors for better output"""
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'


def print_header(text):
    """Print a styled header"""
    print(f"\n{Colors.BOLD}{Colors.HEADER}{'='*60}{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.HEADER}{text.center(60)}{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.HEADER}{'='*60}{Colors.ENDC}\n")


def print_success(text):
    """Print success message"""
    print(f"{Colors.OKGREEN}✓ {text}{Colors.ENDC}")


def print_error(text):
    """Print error message"""
    print(f"{Colors.FAIL}✗ {text}{Colors.ENDC}")


def print_info(text):
    """Print info message"""
    print(f"{Colors.OKCYAN}→ {text}{Colors.ENDC}")


def test_api_key_generation():
    """Test API key generation"""
    print_header("Testing API Key Generation")
    
    # Generate multiple keys
    keys = []
    for i in range(3):
        key = generate_api_key()
        keys.append(key)
        print_info(f"Generated Key {i+1}: {key}")
        
        # Validate the key
        if is_valid_api_key(key):
            print_success(f"Key {i+1} validation passed")
        else:
            print_error(f"Key {i+1} validation failed")
    
    print()
    print_info("Testing invalid keys...")
    
    # Test invalid keys
    invalid_keys = [
        "invalid-key",
        "jpnohub-",
        "jpnohub-short",
        "",
        "wrongprefix-abcdefghijklmnopqrstuvwxyz123456"
    ]
    
    for invalid_key in invalid_keys:
        if not is_valid_api_key(invalid_key):
            print_success(f"Correctly rejected: '{invalid_key}'")
        else:
            print_error(f"Incorrectly accepted: '{invalid_key}'")
    
    return keys[0]  # Return the first key for later use


def save_api_key_to_env(api_key):
    """Save API key to .env file"""
    print_header("Saving API Key to .env")
    
    env_file = backend_dir / ".env"
    
    # Read existing .env or create new
    env_content = {}
    if env_file.exists():
        with open(env_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    env_content[key.strip()] = value.strip()
    
    # Update with new API key
    env_content['BOT_API_KEY'] = api_key
    
    # Write back to file
    with open(env_file, 'w') as f:
        f.write("# AI Hub Configuration\n\n")
        for key, value in env_content.items():
            f.write(f"{key}={value}\n")
    
    print_success(f"API key saved to {env_file}")
    print_info(f"BOT_API_KEY={api_key}")


def check_dependencies():
    """Check if required dependencies are installed"""
    print_header("Checking Dependencies")
    
    required = [
        "fastapi",
        "uvicorn",
        "pydantic",
        "google.generativeai",
        "openai",
        "anthropic"
    ]
    
    all_installed = True
    for package in required:
        try:
            __import__(package.replace("-", "_"))
            print_success(f"{package} is installed")
        except ImportError:
            print_error(f"{package} is NOT installed")
            all_installed = False
    
    if not all_installed:
        print()
        print_info("Install missing dependencies with:")
        print(f"  cd {backend_dir}")
        print("  pip install -r requirements.txt")
        return False
    
    return True


def test_backend_import():
    """Test importing backend modules"""
    print_header("Testing Backend Imports")
    
    try:
        # Test importing main modules
        from config import settings
        print_success("Config loaded successfully")
        
        from providers.cloud.gemini_provider import GeminiProvider
        print_success("Gemini provider imported")
        
        from providers.cloud.openai_provider import OpenAIProvider
        print_success("OpenAI provider imported")
        
        from providers.cloud.claude_provider import ClaudeProvider
        print_success("Claude provider imported")
        
        return True
    except Exception as e:
        print_error(f"Failed to import: {e}")
        return False


def start_backend_server():
    """Start the FastAPI backend server"""
    print_header("Starting Backend Server")
    
    print_info("Starting FastAPI server on http://localhost:8000")
    print_info("Press Ctrl+C to stop")
    print()
    
    # Change to backend directory
    os.chdir(backend_dir)
    
    # Start uvicorn server
    try:
        subprocess.run([
            sys.executable, "-m", "uvicorn",
            "main:app",
            "--host", "0.0.0.0",
            "--port", "8000",
            "--reload"
        ])
    except KeyboardInterrupt:
        print()
        print_info("Server stopped by user")


def display_menu():
    """Display interactive menu"""
    print_header("AI Hub Backend Tester")
    print("1. Generate and test API keys")
    print("2. Check dependencies")
    print("3. Test backend imports")
    print("4. Start backend server")
    print("5. Do all checks and start server")
    print("6. Exit")
    print()


def main():
    """Main entry point"""
    while True:
        display_menu()
        choice = input(f"{Colors.BOLD}Choose an option (1-6): {Colors.ENDC}").strip()
        
        if choice == "1":
            api_key = test_api_key_generation()
            save_key = input("\nSave this key to .env? (y/n): ").strip().lower()
            if save_key == 'y':
                save_api_key_to_env(api_key)
        
        elif choice == "2":
            check_dependencies()
        
        elif choice == "3":
            test_backend_import()
        
        elif choice == "4":
            start_backend_server()
        
        elif choice == "5":
            # Run all checks
            if check_dependencies():
                if test_backend_import():
                    api_key = test_api_key_generation()
                    save_api_key_to_env(api_key)
                    input("\nPress Enter to start the server...")
                    start_backend_server()
        
        elif choice == "6":
            print_info("Exiting...")
            break
        
        else:
            print_error("Invalid choice. Please try again.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print()
        print_info("Exiting...")
        sys.exit(0)
