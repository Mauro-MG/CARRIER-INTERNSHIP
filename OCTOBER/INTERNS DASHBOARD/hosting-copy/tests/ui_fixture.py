"""Browser-test fixture: only disposable local data, never a desktop Excel connection."""
import atexit
from contextlib import contextmanager
from datetime import date
import os
from pathlib import Path
import shutil
import sys
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fake_excel import Book, application
import excel_store
import dashboard_bridge

root = Path(__file__).resolve().parent / ('run_' + uuid4().hex)
root.mkdir()
atexit.register(shutil.rmtree, root, ignore_errors=True)
book = Book(root / 'browser-fixture.xlsx',
            ['Full Name', 'Start Date', 'Universidad', 'Role', 'Supervisor', 'Carrera',
             'Contacto de emergencia (Nombre completo)', 'Agencia del Seguro', 'Número de Póliza', 'Months', 'Notes'],
            [('Sample Intern', date(2026, 1, 31), 'UANL', 'Design', 'Sample Supervisor', 'Engineering',
              'Sample Contact', 'Sample Provider', '00001', 99, 'Existing information retained'),
             ('Second Intern', date(2026, 3, 1), 'TEC', 'Engineering', 'Sample Supervisor', 'Engineering',
              '', '', '', 50, '')], offset_table=True)
app = application(book)
os.environ['DASHBOARD_BACKUP_DIR'] = str(root / 'backups')

@contextmanager
def connection():
    yield app

excel_store.connection = connection
dashboard_bridge.main()
