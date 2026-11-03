"""Additive management writes using the original Excel connection and snapshots."""
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path
import os
from uuid import uuid4

import excel_store
from intern_management import InternModel, RECORD_KEY, normalize


@contextmanager
def writable(previous, backup_dir=None):
    """Shared preflight; never retry/roll back a potentially AutoSaved mutation."""
    with excel_store.connection() as application:
        book = excel_store.workbook(application, previous.path)
        if book.ReadOnly:
            raise ValueError('Excel opened this workbook read-only. Enable editing in Excel first.')
        current = excel_store.snapshot(book, previous.sheet)
        if current.digest != previous.digest:
            raise ValueError('The workbook changed. Refresh and review before saving.')
        ws = book.Worksheets(previous.sheet)
        if ws.ProtectContents or ws.UsedRange.MergeCells is not False:
            raise ValueError('Protected sheets and merged cells are not supported for management writes.')
        if ws.QueryTables.Count:
            raise ValueError('Imported query data cannot be edited. Connect to the original source workbook.')
        table = ws.ListObjects(1) if ws.ListObjects.Count else None
        if table is not None and (table.SourceType != 1 or table.Name != previous.table_name):
            raise ValueError('Imported tables or changed table layouts cannot be edited here.')
        backups = Path(backup_dir or os.environ.get('DASHBOARD_BACKUP_DIR') or
                       Path(os.environ.get('LOCALAPPDATA', str(Path.home()))) / 'ExcelConnectionTester' / 'backups')
        backups.mkdir(parents=True, exist_ok=True)
        backup = backups / f'{Path(book.Name).stem}_management_{datetime.now():%Y%m%d_%H%M%S}_{uuid4().hex[:8]}{Path(book.Name).suffix}'
        # Caller completes all validation before requesting this backup/mutation.
        yield application, book, ws, table, current, backup


def begin(book, previous, backup):
    book.SaveCopyAs(str(backup.resolve()))
    if excel_store.snapshot(book, previous.sheet).digest != previous.digest:
        raise ValueError('The workbook changed during backup. Refresh before saving.')


def finish(book, previous):
    book.Save()
    if not book.Saved:
        raise RuntimeError('Excel did not confirm the save.')
    return excel_store.snapshot(book, previous.sheet)


def uncertain(error, backup):
    return RuntimeError('The change may already be in Excel. Inspect the workbook and refresh before trying again. '
                        f'No automatic retry or rollback was attempted. Backup: {backup}')


def physical_rows(ws, table, current):
    if table is not None:
        return [table.DataBodyRange.Row + i for i in range(len(current.rows))] if current.rows else []
    values = ws.Range(ws.Cells(1, 1), ws.Cells(current.last_row, len(current.headers))).Value2
    if current.last_row == len(current.headers) == 1:
        values = ((values,),)
    return [i for i, row in enumerate(values, 1) if i > 1 and any(v is not None for v in row)]


def cell_value(cell, value):
    if isinstance(value, date):
        cell.NumberFormat = 'dd/mm/yyyy'
        cell.Value2 = (value - date(1899, 12, 30)).days
    else:
        cell.NumberFormat = '@'
        cell.Value2 = value


def check_date_system(book, changes):
    if book.Date1904 and any(isinstance(value, date) for value in changes.values()):
        raise ValueError('Management date writes require the workbook’s 1900 date system.')


