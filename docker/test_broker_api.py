#!/usr/bin/env python3
"""Test Kotak Neo API connectivity"""

import requests
import urllib3
from urllib3.exceptions import InsecureRequestWarning

urllib3.disable_warnings(InsecureRequestWarning)


def test_api():
    base_url = "https://gw-napi.kotaksecurities.com"
    endpoints = [
        "/",
        "/Portfolio/1.0/portfolio/v1/holdings",
        "/Orders/2.0/quick/user/limits",
    ]

    print("Testing Kotak Neo API connectivity...")
    print(f"Base URL: {base_url}\n")

    for endpoint in endpoints:
        url = base_url + endpoint
        print(f"Testing: {endpoint}")
        try:
            response = requests.get(url, timeout=10, verify=False)
            print(f"  Status: {response.status_code}")
            print(f"  Response length: {len(response.content)} bytes")
            if response.status_code == 401 or response.status_code == 403:
                print("  ✓ API is reachable (authentication required - expected)")
            elif response.status_code == 200:
                print("  ✓ API is reachable and responding")
            else:
                print(f"  ⚠ Unexpected status: {response.status_code}")
        except requests.exceptions.ConnectionError as e:
            print(f"  ✗ Connection Error: {e}")
            print("  → API server is DOWN or unreachable")
        except requests.exceptions.Timeout:
            print("  ✗ Timeout: API did not respond within 10 seconds")
        except Exception as e:
            print(f"  ✗ Error: {type(e).__name__}: {e}")
        print()


if __name__ == "__main__":
    test_api()
