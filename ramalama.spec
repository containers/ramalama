# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for building standalone RamaLama executable on macOS.

This creates a single executable that includes Python and all dependencies,
eliminating the need for users to install Python separately.

Build with: pyinstaller ramalama.spec
"""

import sys
from pathlib import Path

# Import version dynamically
sys.path.insert(0, str(Path.cwd() / 'ramalama'))
from version import version as get_version

block_cipher = None

# Get the project root directory
project_root = Path.cwd()

# Get version dynamically
app_version = get_version()

# Collect all ramalama package files
a = Analysis(
    ['bin/ramalama'],
    pathex=[str(project_root)],
    binaries=[],
    datas=[
        # Include shortnames configuration
        ('shortnames/shortnames.conf', 'share/ramalama'),
        # Include ramalama.conf
        ('docs/ramalama.conf', 'share/ramalama'),
        # Include inference spec files
        ('inference-spec/schema/*.json', 'share/ramalama/inference'),
        ('inference-spec/engines/*', 'share/ramalama/inference'),
        # Include completions
        ('completions/bash-completion/completions/*', 'share/bash-completion/completions'),
        ('completions/fish/vendor_completions.d/*', 'share/fish/vendor_completions.d'),
        ('completions/zsh/site-functions/*', 'share/zsh/site-functions'),
        # Include man pages
        ('docs/*.1', 'share/man/man1'),
        ('docs/*.5', 'share/man/man5'),
        ('docs/*.7', 'share/man/man7'),
    ],
    hiddenimports=[
        'ramalama',
        'ramalama.cli',
        'ramalama.version',
        'ramalama.common',
        'ramalama.config',
        'ramalama.engine',
        'ramalama.kube',
        'ramalama.quadlet',
        'ramalama.rag',
        'ramalama.stack',
        'ramalama.chat',
        'ramalama.compose',
        'ramalama.http_client',
        'ramalama.daemon',
        'ramalama.mcp',
        'ramalama.model_store',
        'ramalama.transports',
        'ramalama.file_loaders',
        'argcomplete',
        'yaml',
        'jsonschema',
        'jinja2',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'matplotlib',
        'numpy',
        'scipy',
        'pandas',
        'PIL',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
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
    name='ramalama',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,  # Disabled for Apple Silicon compatibility
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

# Create app bundle for macOS
app = BUNDLE(
    exe,
    name='ramalama.app',
    icon=None,
    bundle_identifier='com.github.containers.ramalama',
    version=app_version,
    info_plist={
        'CFBundleName': 'RamaLama',
        'CFBundleDisplayName': 'RamaLama',
        'CFBundleIdentifier': 'com.github.containers.ramalama',
        'CFBundleVersion': app_version,
        'CFBundleShortVersionString': app_version,
        'NSHumanReadableCopyright': 'Copyright © 2024 The Containers Organization',
        'CFBundleExecutable': 'ramalama',
    },
)

