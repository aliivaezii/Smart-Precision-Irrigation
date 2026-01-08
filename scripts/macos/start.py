#!/usr/bin/env python3
"""
Smart Precision Irrigation System - macOS Launcher
===================================================

Automatically starts all system services in separate Terminal windows.
Each service runs in its own terminal for easy monitoring and debugging.

Usage:
    python scripts/macos/start.py              # Start all services + devices
    python scripts/macos/start.py --no-devices # Start services only
    python scripts/macos/start.py --help       # Show all options

Requirements:
    - macOS with Terminal.app
    - Python 3.9+
    - Virtual environment (optional but recommended)
"""

import subprocess
import time
import os
import sys

# Get the project root directory (two levels up from this script)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "..", ".."))

# Service definitions with startup order and delays
# Format: (name, relative_path, delay_after_start)
SERVICES = [
    ("Catalogue Service", "src/services/catalogue/service.py", 3),
    ("Status Service", "src/services/status/service.py", 1),
    ("Weather Check", "src/services/weather_check/service.py", 1),
    ("Water Manager", "src/services/water_manager/service.py", 1),
    ("Telegram Bot", "src/services/telegram_bot/service.py", 1),
    ("ThingSpeak Adaptor", "src/services/thingspeak_adaptor/service.py", 1),
]

# Device simulator (auto-discovers all registered devices)
DEVICE_SIMULATOR = ("Device Simulator", "src/devices/device_simulator.py", [], 1)


def open_terminal_with_command(title, command, working_dir):
    """Opens a new Terminal window on macOS and runs the specified command."""
    applescript = f'''
    tell application "Terminal"
        activate
        set newTab to do script "cd \\"{working_dir}\\" && echo '=== {title} ===' && {command}"
        set custom title of front window to "{title}"
    end tell
    '''
    
    try:
        subprocess.run(["osascript", "-e", applescript], check=True, capture_output=True)
        print(f"  ✅ {title}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"  ❌ {title}: {e}")
        return False


def get_python_command():
    """Determines the correct Python command to use."""
    # Check for .venv (standard naming)
    venv_path = os.path.join(PROJECT_ROOT, ".venv", "bin", "python")
    if os.path.exists(venv_path):
        return venv_path
    
    # Check for venv (alternative naming)
    venv_path_alt = os.path.join(PROJECT_ROOT, "venv", "bin", "python")
    if os.path.exists(venv_path_alt):
        return venv_path_alt
    
    # Check for python3
    try:
        subprocess.run(["python3", "--version"], capture_output=True, check=True)
        return "python3"
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    
    return "python"


def start_services(python_cmd, include_devices=True):
    """Starts all services in separate Terminal windows."""
    print()
    print("=" * 60)
    print("🌱 Smart Precision Irrigation System")
    print("=" * 60)
    print(f"  📂 Project: {PROJECT_ROOT}")
    print(f"  🐍 Python:  {python_cmd}")
    print()
    
    # Start services
    print("Starting Services...")
    print("-" * 40)
    
    for name, script_path, delay in SERVICES:
        full_path = os.path.join(PROJECT_ROOT, script_path)
        
        if not os.path.exists(full_path):
            print(f"  ⚠️  Not found: {script_path}")
            continue
        
        command = f"{python_cmd} {full_path}"
        if open_terminal_with_command(name, command, PROJECT_ROOT):
            time.sleep(delay)
    
    # Start devices if requested
    if include_devices:
        print()
        print("Starting Device Simulator...")
        print("-" * 40)
        
        name, script_path, args, delay = DEVICE_SIMULATOR
        full_path = os.path.join(PROJECT_ROOT, script_path)
        
        if not os.path.exists(full_path):
            print(f"  ⚠️  Not found: {script_path}")
        else:
            args_str = " ".join(args) if args else ""
            command = f"{python_cmd} {full_path} {args_str}".strip()
            if open_terminal_with_command(name, command, PROJECT_ROOT):
                time.sleep(delay)
    
    print()
    print("=" * 60)
    print("✅ System Started")
    print()
    print("  📋 Endpoints:")
    print("     Catalogue:  http://localhost:8080")
    print("     Devices:    http://localhost:8080/devices")
    print("     Gardens:    http://localhost:8080/gardens")
    print()
    print("  💡 Tips:")
    print("     • The Device Simulator auto-discovers registered devices")
    print("     • POST new devices to /devices - they start automatically!")
    print("     • Run 'python scripts/macos/stop.py' to stop all")
    print("=" * 60)
    print()




def main():
    """
    Main function - starts all services.
    
    Usage:
        python scripts/macos/start.py              # Start all services + devices
        python scripts/macos/start.py --no-devices # Start services only
    """
    # Check platform
    if sys.platform != "darwin":
        print("This script is for macOS only.")
        print("For Windows: python scripts/windows/start.py")
        sys.exit(1)
    
    # Check for --no-devices flag
    include_devices = True
    if len(sys.argv) > 1 and sys.argv[1] == "--no-devices":
        include_devices = False
    
    # Determine Python command
    python_cmd = get_python_command()
    
    # Start the system
    start_services(python_cmd, include_devices=include_devices)


if __name__ == "__main__":
    main()
