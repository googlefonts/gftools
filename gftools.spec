# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all
import freetype as ft

datas = []
binaries = [(ft.raw.filename, ".")]
hiddenimports = []
tmp_ret = collect_all("gftools")
datas += tmp_ret[0]
binaries += tmp_ret[1]
hiddenimports += tmp_ret[2]

# from gftools builder
tmp_ret = collect_all("glyphsLib")
datas += tmp_ret[0]
binaries += tmp_ret[1]
hiddenimports += tmp_ret[2]



block_cipher = None


a_qa = Analysis(
    ["bin/gftools-qa.py"],
    pathex=["."],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
a_builder = Analysis(
    ["bin/gftools-builder.py"],
    pathex=["."],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

MERGE(
        (a_qa, "gftools-qa", "gftools-qa"),
        (a_builder, "gftools-builder", "gftools-builder"),
)

pyz_qa = PYZ(a_qa.pure, a_qa.zipped_data, cipher=block_cipher)
pyz_builder = PYZ(a_builder.pure, a_builder.zipped_data, cipher=block_cipher)

exe_qa = EXE(
    pyz_qa,
    a_qa.scripts,
    a_qa.binaries,
    a_qa.dependencies,
    a_qa.zipfiles,
    a_qa.datas,
    [],
    name="gftools-qa",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
exe_builder = EXE(
    pyz_builder,
    a_builder.scripts,
    a_builder.binaries,
    a_builder.dependencies,
    a_builder.zipfiles,
    a_builder.datas,
    [],
    name="gftools-builder",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)