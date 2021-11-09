# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

datas = []
binaries = [('venv/lib/python3.9/site-packages/freetype/libfreetype.dylib', '.')]
hiddenimports = []
tmp_ret = collect_all('gftools')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('glyphsLib')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]





qa_a = Analysis(['bin/gftools-qa.py'],
             pathex=[],
             binaries=[],
             datas=[],
             hiddenimports=[],
             hookspath=[],
             hooksconfig={},
             runtime_hooks=[],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             noarchive=False)

builder_a = Analysis(['bin/gftools-builder.py'],
             pathex=[],
             binaries=[],
             datas=[],
             hiddenimports=[],
             hookspath=[],
             hooksconfig={},
             runtime_hooks=[],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             noarchive=False)


MERGE((qa_a, 'gftools-qa', 'bin/gftools-qa.py'), (builder_a, 'gftools-builder', 'bin/gftools-builder.py'))



qa_pyz = PYZ(qa_a.pure)

qa_exe = EXE(qa_pyz,
        qa_a.scripts, 
        [],
        exclude_binaries=True,
        name='gftools-qa',
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        console=True,
        disable_windowed_traceback=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None )

qa_coll = COLLECT(qa_exe,
        qa_a.binaries,
        qa_a.zipfiles,
        qa_a.datas, 
        strip=False,
        upx=True,
        upx_exclude=[],
        name='gftools-qa')




builder_pyz = PYZ(builder_a.pure)

builder_exe = EXE(builder_pyz,
          builder_a.scripts, 
          [],
          exclude_binaries=True,
          name='gftools-builder',
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=True,
          console=True,
          disable_windowed_traceback=False,
          target_arch=None,
          codesign_identity=None,
          entitlements_file=None )

builder_coll = COLLECT(builder_exe,
               builder_a.binaries,
               builder_a.zipfiles,
               builder_a.datas, 
               strip=False,
               upx=True,
               upx_exclude=[],
               name='gftools-builder')