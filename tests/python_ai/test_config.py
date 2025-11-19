#!/usr/bin/env python3
"""Test script to verify that Python ONNX server correctly reads settings from config.env."""

import os
import sys
import pathlib
import dotenv

def colorize(text, color_code):
    """Add color to console output."""
    return f"\033[{color_code}m{text}\033[0m"

def green(text):
    """Make text green."""
    return colorize(text, "32")

def red(text):
    """Make text red."""
    return colorize(text, "31")

def yellow(text):
    """Make text yellow."""
    return colorize(text, "33")

def blue(text):
    """Make text blue."""
    return colorize(text, "34")

# Try to load config from parent directory
script_dir = pathlib.Path(__file__).parent
config_path = script_dir.parent.parent / "config.env"

print(f"\n{blue('=== Python ONNX Server Configuration Test ===')}\\n")
print(f"Looking for config file: {config_path}")

if config_path.exists():
    dotenv.load_dotenv(config_path)
    print(f"{green('✓')} Loaded configuration from {config_path}")
else:
    fallback_path = script_dir.parent / ".env"
    print(f"{yellow('!')} Config not found, looking for fallback: {fallback_path}")
    if fallback_path.exists():
        dotenv.load_dotenv(fallback_path)
        print(f"{yellow('✓')} Loaded configuration from fallback {fallback_path}")
    else:
        print(f"{red('✗')} No configuration file found")
        sys.exit(1)

# Define expected configuration settings
expected_settings = {
    "Python ONNX Service": [
        "PYTHON_AI_HOST",
        "PYTHON_AI_PORT",
        "PYTHON_MODEL_ROOT",
        "PYTHON_AI_BASE"
    ],
    "Local Model Settings": [
        "LOCAL_MODEL_NAME",
        "LOCAL_MODEL_KIND",
        "LOCAL_MODEL_URL",
        "LOCAL_MODEL_ONNX_PATH",
    ]
}

# Check all settings
total_settings = 0
defined_settings = 0

for category, settings in expected_settings.items():
    print(f"\n{blue(f'## {category}')}")
    for setting in settings:
        total_settings += 1
        value = os.getenv(setting)
        is_defined = value is not None

        if is_defined:
            defined_settings += 1
            print(f"{green('✓')} {setting} = {value}")
        else:
            print(f"{red('✗')} {setting} is not defined")

# Summary
print(f"\n{blue('=== Summary ===')}");
print(f"Total settings: {total_settings}")
print(f"Defined settings: {defined_settings}")
print(f"Missing settings: {total_settings - defined_settings}")

success_rate = round((defined_settings / total_settings) * 100)
print(f"Configuration success rate: {success_rate}%")

if success_rate == 100:
    print(f"\n{green('✓')} All Python ONNX server settings are defined!")
else:
    print(f"\n{yellow('!')} Some Python ONNX server settings are missing. Check the results above.")

print(f"\n{blue('=== End of Test ===')}\\n")