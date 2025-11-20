"""
Paper Trading Test Runner
Convenience script to run paper trading tests with various options
"""

import sys
import subprocess
from pathlib import Path


def run_all_tests():
    """Run all paper trading tests"""
    print("Running all paper trading tests...\n")
    cmd = [sys.executable, "-m", "pytest", "tests/paper_trading/", "-v", "--tb=short"]
    subprocess.run(cmd)


def run_with_coverage():
    """Run tests with coverage report"""
    print("Running tests with coverage...\n")
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/paper_trading/",
        "--cov=modules/kotak_neo_auto_trader/infrastructure",
        "--cov=modules/kotak_neo_auto_trader/config",
        "--cov-report=term-missing",
        "--cov-report=html",
        "-v",
    ]
    result = subprocess.run(cmd)
    if result.returncode == 0:
        print("\n? Coverage report generated in htmlcov/index.html")


def run_specific_component(component):
    """Run tests for a specific component"""
    test_files = {
        "config": "test_configuration.py",
        "portfolio": "test_portfolio_manager.py",
        "orders": "test_order_simulator.py",
        "persistence": "test_persistence.py",
        "prices": "test_price_provider.py",
        "integration": "test_integration.py",
        "basic": "test_paper_trading_basic.py",
    }

    if component not in test_files:
        print(f"? Unknown component: {component}")
        print(f"Available components: {', '.join(test_files.keys())}")
        return

    test_file = f"tests/paper_trading/{test_files[component]}"
    print(f"Running {component} tests...\n")
    cmd = [sys.executable, "-m", "pytest", test_file, "-v"]
    subprocess.run(cmd)


def run_quick():
    """Run quick smoke tests"""
    print("Running quick smoke tests...\n")
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/paper_trading/test_paper_trading_basic.py",
        "-v",
        "--tb=line",
    ]
    subprocess.run(cmd)


def show_summary():
    """Show test summary"""
    print("\n" + "=" * 60)
    print("PAPER TRADING TEST SUITE")
    print("=" * 60)
    print("\nTest Files:")
    print("  - test_configuration.py (11 tests)")
    print("  - test_portfolio_manager.py (24 tests)")
    print("  - test_order_simulator.py (12 tests)")
    print("  - test_persistence.py (21 tests)")
    print("  - test_price_provider.py (7 tests)")
    print("  - test_integration.py (14 tests)")
    print("  - test_paper_trading_basic.py (15 tests)")
    print("\nTotal: 95+ tests | Coverage: >80%")
    print("=" * 60)
    print("\nCommands:")
    print("  python run_tests.py              # Run all tests")
    print("  python run_tests.py coverage     # Run with coverage")
    print("  python run_tests.py quick        # Quick smoke tests")
    print("  python run_tests.py <component>  # Run specific component")
    print("\nComponents:")
    print("  config, portfolio, orders, persistence, prices, integration, basic")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    if len(sys.argv) == 1:
        run_all_tests()
    elif sys.argv[1] == "coverage":
        run_with_coverage()
    elif sys.argv[1] == "quick":
        run_quick()
    elif sys.argv[1] == "help":
        show_summary()
    else:
        run_specific_component(sys.argv[1])
