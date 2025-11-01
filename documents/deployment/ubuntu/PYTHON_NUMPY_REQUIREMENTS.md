# Python and NumPy requirements for Kotak Neo API

Context:
- Upstream kotak-neo-api commit 67143c58f29da9572cdbb273199852682a0019d5 pins numpy==1.24.2.
- numpy==1.24.2 does not provide wheels for Python 3.12 and fails to build; our project pins numpy==2.2.6.

Recommended setups

Option A: Python 3.11 (fully compatible with upstream deps)
- Create venv with Python 3.11
- Install dependencies from requirements.txt (the VCS dependency is enabled for Python < 3.12)

Example (Ubuntu):

```bash
sudo apt-get update
sudo apt-get install -y python3.11-venv
python3.11 -m venv .venv && source .venv/bin/activate
python -m pip install -U pip setuptools wheel
pip install -r requirements.txt
```

Option B: Python 3.12 (keep newer NumPy, bypass upstream pin)
- Keep NumPy >= 1.26 (project uses 2.2.6)
- Install kotak-neo-api without its dependencies to avoid downgrading NumPy

Example:
```bash
python3 -m venv .venv && source .venv/bin/activate
python -m pip install -U pip setuptools wheel
pip install -r requirements.txt
pip install --no-deps git+https://github.com/Kotak-Neo/kotak-neo-api@67143c58f29da9572cdbb273199852682a0019d5
```

Notes
- requirements.txt now contains the VCS dependency guarded with marker: only installs on Python < 3.12.
- For Python 3.12, use the --no-deps install shown above, or fork the repository and relax the NumPy pin (recommended long-term).
- If using system packages on Ubuntu and you hit dpkg overwrite errors while upgrading Python 3.11, upgrade minimal packages first or use the force-overwrite option for the conflicting package, then retry.
