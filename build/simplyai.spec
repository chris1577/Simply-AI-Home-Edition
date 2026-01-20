# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for Simply AI - Home Edition

This spec file bundles the Flask application with all dependencies,
templates, static files, and setup scripts into a single executable.
"""

import os
import sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# Project root directory
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(SPEC)))

# Collect data files from various packages
datas = [
    # Application templates and static files
    (os.path.join(PROJECT_ROOT, 'templates'), 'templates'),
    (os.path.join(PROJECT_ROOT, 'static'), 'static'),

    # Setup scripts (needed for first-run initialization)
    (os.path.join(PROJECT_ROOT, 'scripts', 'setup'), os.path.join('scripts', 'setup')),
    (os.path.join(PROJECT_ROOT, 'scripts', 'migrations'), os.path.join('scripts', 'migrations')),

    # Include .env.example as reference
    # (os.path.join(PROJECT_ROOT, '.env.example'), '.'),
]

# Collect data files from dependencies
datas += collect_data_files('sentence_transformers')
datas += collect_data_files('transformers')
datas += collect_data_files('tiktoken')
datas += collect_data_files('chromadb')
datas += collect_data_files('certifi')

# Hidden imports - packages that PyInstaller might miss
hiddenimports = [
    # Flask and extensions
    'flask',
    'flask_sqlalchemy',
    'flask_login',
    'flask_limiter',
    'werkzeug',
    'jinja2',

    # Database
    'sqlalchemy',
    'sqlalchemy.dialects.sqlite',
    'sqlite3',

    # AI/ML packages
    'google.genai',
    'tiktoken',
    'tiktoken_ext',
    'tiktoken_ext.openai_public',
    'sentence_transformers',
    'transformers',
    'torch',
    'chromadb',
    'chromadb.config',

    # Document processing
    'fitz',  # PyMuPDF
    'docx',
    'openpyxl',

    # Security
    'cryptography',
    'pyotp',
    'qrcode',

    # Utilities
    'PIL',
    'requests',
    'dotenv',

    # App modules
    'app',
    'app.config',
    'app.models',
    'app.routes',
    'app.services',
    'app.utils',
]

# Collect all submodules for complex packages
hiddenimports += collect_submodules('sqlalchemy')
hiddenimports += collect_submodules('chromadb')
hiddenimports += collect_submodules('sentence_transformers')
hiddenimports += collect_submodules('transformers')
hiddenimports += collect_submodules('google.genai')

# Analysis
a = Analysis(
    [os.path.join(PROJECT_ROOT, 'run_compiled.py')],
    pathex=[PROJECT_ROOT],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib',
        'notebook',
        'jupyter',
        'IPython',
        'pytest',
        'black',
        'flake8',
        'mypy',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

# Create PYZ archive
pyz = PYZ(a.pure, a.zipped_data, cipher=None)

# Create executable
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='SimplyAI',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,  # Set to False for GUI-only mode
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join(PROJECT_ROOT, 'static', 'images', 'favicon.ico') if os.path.exists(os.path.join(PROJECT_ROOT, 'static', 'images', 'favicon.ico')) else None,
)

# Collect all files
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='SimplyAI',
)
