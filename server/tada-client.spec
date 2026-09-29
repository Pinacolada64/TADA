# -*- mode: python ; coding: utf-8 -*-
#
# PyInstaller spec for the standalone TADA client (tada_client.py).
#
# Build (run from this directory, server/):
#     pyinstaller tada-client.spec
#
# Produces a --onedir bundle at dist/tada-client/ — a folder containing the
# launcher plus its private Python runtime and libs. Ship the whole folder
# (zipped); testers run tada-client / tada-client.exe inside it. onedir is
# used rather than --onefile because it starts instantly (no unpack-to-temp
# on every launch) and draws far fewer Windows antivirus false positives.
#
# The client only needs stdlib + prompt_toolkit (+ its wcwidth dep). We pull
# both in wholesale via collect_all so a missing lazy import or data file
# can't surface only on a tester's machine.

from PyInstaller.utils.hooks import collect_all

datas = []
binaries = []
hiddenimports = []
for _pkg in ('prompt_toolkit', 'wcwidth'):
    _d, _b, _h = collect_all(_pkg)
    datas += _d
    binaries += _b
    hiddenimports += _h

a = Analysis(
    ['tada_client.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # Keep the bundle lean: none of these are imported by the client, and
    # letting PyInstaller drag them in just bloats the folder.
    excludes=['tkinter', 'pytest', '_pytest', 'numpy', 'PIL'],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='tada-client',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='tada-client',
)