def migrate(previous, overrides=None, backup_dir=None):
    with writable(previous, backup_dir) as (application, book, ws, table, current, backup):
        model = InternModel(current, overrides)
        plan = model.schema()
        missing = plan['missingColumns']
        if plan['ready']:
            return current, None
        if len(current.headers) + len(missing) > 100:
            raise ValueError('The migration would exceed the existing 100-column workbook limit.')
        positions = physical_rows(ws, table, current)
        first_column = table.Range.Column if table is not None else 1
        first_row = table.Range.Row if table is not None else 1
        if missing:
            next_column = first_column + len(current.headers)
            adjacent = ws.Range(ws.Cells(first_row, next_column),
                                ws.Cells(max(current.last_row, first_row), next_column + len(missing) - 1))
            if application.WorksheetFunction.CountA(adjacent) or adjacent.MergeCells is not False:
                raise ValueError('New columns would overlap existing cells. Move adjacent data in Excel first.')
        if RECORD_KEY in current.headers:
            for index, raw in model.records:
                if not str(raw.get(RECORD_KEY) or '').strip() and ws.Cells(positions[index], first_column + current.headers.index(RECORD_KEY)).HasFormula:
                    raise ValueError('A missing record key contains a formula. Resolve it in Excel first.')
        begin(book, previous, backup)
        try:
            headers = list(current.headers)
            for header in missing:
                if table is not None:
                    table.ListColumns.Add().Name = header
                else:
                    cell_value(ws.Cells(1, len(headers) + 1), header)
                headers.append(header)
            key_column = first_column + headers.index(RECORD_KEY)
            status_header = model.mapping['status'] or next(field['label'] for field in plan['fields'] if field['key'] == 'status')
            status_column = first_column + headers.index(status_header)
            for (index, raw), row_number in zip(enumerate(current.rows), positions):
                if not any(value is not None and str(value).strip() for value in raw):
                    continue
                previous_values = dict(zip(current.headers, raw))
                if not str(previous_values.get(RECORD_KEY) or '').strip():
                    cell_value(ws.Cells(row_number, key_column), str(uuid4()))
                if status_header not in current.headers:
                    cell_value(ws.Cells(row_number, status_column), 'Active')
            return finish(book, previous), backup
        except Exception as error:
            raise uncertain(error, backup) from error


def save(previous, changes, record_id=None, overrides=None, backup_dir=None):
    with writable(previous, backup_dir) as (_application, book, ws, table, current, backup):
        model = InternModel(current, overrides)
        if not model.schema()['ready']:
            raise ValueError('Prepare the workbook fields before saving interns.')
        if not changes:
            return current, None
        if set(changes) - set(current.headers):
            raise ValueError('The workbook layout changed. Refresh before saving.')
        check_date_system(book, changes)
        first_column = table.Range.Column if table is not None else 1
        row_number = None
        if record_id:
            index, _raw = model.locate(record_id)
            row_number = physical_rows(ws, table, current)[index]
            if RECORD_KEY in changes:
                raise ValueError('Intern record keys cannot be edited.')
            for header in changes:
                if ws.Cells(row_number, first_column + current.headers.index(header)).HasFormula:
                    raise ValueError(f'{header} contains an Excel formula and is read-only here.')
        else:
            if current.last_row >= 50000:
                raise ValueError('The workbook has reached the existing 50,000-row limit.')
            if not changes.get(RECORD_KEY):
                raise ValueError('A new intern needs a record key.')
            if table is not None and current.rows:
                for header in changes:
                    if table.ListColumns(current.headers.index(header) + 1).DataBodyRange.HasFormula is not False:
                        raise ValueError(f'{header} is a calculated Excel column and cannot be written here.')
        begin(book, previous, backup)
        try:
            if row_number is None:
                row_number = table.ListRows.Add().Range.Row if table is not None else current.last_row + 1
            for header, value in changes.items():
                cell_value(ws.Cells(row_number, first_column + current.headers.index(header)), value)
            return finish(book, previous), backup
        except Exception as error:
            raise uncertain(error, backup) from error


def delete(previous, record_id, overrides=None, backup_dir=None):
    """Remove one identified workbook record after taking the normal recovery backup."""
    with writable(previous, backup_dir) as (_application, book, ws, table, current, backup):
        model = InternModel(current, overrides)
        if not model.schema()['ready']:
            raise ValueError('Prepare the workbook fields before deleting interns.')
        index, _raw = model.locate(record_id)
        positions = physical_rows(ws, table, current)
        if index >= len(positions):
            raise ValueError('Intern record location changed. Refresh and try again.')
        row_number = positions[index]
        begin(book, previous, backup)
        try:
            if table is not None:
                # Excel ListRows is one-based and preserves the table around the remaining records.
                table.ListRows(index + 1).Delete()
            else:
                ws.Rows(row_number).Delete()
            return finish(book, previous), backup
        except Exception as error:
            raise uncertain(error, backup) from error
