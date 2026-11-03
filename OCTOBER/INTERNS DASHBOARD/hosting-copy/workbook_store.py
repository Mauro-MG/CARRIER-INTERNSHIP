"""Local XLSX read/append operations. No cloud synchronization is implied."""
from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
from io import BytesIO
from pathlib import Path
import os
import tempfile
import uuid

from openpyxl import Workbook, load_workbook
from openpyxl.utils.cell import range_boundaries, get_column_letter


@dataclass
class Snapshot:
    path: Path
    sheet: str
    sheets: list
    headers: list
    rows: list
    digest: str


def read(path, sheet=None):
    path = Path(path).resolve()
    if path.suffix.lower() != '.xlsx':
        raise ValueError('Choose an .xlsx workbook. Macros are not supported in this prototype.')
    raw = path.read_bytes()
    wb = load_workbook(BytesIO(raw))
    try:
        ws = wb[sheet] if sheet else wb.active
        if ws.max_row > 50000 or ws.max_column > 100:
            raise ValueError('This prototype supports up to 50,000 rows and 100 columns.')
        values = list(ws.iter_rows(values_only=True))
        headers = list(values[0])
        while headers and headers[-1] is None:
            headers.pop()
        if not headers or any(not isinstance(h, str) or not h.strip() for h in headers):
            raise ValueError('Row 1 must contain a nonempty text header for every column.')
        if len(set(headers)) != len(headers):
            raise ValueError('Column headers must be unique.')
        rows = [tuple(r[:len(headers)]) for r in values[1:] if any(v is not None for v in r)]
        return Snapshot(path, ws.title, wb.sheetnames, headers, rows, sha256(raw).hexdigest())
    finally:
        wb.close()


def append(snapshot, values, backup_dir):
    if len(values) != len(snapshot.headers) or not any(v.strip() for v in values):
        raise ValueError('Enter at least one value before saving.')
    path = snapshot.path
    if path.with_name('~$' + path.name).exists():
        raise ValueError('Close this workbook in Excel before saving, then refresh.')
    raw = path.read_bytes()
    if sha256(raw).hexdigest() != snapshot.digest:
        raise ValueError('The local workbook changed. Refresh and review the data before saving again.')
    wb = load_workbook(BytesIO(raw))
    temporary = None
    try:
        ws = wb[snapshot.sheet]
        if ws.protection.sheet or ws.merged_cells:
            raise ValueError('Writing to protected sheets or sheets with merged cells is not supported.')
        tables = list(ws.tables.values())
        if len(tables) > 1:
            raise ValueError('This prototype supports only one Excel table per sheet.')
        last = max((cell.row for row in ws for cell in row if cell.value is not None), default=1)
        target = last + 1
        if tables:
            table = tables[0]
            left, top, right, bottom = range_boundaries(table.ref)
            if left != 1 or top != 1 or right != len(values) or bottom != last or table.totalsRowCount or table.totalsRowShown:
                raise ValueError('The Excel table must start at A1, cover the data, and have no totals row.')
            table.ref = f'A1:{get_column_letter(right)}{target}'
            if table.autoFilter:
                table.autoFilter.ref = table.ref
        for column, value in enumerate(values, 1):
            cell = ws.cell(target, column, value if value else None)
            if value:
                cell.data_type = 's'  # User input stays literal, including leading '=' and zeros.
        backup_dir = Path(backup_dir)
        backup_dir.mkdir(parents=True, exist_ok=True)
        backup = backup_dir / f'{path.stem}_{datetime.now():%Y%m%d_%H%M%S}_{uuid.uuid4().hex[:8]}.xlsx'
        backup.write_bytes(raw)
        fd, temporary = tempfile.mkstemp(prefix='.excel-validation-', suffix='.xlsx', dir=path.parent)
        os.close(fd)
        wb.save(temporary)
        if sha256(path.read_bytes()).hexdigest() != snapshot.digest:
            raise ValueError('The workbook changed during saving. No changes were applied; refresh first.')
        os.replace(temporary, path)
        return backup
    finally:
        wb.close()
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)


def create_sample(path):
    wb = Workbook()
    ws = wb.active
    ws.title = 'Records'
    ws.append(['Record ID', 'Name', 'Status', 'Notes'])
    ws.append(['TEST-001', 'Sample intern', 'Active', 'Initial test record'])
    from openpyxl.worksheet.table import Table, TableStyleInfo
    table = Table(displayName='Records', ref='A1:D2')
    table.tableStyleInfo = TableStyleInfo(name='TableStyleMedium2', showRowStripes=True)
    ws.add_table(table)
    wb.save(path)
    wb.close()
