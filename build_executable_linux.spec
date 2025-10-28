# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for Modular Trade Agent - Linux Build
Builds a standalone Linux executable with all dependencies
"""

block_cipher = None

# Analysis: Collect all Python files and dependencies
a = Analysis(
    ['modules/kotak_neo_auto_trader/run_auto_trade.py'],  # Main entry point
    pathex=[],
    binaries=[],
    datas=[
        # Include configuration files
        ('config/*.py', 'config'),
        ('modules/kotak_neo_auto_trader/*.py', 'modules/kotak_neo_auto_trader'),
        ('core/*.py', 'core'),
        ('utils/*.py', 'utils'),
        # Include data directory structure (but not sensitive files)
        ('data/.gitkeep', 'data'),
        # Include documentation
        ('documents/*.md', 'documents'),
        ('README.md', '.'),
    ],
    hiddenimports=[
        'pandas',
        'numpy',
        'yfinance',
        'requests',
        'ta',
        'pyotp',
        'neo_api_client',
        'selenium',
        'webdriver_manager',
        'schedule',
        'python-dotenv',
        'dotenv',
        'nltk',
        'beautifulsoup4',
        'bs4',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib',  # Exclude if not used
        'tkinter',     # Exclude GUI libraries
        'PyQt5',
        'PySide2',
    ],
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='ModularTradeAgent',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,  # Compress with UPX (optional, reduces size)
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,  # Keep console for logs
    disable_windowed_traceback=False,
)
