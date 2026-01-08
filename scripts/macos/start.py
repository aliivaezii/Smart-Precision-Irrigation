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
import argparse

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

# Device definitions (started after services)
# Format: (name, relative_path, args, delay_after_start)
DEVICES = [
    ("Sensor Node (garden_1/field_1)", "src/devices/sensor_node.py", ["garden_1", "field_1"], 1),
    ("Actuator Node (garden_1/field_1)", "src/devices/actuator_node.py", ["garden_1", "field_1"], 1),
]


def open_terminal_with_command(title: str, command: str, working_dir: str) -> bool:
    """
    Opens a new Terminal window on macOS and runs the specified command.
    
    Args:
        title: Window title for identification
        command: The command to run in the terminal
        working_dir: Working directory for the command
    
    Returns:
        True if successful, False otherwise
    """
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


def get_python_command() -> str:
    """
    Determines the correct Python command to use.
    Checks for virtual environment first, then falls back to system Python.
    """
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


def start_services(python_cmd: str, include_devices: bool = True) -> None:
    """
    Starts all services in separate Terminal windows.
    
    Args:
        python_cmd: Python executable to use
        include_devices: Whether to start sensor/actuator devices
    """
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
        print("Starting Devices...")
        print("-" * 40)
        
        for name, script_path, args, delay in DEVICES:
            full_path = os.path.join(PROJECT_ROOT, script_path)
            
            if not os.path.exists(full_path):
                print(f"  ⚠️  Not found: {script_path}")
                continue
            
            args_str = " ".join(args)
            command = f"{python_cmd} {full_path} {args_str}"
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
    print("     • Close individual windows to stop services")
    print("     • Press Ctrl+C in a terminal to stop that service")
    print("     • Run 'python scripts/macos/stop.py' to stop all")
    print("=" * 60)
    print()


def main():
    parser = argparse.ArgumentParser(
        description="Start Smart Precision Irrigation System (macOS)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/macos/start.py              Start all services and devices
  python scripts/macos/start.py --no-devices Start services only
  python scripts/macos/start.py --python /usr/bin/python3  Use specific Python
        """
    )
    parser.add_argument(
        "--no-devices",
        action="store_true",
        help="Start services only, without sensor/actuator devices"
    )
    parser.add_argument(
        "--python",
        type=str,
        default=None,
        help="Path to Python executable (default: auto-detect)"
    )
    
    args = parser.parse_args()
    
    # Check platform
    if sys.platform != "darwin":
        print("❌ This script is for macOS only.")
        print("   For Windows: python scripts/windows/start.py")
        sys.exit(1)
    
    # Determine Python command
    python_cmd = args.python if args.python else get_python_command()
    
    # Start the system
    start_services(python_cmd, include_devices=not args.no_devices)


if __name__ == "__main__":
    main()
