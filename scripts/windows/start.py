#!/usr/bin/env python3
"""
Smart Precision Irrigation System - Windows Launcher
=====================================================

Automatically starts all system services in separate terminal windows.
Each service runs in its own terminal for easy monitoring and debugging.

Usage:
    python scripts\\windows\\start.py              # Start all services + devices
    python scripts\\windows\\start.py --no-devices # Start services only
    python scripts\\windows\\start.py --powershell # Use PowerShell instead of cmd
    python scripts\\windows\\start.py --help       # Show all options

Requirements:
    - Windows 10/11
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
    ("Status Service", "src/services/status_service/service.py", 1),
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


def open_cmd_with_command(title: str, command: str, working_dir: str) -> bool:
    """
    Opens a new Command Prompt window and runs the specified command.
    
    Args:
        title: Window title for identification
        command: The command to run in the terminal
        working_dir: Working directory for the command
    
    Returns:
        True if successful, False otherwise
    """
    try:
        full_command = f'start "{title}" cmd /K "cd /d {working_dir} && echo === {title} === && {command}"'
        subprocess.run(full_command, shell=True, check=True)
        print(f"  ✅ {title}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"  ❌ {title}: {e}")
        return False


def open_powershell_with_command(title: str, command: str, working_dir: str) -> bool:
    """
    Opens a new PowerShell window and runs the specified command.
    
    Args:
        title: Window title for identification
        command: The command to run in the terminal
        working_dir: Working directory for the command
    
    Returns:
        True if successful, False otherwise
    """
    try:
        ps_command = f'Set-Location -Path "{working_dir}"; Write-Host "=== {title} ===" -ForegroundColor Green; {command}'
        full_command = f'start powershell -NoExit -Command "{ps_command}"'
        subprocess.run(full_command, shell=True, check=True)
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
    venv_path = os.path.join(PROJECT_ROOT, ".venv", "Scripts", "python.exe")
    if os.path.exists(venv_path):
        return f'"{venv_path}"'
    
    # Check for venv (alternative naming)
    venv_path_alt = os.path.join(PROJECT_ROOT, "venv", "Scripts", "python.exe")
    if os.path.exists(venv_path_alt):
        return f'"{venv_path_alt}"'
    
    # Check for python
    try:
        subprocess.run(["python", "--version"], capture_output=True, check=True)
        return "python"
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    
    # Check for py launcher
    try:
        subprocess.run(["py", "--version"], capture_output=True, check=True)
        return "py"
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    
    return "python"


def start_services(python_cmd: str, include_devices: bool = True, use_powershell: bool = False) -> None:
    """
    Starts all services in separate terminal windows.
    
    Args:
        python_cmd: Python executable to use
        include_devices: Whether to start sensor/actuator devices
        use_powershell: Use PowerShell instead of Command Prompt
    """
    terminal_type = "PowerShell" if use_powershell else "Command Prompt"
    open_terminal = open_powershell_with_command if use_powershell else open_cmd_with_command
    
    print()
    print("=" * 60)
    print("🌱 Smart Precision Irrigation System")
    print("=" * 60)
    print(f"  📂 Project:  {PROJECT_ROOT}")
    print(f"  🐍 Python:   {python_cmd}")
    print(f"  💻 Terminal: {terminal_type}")
    print()
    
    # Start services
    print("Starting Services...")
    print("-" * 40)
    
    for name, script_path, delay in SERVICES:
        full_path = os.path.join(PROJECT_ROOT, script_path).replace("/", "\\")
        
        if not os.path.exists(full_path):
            print(f"  ⚠️  Not found: {script_path}")
            continue
        
        command = f'{python_cmd} "{full_path}"'
        if open_terminal(name, command, PROJECT_ROOT):
            time.sleep(delay)
    
    # Start devices if requested
    if include_devices:
        print()
        print("Starting Devices...")
        print("-" * 40)
        
        for name, script_path, args, delay in DEVICES:
            full_path = os.path.join(PROJECT_ROOT, script_path).replace("/", "\\")
            
            if not os.path.exists(full_path):
                print(f"  ⚠️  Not found: {script_path}")
                continue
            
            args_str = " ".join(args)
            command = f'{python_cmd} "{full_path}" {args_str}'
            if open_terminal(name, command, PROJECT_ROOT):
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
    print("     • Run 'python scripts\\windows\\stop.py' to stop all")
    print("=" * 60)
    print()


def main():
    parser = argparse.ArgumentParser(
        description="Start Smart Precision Irrigation System (Windows)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts\\windows\\start.py              Start all services and devices
  python scripts\\windows\\start.py --no-devices Start services only
  python scripts\\windows\\start.py --powershell Use PowerShell terminals
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
    parser.add_argument(
        "--powershell",
        action="store_true",
        help="Use PowerShell instead of Command Prompt"
    )
    
    args = parser.parse_args()
    
    # Check platform
    if sys.platform != "win32":
        print("❌ This script is for Windows only.")
        print("   For macOS: python scripts/macos/start.py")
        sys.exit(1)
    
    # Determine Python command
    python_cmd = args.python if args.python else get_python_command()
    
    # Start the system
    start_services(python_cmd, include_devices=not args.no_devices, use_powershell=args.powershell)


if __name__ == "__main__":
    main()
