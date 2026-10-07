# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_submodules


app_name = "ANNA"
distribution_name = "ANNA-1.0.0-Windows"

datas = [
    ("assets", "assets"),
    ("demo_project", "demo_project"),
    ("LICENSE", "."),
    ("PACKAGE_README.txt", "."),
    ("THIRD_PARTY_NOTICES.txt", "."),
    ("licenses", "licenses"),
]

a = Analysis(
    ["hotspot_editor.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=collect_submodules("PySide6.QtTextToSpeech"),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pytest", "tests"],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=app_name,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=["assets/app/ANNA.ico"],
    version="packaging/windows_version_info.txt",
    contents_directory=".",
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name=distribution_name,
)
