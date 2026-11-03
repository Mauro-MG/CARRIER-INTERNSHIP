"""Collect the installed runtime license texts into the distributable."""
import importlib.metadata
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1]
target = root / 'build' / 'licenses'
target.mkdir(parents=True, exist_ok=True)
python_license = Path(sys.base_prefix) / 'LICENSE.txt'
if not python_license.exists():
    raise RuntimeError('The Python license text is missing from the build interpreter.')
(target / 'Python-LICENSE.txt').write_bytes(python_license.read_bytes())
for name in ('openpyxl', 'et-xmlfile', 'pillow', 'pywin32', 'pyinstaller'):
    distribution = importlib.metadata.distribution(name)
    found = False
    for item in distribution.files or []:
        if 'licen' not in str(item).lower() and 'copying' not in str(item).lower():
            continue
        source = Path(distribution.locate_file(item))
        if not source.is_file():
            continue
        destination = target / name / str(item).replace('..', '_parent_')
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(source.read_bytes())
        found = True
    if not found:
        raise RuntimeError(f'No license text found for {name}. Check the installed build dependencies.')
