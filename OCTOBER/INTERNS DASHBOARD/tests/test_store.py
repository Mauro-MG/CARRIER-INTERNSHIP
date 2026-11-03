import shutil
import uuid
import unittest
from pathlib import Path
from openpyxl import load_workbook
import workbook_store as store


class WorkbookTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(__file__).resolve().parent / ('run_' + uuid.uuid4().hex)
        self.root.mkdir()
        self.addCleanup(shutil.rmtree, self.root)
        self.path = self.root / 'test.xlsx'
        store.create_sample(self.path)

    def test_append_backup_table_and_literal_values(self):
        before = self.path.read_bytes()
        snap = store.read(self.path)
        backup = store.append(snap, ['001', 'Alice', '=1+1', 'Note'], self.root / 'backups')
        self.assertEqual(backup.read_bytes(), before)
        result = store.read(self.path)
        self.assertEqual(result.rows[-1], ('001', 'Alice', '=1+1', 'Note'))
        wb = load_workbook(self.path)
        self.assertEqual(wb.active.tables['Records'].ref, 'A1:D3')
        self.assertEqual(wb.active['C3'].data_type, 's')
        wb.close()

    def test_stale_writer_is_blocked(self):
        snap = store.read(self.path)
        store.append(snap, ['002', 'Bob', '', ''], self.root / 'backups')
        saved = self.path.read_bytes()
        with self.assertRaisesRegex(ValueError, 'changed'):
            store.append(snap, ['003', 'Alice', '', ''], self.root / 'backups')
        self.assertEqual(self.path.read_bytes(), saved)

    def test_excel_lock_and_empty_submission(self):
        snap = store.read(self.path)
        with self.assertRaises(ValueError):
            store.append(snap, ['', '', '', ''], self.root)
        self.path.with_name('~$' + self.path.name).touch()
        with self.assertRaisesRegex(ValueError, 'Close'):
            store.append(snap, ['003', '', '', ''], self.root)


if __name__ == '__main__':
    unittest.main()
