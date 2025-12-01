#!/usr/bin/env python3
"""
Health Check Script for Rebound — Modular Trade Agent
Verifies all components are properly configured and functional

Run this script to diagnose issues with your installation.
"""

import os
import sys
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

try:
    from utils.version import get_installed_version, get_package_version, format_version_info

    HAS_VERSION = True
except ImportError:
    HAS_VERSION = False


class HealthCheck:
    """Comprehensive health check for trading agent"""

    def __init__(self):
        self.install_dir = (
            Path(os.environ.get("PROGRAMDATA", "C:\\ProgramData")) / "ModularTradeAgent"
        )
        self.results = []
        self.warnings = []
        self.errors = []

    def check(
        self, name: str, condition: bool, success_msg: str, fail_msg: str, critical: bool = False
    ):
        """
        Record a check result.

        Args:
            name: Check name
            condition: True if check passed
            success_msg: Message on success
            fail_msg: Message on failure
            critical: If True, failure is an error, else warning
        """
        status = "[OK]" if condition else "[FAIL]"
        message = success_msg if condition else fail_msg

        self.results.append((status, name, message))

        if not condition:
            if critical:
                self.errors.append(f"{name}: {fail_msg}")
            else:
                self.warnings.append(f"{name}: {fail_msg}")

        return condition

    def section(self, title: str):
        """Print section header"""
        print(f"\n{'='*60}")
        print(f"{title}")
        print("=" * 60)

    def print_result(self, status: str, name: str, message: str):
        """Print a check result"""
        symbol = "[OK]" if status == "[OK]" else "[FAIL]"
        color = "green" if status == "[OK]" else "red"
        print(f"  {symbol} {name}: {message}")

    def check_version(self):
        """Check version information"""
        self.section("VERSION CHECK")

        if not HAS_VERSION:
            self.check(
                "Version Module",
                False,
                "Version module available",
                "Version module not found",
                False,
            )
            return

        # Package version
        package_version = get_package_version()
        if package_version:
            self.check(
                "Package Version",
                True,
                f"{format_version_info(package_version)}",
                "No package version found",
                False,
            )

        # Installed version
        installed_version = get_installed_version(self.install_dir)
        if installed_version:
            self.check(
                "Installed Version",
                True,
                f"{format_version_info(installed_version)}",
                "No installed version found",
                False,
            )
        else:
            self.check(
                "Installed Version", False, "Installation found", "No installation detected", False
            )

        # Print results
        for status, name, message in self.results[-3:]:
            self.print_result(status, name, message)

    def check_installation(self):
        """Check if software is installed"""
        self.section("INSTALLATION CHECK")

        # Installation directory
        install_exists = self.install_dir.exists()
        self.check(
            "Install Directory",
            install_exists,
            f"Found at {self.install_dir}",
            f"Not found at {self.install_dir}",
            True,
        )

        if not install_exists:
            self.print_result("[FAIL]", "Install Directory", f"Not found at {self.install_dir}")
            return

        # Python runtime
        python_dir = self.install_dir / "python"
        python_exe = python_dir / "python.exe"
        self.check(
            "Python Runtime",
            python_exe.exists(),
            f"Found at {python_exe}",
            f"Not found at {python_exe}",
            True,
        )

        # Application files
        app_dir = self.install_dir / "TradingAgent"
        self.check(
            "Application Files",
            app_dir.exists(),
            f"Found at {app_dir}",
            f"Not found at {app_dir}",
            True,
        )

        # Data directory
        data_dir = self.install_dir / "data"
        self.check(
            "Data Directory",
            data_dir.exists(),
            f"Found at {data_dir}",
            f"Not found at {data_dir}",
            False,
        )

        # Logs directory
        logs_dir = self.install_dir / "logs"
        self.check(
            "Logs Directory",
            logs_dir.exists(),
            f"Found at {logs_dir}",
            f"Not found at {logs_dir}",
            False,
        )

        # Print results
        for status, name, message in self.results[-5:]:
            self.print_result(status, name, message)

    def check_configuration(self):
        """Check configuration files"""
        self.section("CONFIGURATION CHECK")

        # kotak_neo.env
        env_file = self.install_dir / "kotak_neo.env"
        env_exists = env_file.exists()
        self.check(
            "Environment File",
            env_exists,
            "kotak_neo.env found",
            "kotak_neo.env missing - credentials not configured!",
            True,
        )

        if env_exists:
            # Check required fields
            required_fields = [
                "KOTAK_NEO_CONSUMER_KEY",
                "KOTAK_NEO_CONSUMER_SECRET",
                "KOTAK_NEO_MOBILE_NUMBER",
                "KOTAK_NEO_PASSWORD",
                "KOTAK_NEO_MPIN",
            ]

            try:
                env_content = env_file.read_text()
                for field in required_fields:
                    has_field = (
                        field in env_content
                        and not env_content.split(field)[1].split("\n")[0].strip() == "="
                    )
                    self.check(
                        f"Config: {field}", has_field, "Configured", "Missing or empty", True
                    )
            except Exception as e:
                self.check(
                    "Config Parsing",
                    False,
                    "Config parsed successfully",
                    f"Failed to parse: {e}",
                    True,
                )

        # Print results
        start_idx = len(self.results) - (6 if env_exists else 1)
        for status, name, message in self.results[start_idx:]:
            self.print_result(status, name, message)

    def check_services(self):
        """Check Windows services"""
        self.section("WINDOWS SERVICES CHECK")

        services = [
            "ModularTradeAgent_Main",
            "ModularTradeAgent_Monitor",
            "ModularTradeAgent_EOD",
            "ModularTradeAgent_Sell",
        ]

        for service_name in services:
            try:
                result = subprocess.run(
                    ["sc", "query", service_name], capture_output=True, text=True, timeout=5
                )

                if result.returncode == 0:
                    # Service exists, check if running
                    output = result.stdout
                    is_running = "RUNNING" in output

                    if is_running:
                        self.check(service_name, True, "Installed and RUNNING", "", False)
                    else:
                        self.check(service_name, True, "Installed but STOPPED", "", False)
                else:
                    self.check(service_name, False, "Installed", "Not installed", False)
            except Exception as e:
                self.check(service_name, False, "Accessible", f"Error checking: {e}", False)

        # Print results
        for status, name, message in self.results[-len(services) :]:
            self.print_result(status, name, message)

    def check_scripts(self):
        """Check critical Python scripts"""
        self.section("SCRIPT FILES CHECK")

        if not (self.install_dir / "TradingAgent").exists():
            self.check(
                "Scripts", False, "Script directory found", "TradingAgent directory missing", True
            )
            self.print_result("[FAIL]", "Scripts", "TradingAgent directory missing")
            return

        scripts_dir = self.install_dir / "TradingAgent" / "modules" / "kotak_neo_auto_trader"

        scripts = [
            "run_auto_trade.py",
            "run_position_monitor.py",
            "run_eod_cleanup.py",
            "run_sell_orders.py",
        ]

        for script in scripts:
            script_path = scripts_dir / script
            self.check(f"Script: {script}", script_path.exists(), "Found", "Missing", False)

        # Print results
        for status, name, message in self.results[-len(scripts) :]:
            self.print_result(status, name, message)

    def check_launcher_scripts(self):
        """Check launcher batch files"""
        self.section("LAUNCHER SCRIPTS CHECK")

        launchers = [
            "RUN_AGENT.bat",
            "START_ALL_SERVICES.bat",
            "STOP_ALL_SERVICES.bat",
            "START_MAIN.bat",
            "STOP_MAIN.bat",
        ]

        for launcher in launchers:
            launcher_path = self.install_dir / launcher
            self.check(f"Launcher: {launcher}", launcher_path.exists(), "Found", "Missing", False)

        # Print results
        for status, name, message in self.results[-len(launchers) :]:
            self.print_result(status, name, message)

    def check_data_files(self):
        """Check data and history files"""
        self.section("DATA FILES CHECK")

        data_dir = self.install_dir / "data"

        if not data_dir.exists():
            self.check(
                "Data Files", False, "Data directory exists", "Data directory not found", False
            )
            self.print_result("[FAIL]", "Data Files", "Data directory not found")
            return

        # trades_history.json
        history_file = data_dir / "trades_history.json"
        if history_file.exists():
            try:
                import json

                with open(history_file) as f:
                    data = json.load(f)
                    trades_count = len(data.get("trades", []))
                    failed_count = len(data.get("failed_orders", []))

                    self.check(
                        "Trade History",
                        True,
                        f"{trades_count} trades, {failed_count} failed orders",
                        "",
                        False,
                    )
            except Exception as e:
                self.check("Trade History", False, "Valid JSON", f"Corrupt file: {e}", False)
        else:
            self.check(
                "Trade History",
                False,
                "File exists",
                "No trade history yet (normal for new install)",
                False,
            )

        # Print results
        for status, name, message in self.results[-1:]:
            self.print_result(status, name, message)

    def check_logs(self):
        """Check log files"""
        self.section("LOG FILES CHECK")

        logs_dir = self.install_dir / "logs"

        if not logs_dir.exists():
            self.check(
                "Logs",
                False,
                "Logs directory exists",
                "Logs directory not found (services haven't run yet)",
                False,
            )
            self.print_result(
                "[FAIL]", "Logs", "Logs directory not found (services haven't run yet)"
            )
            return

        log_files = list(logs_dir.glob("*.log"))

        if log_files:
            self.check("Log Files", True, f"Found {len(log_files)} log files", "", False)

            # Check latest log
            if log_files:
                latest_log = max(log_files, key=lambda p: p.stat().st_mtime)
                mod_time = datetime.fromtimestamp(latest_log.stat().st_mtime)
                self.check(
                    "Latest Log",
                    True,
                    f"{latest_log.name} (modified {mod_time.strftime('%Y-%m-%d %H:%M')})",
                    "",
                    False,
                )
        else:
            self.check(
                "Log Files", False, "Log files exist", "No logs yet (services haven't run)", False
            )

        # Print results
        for status, name, message in self.results[-2:]:
            self.print_result(status, name, message)

    def check_dependencies(self):
        """Check Python dependencies"""
        self.section("PYTHON DEPENDENCIES CHECK")

        python_exe = self.install_dir / "python" / "python.exe"

        if not python_exe.exists():
            self.check("Dependencies", False, "Python runtime available", "Python not found", True)
            self.print_result("[FAIL]", "Dependencies", "Python not found")
            return

        # Key dependencies
        required_packages = ["pandas", "numpy", "yfinance", "requests", "ta"]

        for package in required_packages:
            try:
                result = subprocess.run(
                    [str(python_exe), "-m", "pip", "show", package],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )

                self.check(
                    f"Package: {package}",
                    result.returncode == 0,
                    "Installed",
                    "Not installed",
                    True,
                )
            except Exception as e:
                self.check(f"Package: {package}", False, "Installed", f"Error checking: {e}", True)

        # Print results
        for status, name, message in self.results[-len(required_packages) :]:
            self.print_result(status, name, message)

    def generate_summary(self):
        """Generate final summary"""
        self.section("HEALTH CHECK SUMMARY")

        total_checks = len(self.results)
        passed = sum(1 for s, _, _ in self.results if s == "[OK]")
        failed = total_checks - passed

        print(f"\nTotal Checks: {total_checks}")
        print(f"  [OK] Passed: {passed}")
        print(f"  [FAIL] Failed: {failed}")
        print()

        if self.errors:
            print(f"ERRORS ({len(self.errors)}):")
            for error in self.errors:
                print(f"  [FAIL] {error}")
            print()

        if self.warnings:
            print(f"WARNINGS ({len(self.warnings)}):")
            for warning in self.warnings:
                print(f"  [WARN] {warning}")
            print()

        # Overall status
        if not self.errors:
            print("=" * 60)
            print("[OK] OVERALL STATUS: HEALTHY")
            print("=" * 60)
            print("\nYour installation appears to be working correctly!")
            print("If you're experiencing issues, check the warnings above.")
        else:
            print("=" * 60)
            print("[FAIL] OVERALL STATUS: ISSUES DETECTED")
            print("=" * 60)
            print("\nCritical errors found. Please address the errors listed above.")
            print("Run the installer to fix missing files or configuration.")

        print()

    def run_all_checks(self):
        """Run all health checks"""
        print("=" * 60)
        print("REBOUND — MODULAR TRADE AGENT - HEALTH CHECK")
        print("=" * 60)
        print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        self.check_version()
        self.check_installation()
        self.check_configuration()
        self.check_services()
        self.check_scripts()
        self.check_launcher_scripts()
        self.check_data_files()
        self.check_logs()
        self.check_dependencies()

        self.generate_summary()


def main():
    """Main entry point"""
    health_check = HealthCheck()

    try:
        health_check.run_all_checks()
    except KeyboardInterrupt:
        print("\n\nHealth check interrupted by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nERROR: Health check failed: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)

    # Exit code based on results
    sys.exit(0 if not health_check.errors else 1)


if __name__ == "__main__":
    main()
