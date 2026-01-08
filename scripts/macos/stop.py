#!/usr/bin/env python3
"""
Smart Precision Irrigation System - macOS Stop Script
======================================================

Stops all running Python services by finding and terminating
processes that match the service script names.

Usage:
    python scripts/macos/stop.py         # Stop with confirmation
    python scripts/macos/stop.py --force # Stop without confirmation
    python scripts/macos/stop.py --force # Stop without asking
"""

import subprocess
import sys

# Service script names to look for
SERVICE_PATTERNS = [
    "catalogue/service.py",
    "weather_check/service.py",
    "water_manager/service.py",
    "telegram_bot/service.py",
    "thingspeak_adaptor/service.py",
    "status/service.py",
    "device_simulator.py",
    "sensor_node.py",
    "actuator_node.py",
]


def find_service_processes():
    """
    Finds all running Python processes that match our service scripts.
    Returns a list of tuples: (pid, command_line)
    """
    processes = []
    
    try:
        result = subprocess.run(
            ["ps", "aux"],
            capture_output=True,
            text=True,
            check=True
        )
        
        for line in result.stdout.split("\n"):
            if "python" in line.lower():
                for pattern in SERVICE_PATTERNS:
                    if pattern in line:
                        parts = line.split()
                        if len(parts) >= 2:
                            pid = parts[1]
                            processes.append((pid, line.strip()))
                        break
    
    except subprocess.CalledProcessError as e:
        print(f"Error finding processes: {e}")
    
    return processes


def stop_processes(processes, force=False):
    """
    Stops the given processes.
    processes: List of (pid, command_line) tuples
        force: If True, skip confirmation
    """
    if not processes:
        print()
        print("✅ No Smart Irrigation services are currently running.")
        print()
        return
    
    print()
    print("=" * 60)
    print("🌱 Smart Precision Irrigation System - Stop")
    print("=" * 60)
    print()
    print(f"Found {len(processes)} running service(s):")
    print("-" * 60)
    
    for pid, cmd in processes:
        # Extract script name for cleaner display
        for pattern in SERVICE_PATTERNS:
            if pattern in cmd:
                print(f"  PID {pid}: {pattern}")
                break
    
    print("-" * 60)
    print()
    
    if not force:
        response = input("Stop all services? [y/N]: ").strip().lower()
        if response != 'y':
            print("Cancelled.")
            return
    
    print()
    print("Stopping services...")
    
    stopped = 0
    failed = 0
    
    for pid, _ in processes:
        try:
            subprocess.run(["kill", pid], check=True, capture_output=True)
            stopped += 1
        except subprocess.CalledProcessError:
            try:
                subprocess.run(["kill", "-9", pid], check=True, capture_output=True)
                stopped += 1
            except subprocess.CalledProcessError:
                failed += 1
    
    print()
    print("=" * 60)
    if stopped > 0:
        print(f"✅ Stopped {stopped} service(s)")
    if failed > 0:
        print(f"❌ Failed to stop {failed} service(s)")
    print("=" * 60)
    print()




def main():
    """
    Main function - stops all services.
    
    Usage:
        python scripts/macos/stop.py         # Stop with confirmation
        python scripts/macos/stop.py --force # Stop without confirmation
    """
    # Check platform
    if sys.platform != "darwin":
        print("This script is for macOS only.")
        print("For Windows: python scripts/windows/stop.py")
        sys.exit(1)
    
    # Check for --force flag
    force = False
    if len(sys.argv) > 1 and sys.argv[1] in ["--force", "-f"]:
        force = True
    
    # Find and stop processes
    processes = find_service_processes()
    stop_processes(processes, force=force)


if __name__ == "__main__":
    main()
