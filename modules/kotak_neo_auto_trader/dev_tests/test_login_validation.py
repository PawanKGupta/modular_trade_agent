#!/usr/bin/env python3
"""
Test script to validate Kotak Neo login
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

import json

from modules.kotak_neo_auto_trader.auth import KotakNeoAuth


def main():
    print("=" * 80)
    print("Kotak Neo Login Validation Test")
    print("=" * 80)
    print()

    # Initialize auth
    config_file = "modules/kotak_neo_auto_trader/kotak_neo.env"
    print(f"? Loading credentials from: {config_file}")
    auth = KotakNeoAuth(config_file)
    print(f"? Auth initialized (Environment: {auth.environment})")
    print()

    # Attempt login
    print("? Attempting login...")
    login_success = auth.login()
    print(f"Login result: {'? SUCCESS' if login_success else '? FAILED'}")
    print()

    # Validate login
    print("=" * 80)
    print("Validating Login...")
    print("=" * 80)

    is_valid, validation_details = auth.validate_login(test_api_call=True)

    print("\n? Validation Results:")
    print(f"  Overall Status: {'? VALID' if is_valid else '? INVALID'}")
    print()

    print("? Validation Details:")
    print(f"  - Is Logged In: {'?' if validation_details['is_logged_in'] else '?'}")
    print(f"  - Client Exists: {'?' if validation_details['client_exists'] else '?'}")
    print(
        f"  - Session Token: {'?' if validation_details['session_token_exists'] else '[WARN]?  Not set (may be normal)'}"
    )

    if validation_details["api_test_passed"] is not None:
        api_status = "?" if validation_details["api_test_passed"] else "?"
        print(f"  - API Test: {api_status}")
        print(f"    Message: {validation_details['api_test_message']}")
    else:
        print("  - API Test: [WARN]?  Not performed")
        if validation_details["api_test_message"]:
            print(f"    Message: {validation_details['api_test_message']}")

    print()

    # Show errors if any
    if validation_details["errors"]:
        print("? Errors:")
        for error in validation_details["errors"]:
            print(f"  - {error}")
        print()

    # Show warnings if any
    if validation_details["warnings"]:
        print("[WARN]?  Warnings:")
        for warning in validation_details["warnings"]:
            print(f"  - {warning}")
        print()

    # Summary
    print("=" * 80)
    if is_valid:
        print("? Login validation PASSED")
        print("   Session is valid and ready for API calls")
    else:
        print("? Login validation FAILED")
        print("   Please check errors above and verify credentials")
    print("=" * 80)

    # Optionally print full validation details as JSON
    if len(sys.argv) > 1 and sys.argv[1] == "--json":
        print("\n? Full Validation Details (JSON):")
        print(json.dumps(validation_details, indent=2, default=str))

    return 0 if is_valid else 1


if __name__ == "__main__":
    sys.exit(main())
