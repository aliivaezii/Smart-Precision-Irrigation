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


def open_cmd_with_command(title, command, working_dir):
    """Opens a new Command Prompt window and runs the specified command."""
    try:
        full_command = f'start "{title}" cmd /K "cd /d {working_dir} && echo === {title} === && {command}"'
        subprocess.run(full_command, shell=True, check=True)
        print(f"   {title}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"   {title}: {e}")
        return False


def open_powershell_with_command(title, command, working_dir):
    """Opens a new PowerShell window and runs the specified command."""
    try:
        ps_command = f'Set-Location -Path "{working_dir}"; Write-Host "=== {title} ===" -ForegroundColor Green; {command}'
        full_command = f'start powershell -NoExit -Command "{ps_command}"'
        subprocess.run(full_command, shell=True, check=True)
        print(f"   {title}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"   {title}: {e}")
        return False


def get_python_command():
    """Determines the correct Python command to use."""
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


def start_services(python_cmd, include_devices=True, use_powershell=False):
    """Starts all services in separate terminal windows."""
    terminal_type = "PowerShell" if use_powershell else "Command Prompt"
    open_terminal = open_powershell_with_command if use_powershell else open_cmd_with_command
    
    print()
    print("=" * 60)
    print(" Smart Precision Irrigation System")
    print("=" * 60)
    print(f"   Project:  {PROJECT_ROOT}")
    print(f"   Python:   {python_cmd}")
    print(f"   Terminal: {terminal_type}")
    print()
    
    # Start services
    print("Starting Services...")
    print("-" * 40)
    
    for name, script_path, delay in SERVICES:
        full_path = os.path.join(PROJECT_ROOT, script_path).replace("/", "\\")
        
        if not os.path.exists(full_path):
            print(f"    Not found: {script_path}")
            continue
        
        command = f'{python_cmd} "{full_path}"'
        if open_terminal(name, command, PROJECT_ROOT):
            time.sleep(delay)
    
    # Start devices if requested
    if include_devices:
        print()
        print("Starting Device Simulator...")
        print("-" * 40)
        
        name, script_path, args, delay = DEVICE_SIMULATOR
        full_path = os.path.join(PROJECT_ROOT, script_path).replace("/", "\\")
        
        if not os.path.exists(full_path):
            print(f"    Not found: {script_path}")
        else:
            args_str = " ".join(args) if args else ""
            command = f'{python_cmd} "{full_path}" {args_str}'.strip()
            if open_terminal(name, command, PROJECT_ROOT):
                time.sleep(delay)
    
    print()
    print("=" * 60)
    print(" System Started")
    print()
    print("     Endpoints:")
    print("     Catalogue:  http://localhost:8080")
    print("     Devices:    http://localhost:8080/devices")
    print("     Gardens:    http://localhost:8080/gardens")
    print()
    print("    Tips:")
    print("     • The Device Simulator auto-discovers registered devices")
    print("     • POST new devices to /devices - they start automatically!")
    print("     • Run 'python scripts\\windows\\stop.py' to stop all")
    print("=" * 60)
    print()



def main():
    """
    Main function - starts all services.
    
    Usage:
        python scripts\\windows\\start.py              # Start all services + devices
        python scripts\\windows\\start.py --no-devices # Start services only
        python scripts\\windows\\start.py --powershell # Use PowerShell
    """
    # Check platform
    if sys.platform != "win32":
        print("This script is for Windows only.")
        print("For macOS: python scripts/macos/start.py")
        sys.exit(1)
    
    # Check for flags
    include_devices = True
    use_powershell = False
    
    for arg in sys.argv[1:]:
        if arg == "--no-devices":
            include_devices = False
        elif arg == "--powershell":
            use_powershell = True
    
    # Determine Python command
    python_cmd = get_python_command()
    
    # Start the system
    start_services(python_cmd, include_devices=include_devices, use_powershell=use_powershell)


if __name__ == "__main__":
    main()
