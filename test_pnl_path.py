#!/usr/bin/env python3
import json
import os
from pathlib import Path

cwd = os.getcwd()
print(f"Current working directory: {cwd}")

path = Path("paper_trading/user_1/account.json")
print(f"Relative path exists: {path.exists()}")

if path.exists():
    with open(path) as f:
        data = json.load(f)
    print(f"Total PnL (relative): {data.get('total_pnl')}")
else:
    # Try absolute path
    abs_path = Path("/app/paper_trading/user_1/account.json")
    print(f"Trying absolute path: {abs_path}")
    print(f"Absolute exists: {abs_path.exists()}")
    if abs_path.exists():
        with open(abs_path) as f:
            data = json.load(f)
        print(f"Total PnL (absolute): {data.get('total_pnl')}")
