#!/usr/bin/env python3
"""
Smart Precision Irrigation System - Windows Stop Script
========================================================

Stops all running Python services by finding and terminating
processes that match the service script names.

Usage:
    python scripts\\windows\\stop.py         # Stop with confirmation
    python scripts\\windows\\stop.py --force # Stop without confirmation
    python scripts\\windows\\stop.py --help  # Show all options
"""

import subprocess
import sys
import argparse
from typing import List, Tuple

# Service script names to look for
SERVICE_PATTERNS = [
    "catalogue\\service.py",
    "weather_check\\service.py",
    "water_manager\\service.py",
    "telegram_bot\\service.py",
    "thingspeak_adaptor\\service.py",
    "status\service.py",
    "sensor_node.py",
    "actuator_node.py",
]


def find_service_processes() -> List[Tuple[str, str]]:
    """
    Finds all running Python processes that match our service scripts.
    
    Returns:
        List of tuples: (pid, command_line)
    """
    processes: List[Tuple[str, str]] = []
    
    try:
        # Use WMIC to find Python processes
        result = subprocess.run(
            ["wmic", "process", "where", "name like '%python%'", "get", "processid,commandline", "/format:csv"],
            capture_output=True,
            text=True,
            check=True
        )
        
        for line in result.stdout.split("\n"):
            line = line.strip()
            if not line or line.startswith("Node,"):
                continue
            
            parts = line.split(",")
            if len(parts) >= 3:
                cmd = ",".join(parts[1:-1])
                pid = parts[-1]
                
                for pattern in SERVICE_PATTERNS:
                    if pattern.lower() in cmd.lower():
                        processes.append((pid, cmd))
                        break
    
    except (subprocess.CalledProcessError, FileNotFoundError):
        # WMIC might not be available
        print("ℹ️  Limited process detection. Some services may not be found.")
    
    return processes


def stop_processes(processes: List[Tuple[str, str]], force: bool = False) -> None:
    """
    Stops the given processes.
    
    Args:
        processes: List of (pid, command_line) tuples
        force: If True, skip confirmation
    """
    if not processes:
        print()
        print("✅ No Smart Irrigation services are currently running.")
        print()
        print("💡 If services are running but not detected:")
        print("   • Close terminal windows manually")
        print("   • Use Task Manager to end 'python.exe' processes")
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
        for pattern in SERVICE_PATTERNS:
            if pattern.lower() in cmd.lower():
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
            subprocess.run(
                ["taskkill", "/PID", str(pid), "/F"],
                check=True,
                capture_output=True
            )
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
    parser = argparse.ArgumentParser(
        description="Stop Smart Precision Irrigation System (Windows)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts\\windows\\stop.py         Stop with confirmation prompt
  python scripts\\windows\\stop.py -f      Stop without confirmation
        """
    )
    parser.add_argument(
        "--force", "-f",
        action="store_true",
        help="Stop services without confirmation"
    )
    
    args = parser.parse_args()
    
    # Check platform
    if sys.platform != "win32":
        print("❌ This script is for Windows only.")
        print("   For macOS: python scripts/macos/stop.py")
        sys.exit(1)
    
    # Find and stop processes
    processes = find_service_processes()
    stop_processes(processes, force=args.force)


if __name__ == "__main__":
    main()
