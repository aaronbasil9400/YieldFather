# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for the portable Windows SPC desktop bundle (onedir).
# Build:  python -m PyInstaller --noconfirm --clean spc_desktop.spec
# Output: dist/SPC_Dashboard/SPC_Dashboard.exe

a = Analysis(
    ["spc_desktop_launcher.py"],
    pathex=[],
    binaries=[],
    datas=[("assets", "assets")],
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    excludes=[
        "streamlit",
        "plotly",
        "matplotlib",
        "tkinter",
        "IPython",
        "jupyter",
        "pytest",
        "PySide6.QtWebEngineCore",
        "PySide6.QtWebEngineWidgets",
        "PySide6.QtPdf",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="SPC_Dashboard",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="SPC_Dashboard",
)
