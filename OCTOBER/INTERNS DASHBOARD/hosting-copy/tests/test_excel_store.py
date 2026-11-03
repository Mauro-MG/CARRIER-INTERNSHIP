import unittest
from unittest.mock import Mock, MagicMock, patch
from contextlib import contextmanager
import excel_store


class ExcelSafetyTests(unittest.TestCase):
    def test_offset_table_with_totals_and_blank_rows(self):
        book = Mock(FullName='https://example/test.xlsx')
        book.Worksheets = MagicMock()
        ws = Mock(Name='Records')
        book.Worksheets.__iter__.return_value = iter([ws])
        book.Worksheets.return_value = ws
        ws.ListObjects.Count = 1
        table = ws.ListObjects.return_value
        table.Name = 'Interns'
        table.Range.Row = 5
        table.Range.Rows.Count = 5
        table.Range.Columns.Count = 2
        table.Range.Address = '$C$5:$D$9'
        table.ShowTotals = True
        table.HeaderRowRange.Rows.Count = 1
        table.HeaderRowRange.Columns.Count = 2
        table.HeaderRowRange.Value2 = (('ID', 'Name'),)
        table.DataBodyRange.Rows.Count = 3
        table.DataBodyRange.Columns.Count = 2
        table.DataBodyRange.Value2 = (('001', 'Ana'), (None, None), ('002', 'Cass'))
        result = excel_store.snapshot(book, 'Records')
        self.assertEqual(result.headers, ['ID', 'Name'])
        self.assertEqual(len(result.rows), 3)
        self.assertEqual(result.rows[-1], ('002', 'Cass'))
        self.assertEqual(result.table_name, 'Interns')
        self.assertEqual(result.last_row, 9)

    def setUp(self):
        self.book = Mock()
        self.book.ReadOnly = False
        self.previous = excel_store.Snapshot('https://example/test.xlsx', 'Records', ['Records'], ['ID'], [], 'before', 1)

    @contextmanager
    def connection(self):
        yield Mock()

    def test_changed_data_cannot_write(self):
        with patch.object(excel_store, 'connection', self.connection), patch.object(excel_store, 'workbook', return_value=self.book), patch.object(excel_store, 'snapshot', return_value=Mock(digest='after')):
            with self.assertRaisesRegex(ValueError, 'changed'):
                excel_store.append(self.previous, ['001'], '.')
        self.book.Save.assert_not_called()
        self.book.SaveCopyAs.assert_not_called()

    def test_read_only_cannot_write(self):
        self.book.ReadOnly = True
        with patch.object(excel_store, 'connection', self.connection), patch.object(excel_store, 'workbook', return_value=self.book):
            with self.assertRaisesRegex(ValueError, 'read-only'):
                excel_store.append(self.previous, ['001'], '.')
        self.book.Save.assert_not_called()

    def test_workbook_identity_does_not_follow_active_workbook(self):
        app = Mock()
        other = Mock(FullName='other.xlsx')
        target = Mock(FullName=self.previous.path, Path='https://example')
        app.Workbooks = [other, target]
        app.ActiveWorkbook = other
        self.assertIs(excel_store.workbook(app, self.previous.path), target)
        with self.assertRaisesRegex(ValueError, 'no longer open'):
            excel_store.workbook(app, 'missing.xlsx')
