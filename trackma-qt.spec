# -*- mode: python -*-

from PyInstaller.utils.hooks import collect_submodules

block_cipher = None


a = Analysis(['trackma/ui/qtui.py'],
             binaries=[],
             datas=[('trackma/data', 'trackma/data')],
             hiddenimports=collect_submodules('trackma.lib'),
             hookspath=[],
             runtime_hooks=[],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher,
             noarchive=False)
pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)

# Bundle
'''
exe = EXE(pyz,
          a.scripts,
          [],
          exclude_binaries=True,
          name='trackma-qt',
          debug=False,
          strip=False,
          upx=True,
          console=True )

coll = COLLECT(exe,
               a.binaries,
               a.zipfiles,
               a.datas,
               strip=False,
               upx=True,
               name='trackma-qt')
'''

# Onefile
exe = EXE(pyz,
          a.scripts,
          a.binaries,
          a.zipfiles,
          a.datas,
          [],
          name='trackma-qt',
          debug=False,
          strip=False,
          upx=True,
          icon='trackma/data/icon.ico',
          runtime_tmpdir=None,
          console=False )

