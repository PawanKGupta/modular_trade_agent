# Python 3.12+ Setup Guide

**This guide applies to all operating systems (Windows, Linux, macOS).**

## Context

- Upstream kotak-neo-api commit 67143c58f29da9572cdbb273199852682a0019d5 pins numpy==1.24.2
- numpy==1.24.2 does not provide wheels for Python 3.12+ and fails to build
- Our project requires numpy==2.2.6 for Python 3.12+ compatibility
- **Python 3.11 is NOT compatible with this project**

## Required Python Version

**Python 3.12 or above is required.**

## Setup Instructions
**Strategy:**
- Keep NumPy >= 1.26 (project uses 2.2.6)
- Install kotak-neo-api without its dependencies to avoid downgrading NumPy
- Manually install minimal required dependencies for kotak-neo-api
- Upgrade websockets/websocket-client to compatible versions

Complete step-by-step commands:

### 1. Install Python 3.12+

**Ubuntu/Debian:**
```bash
sudo apt-get update && sudo apt-get install -y python3.12 python3.12-venv
```

**Windows:**
- Download from [python.org](https://www.python.org/downloads/)
- Check "Add Python to PATH" during installation

**macOS:**
```bash
brew install python@3.12
```

### 2. Create and activate virtual environment

**Linux/macOS:**
```bash
python3.12 -m venv .venv && source .venv/bin/activate
```

**Windows (PowerShell):**
```powershell
python -m venv .venv
.\.venv\Scripts\activate
```

**Windows (Command Prompt):**
```cmd
python -m venv .venv
.venv\Scripts\activate.bat
```

### 3. Upgrade pip, setuptools, wheel

```bash

python -m pip install -U pip setuptools wheel
```

### 4. Install project dependencies

```bash
# numpy 2.2.6 will be installed
pip install -r requirements.txt
```

### 5. Install dev dependencies

```bash
# pytest, pytest-cov
pip install -r requirements-dev.txt
```

### 6. Install kotak-neo-api without dependencies

```bash
# Bypasses numpy==1.24.2 pin
pip install --no-deps git+https://github.com/Kotak-Neo/kotak-neo-api@67143c58f29da9572cdbb273199852682a0019d5
```

### 7. Install minimal required dependencies for kotak-neo-api

**Note:** You may see dependency warnings - this is expected and can be ignored.

```bash
pip install -U bidict==0.22.1
pip install pyjsparser==2.7.1 PyJWT==2.6.0 websocket-client==1.5.1 websockets==8.1 python-dateutil==2.9.0.post0 six==1.17.0
```

### 8. Verify neo_api_client imports successfully

```bash
python -c "import neo_api_client; print('neo_api_client OK')"
```

### 9. Upgrade websockets to modern versions

**Note:** You may see warnings about incompatible versions - this is expected and can be ignored.

```bash
pip install -U "websockets>=13" "websocket-client>=1.8,<2"
```

### 10. Verify all critical imports work

**Linux/macOS:**
```bash
python - <<'PY'
import yfinance, selenium, neo_api_client, numpy, pandas
print("Imports OK:", numpy.__version__, pandas.__version__)
PY
```

**Windows (PowerShell):**
```powershell
python -c "import yfinance, selenium, neo_api_client, numpy, pandas; print('Imports OK:', numpy.__version__, pandas.__version__)"
```

### 11. Run tests to verify setup

```bash
python -m pytest -q
```

## Notes

**Python 3.12+ Workaround Explanation:**
- requirements.txt contains the VCS dependency guarded with marker: only installs on Python < 3.12 (legacy, not used).
- For Python 3.12+, the `--no-deps` flag is crucial to prevent kotak-neo-api from downgrading numpy to 1.24.2.
- After installing kotak-neo-api without deps, we manually install only its required dependencies:
  - `bidict==0.22.1` - bidirectional dict library
  - `pyjsparser==2.7.1` - JavaScript parser
  - `PyJWT==2.6.0` - JSON Web Token implementation
  - `websocket-client==1.5.1` - WebSocket client (initial version)
  - `websockets==8.1` - WebSocket protocol implementation (initial version)
  - `python-dateutil==2.9.0.post0` - date/time utilities
  - `six==1.17.0` - Python 2/3 compatibility
- The two-stage websockets installation is necessary:
  1. First install older versions (1.5.1 and 8.1) to satisfy neo_api_client imports
  2. Then upgrade to modern versions (>=13 and >=1.8) for better compatibility
- This approach keeps numpy 2.2.6 while maintaining kotak-neo-api functionality.
- Alternative long-term solution: fork the kotak-neo-api repository and relax the NumPy pin.

**Important:**
- **Python 3.11 and below are NOT supported** - use Python 3.12 or higher only.
- Always use `python -m pytest` instead of bare `pytest` command to ensure correct Python interpreter.
- If you encounter package conflicts during installation, ensure you're using Python 3.12+ before troubleshooting.
