# Build with: python -m PyInstaller --distpath build/backend --workpath build/pyinstaller packaging/InternBackend.spec
from pathlib import Path

root = Path(SPECPATH).parent
a = Analysis(
    [str(root / 'packaging' / 'backend_entry.py')], pathex=[str(root)],
    binaries=[], datas=[],
    hiddenimports=['pythoncom', 'pywintypes', 'win32com.client', 'win32timezone', 'workbook_store', 'openpyxl'],
    hookspath=[], hooksconfig={}, runtime_hooks=[],
    excludes=['tkinter', 'ttkbootstrap', 'pytest'], noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='InternBackend', debug=False,
          bootloader_ignore_signals=False, strip=False, upx=False, console=True,
          icon=str(root / 'build-resources' / 'icon.ico'))
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='InternBackend')
