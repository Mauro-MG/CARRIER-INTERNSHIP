"""Attach to an already-open Excel instance; never open or close user workbooks."""
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
from pathlib import Path
import uuid


@dataclass
class Snapshot:
    path: str
    sheet: str
    sheets: list
    headers: list
    rows: list
    digest: str
    last_row: int
    source: str = 'excel'
    table_name: str = ''


def matrix(region):
    if region is None:
        return ()
    value = region.Value2
    return ((value,),) if region.Rows.Count == region.Columns.Count == 1 else value


@contextmanager
def connection():
    try:
        import pythoncom
        import win32com.client
    except ImportError as exc:
        raise RuntimeError('Install Excel support: python -m pip install pywin32') from exc
    pythoncom.CoInitialize()
    application = None
    try:
        try:
            application = win32com.client.GetActiveObject('Excel.Application')
        except Exception as exc:
            raise RuntimeError('Open the original workbook in desktop Excel, switch back to this app, then connect. If Excel was just opened, try again.') from exc
        yield application
    finally:
        application = None
        pythoncom.CoUninitialize()


def workbook(application, path=None):
    if path is None:
        book = application.ActiveWorkbook
        if book is None:
            raise ValueError('No active workbook. Select your workbook in Excel first.')
    else:
        book = next((b for b in application.Workbooks if b.FullName == path), None)
        if book is None:
            raise ValueError('The connected workbook is no longer open in this Excel instance. Reconnect to it.')
    if not book.Path:
        raise ValueError('Save the workbook in Excel before connecting.')
    return book


def snapshot(book, sheet=None):
    sheets = [s.Name for s in book.Worksheets]
    name = sheet or book.ActiveSheet.Name
    if name not in sheets:
        raise ValueError('Select a data worksheet in Excel before connecting.')
    ws = book.Worksheets(name)
    if ws.ListObjects.Count > 1:
        raise ValueError('Only one data table per sheet is supported. Select a sheet with one table.')
    if ws.ListObjects.Count == 1:
        table = ws.ListObjects(1)
        if table.Range.Rows.Count > 50000 or table.Range.Columns.Count > 100:
            raise ValueError('This prototype supports up to 50,000 rows and 100 columns.')
        if table.HeaderRowRange is None:
            raise ValueError('Show the table header row in Excel before connecting.')
        headers = list(matrix(table.HeaderRowRange)[0])
        if any(not isinstance(h, str) or not h.strip() for h in headers) or len(set(headers)) != len(headers):
            raise ValueError('The table needs unique, nonempty text headers.')
        rows = list(matrix(table.DataBodyRange))
        identity = (table.Name, table.Range.Address, table.ShowTotals, table.Range.Value2, table.Range.Formula)
        digest = sha256(repr(identity).encode('utf-8')).hexdigest()
        return Snapshot(book.FullName, name, sheets, headers, rows, digest,
                        table.Range.Row + table.Range.Rows.Count - 1, table_name=table.Name)
    used = ws.UsedRange
    last_row = used.Row + used.Rows.Count - 1
    last_column = used.Column + used.Columns.Count - 1
    if last_row > 50000 or last_column > 100:
        raise ValueError('This prototype supports up to 50,000 used rows and 100 columns.')
    region = ws.Range(ws.Cells(1, 1), ws.Cells(last_row, last_column))
    values = region.Value2
    formulas = region.Formula
    if last_row == last_column == 1:
        values = ((values,),)
    headers = list(values[0])
    while headers and headers[-1] is None:
        headers.pop()
    if not headers or any(not isinstance(h, str) or not h.strip() for h in headers) or len(set(headers)) != len(headers):
        raise ValueError('Row 1 must have unique, nonempty text headers. Select the data worksheet.')
    if any(any(v is not None for v in row[len(headers):]) for row in values[1:]):
        raise ValueError('There is data outside the header columns. Use a rectangular data sheet.')
    last_data = max((i for i, row in enumerate(values, 1) if any(v is not None for v in row)), default=1)
    rows = [tuple(row[:len(headers)]) for row in values[1:] if any(v is not None for v in row)]
    digest = sha256(repr((values, formulas)).encode('utf-8')).hexdigest()
    return Snapshot(book.FullName, name, sheets, headers, rows, digest, last_data)


def read(path=None, sheet=None):
    with connection() as application:
        book = workbook(application, path)
        try:
            return snapshot(book, sheet)
        finally:
            book = None


def append(previous, values, backup_dir):
    if len(values) != len(previous.headers) or not any(v.strip() for v in values):
        raise ValueError('Enter at least one value before saving.')
    with connection() as application:
        book = workbook(application, previous.path)
        ws = target = table = None
        try:
            if book.ReadOnly:
                raise ValueError('Excel opened this workbook read-only. Enable editing in Excel first.')
            if snapshot(book, previous.sheet).digest != previous.digest:
                raise ValueError('The workbook changed. Refresh and review before saving.')
            ws = book.Worksheets(previous.sheet)
            if ws.ProtectContents:
                raise ValueError('Protected sheets are not supported for writing.')
            if ws.QueryTables.Count:
                raise ValueError('This sheet contains imported query data. Connect to the original source workbook instead.')
            if ws.ListObjects.Count > 1:
                raise ValueError('Only one data table per sheet is supported.')
            if ws.ListObjects.Count:
                table = ws.ListObjects(1)
                if table.SourceType != 1:
                    raise ValueError('Imported or linked tables cannot be edited here. Open the source workbook.')
                if table.Name != previous.table_name or table.Range.Columns.Count != len(values):
                    raise ValueError('The table layout changed. Refresh before saving.')
            elif previous.table_name:
                raise ValueError('The connected table was removed. Refresh before saving.')
            elif ws.UsedRange.MergeCells is not False:
                raise ValueError('Merged cells are not supported for writing to a plain sheet.')
            backups = Path(backup_dir)
            backups.mkdir(parents=True, exist_ok=True)
            backup = backups / f'{Path(book.Name).stem}_{datetime.now():%Y%m%d_%H%M%S}_{uuid.uuid4().hex[:8]}{Path(book.Name).suffix}'
            book.SaveCopyAs(str(backup.resolve()))
            if snapshot(book, previous.sheet).digest != previous.digest:
                raise ValueError('The workbook changed during backup. Refresh before saving.')
            try:
                if table is not None:
                    target = table.ListRows.Add().Range
                else:
                    row = previous.last_row + 1
                    target = ws.Range(ws.Cells(row, 1), ws.Cells(row, len(values)))
                target.NumberFormat = '@'
                target.Value2 = (tuple(values),)
                book.Save()
                if not book.Saved:
                    raise RuntimeError('Excel did not confirm the save.')
            except Exception as exc:
                # AutoSave may already have propagated the edit. Never retry or roll back blindly.
                raise RuntimeError('The row may already be in Excel. Inspect the workbook and refresh before submitting again. Excel may need you to resolve a save prompt. Backup: ' + str(backup)) from exc
            return backup
        finally:
            target = table = ws = book = None
