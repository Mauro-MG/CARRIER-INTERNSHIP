"""Small Excel object-model fixture backed by real XLSX files, never user workbooks."""
from datetime import date, datetime
from pathlib import Path
from types import SimpleNamespace
from openpyxl import Workbook
from openpyxl.cell.cell import Cell as StoredCell
from openpyxl.utils import get_column_letter


def value2(value):
    if isinstance(value, datetime):
        value = value.date()
    if isinstance(value, date):
        return (value - date(1899, 12, 30)).days
    return value


class Cell:
    def __init__(self, worksheet, row, column):
        self.worksheet = worksheet
        self.Row, self.Column = row, column

    @property
    def cell(self):
        return self.worksheet.ws._cells.get((self.Row, self.Column)) or StoredCell(self.worksheet.ws, self.Row, self.Column)

    @property
    def HasFormula(self):
        return self.cell.data_type == 'f'

    @property
    def Value2(self):
        return value2(self.cell.value)

    @Value2.setter
    def Value2(self, value):
        cell = self.worksheet.ws.cell(self.Row, self.Column)
        cell.value = value
        if isinstance(value, str) and cell.number_format == '@':
            cell.data_type = 's'

    @property
    def NumberFormat(self):
        return self.cell.number_format

    @NumberFormat.setter
    def NumberFormat(self, value):
        self.worksheet.ws.cell(self.Row, self.Column).number_format = value


class Region:
    def __init__(self, worksheet, top, left, bottom, right):
        self.worksheet = worksheet
        self.Row, self.Column = top, left
        self.bottom, self.right = bottom, right
        self.Rows = SimpleNamespace(Count=bottom - top + 1)
        self.Columns = SimpleNamespace(Count=right - left + 1)
        self.MergeCells = False
        self.Address = f'${get_column_letter(left)}${top}:${get_column_letter(right)}${bottom}'

    def values(self, formula=False):
        result = tuple(tuple(self.worksheet.Cells(row, column).cell.value if formula else
                             self.worksheet.Cells(row, column).Value2
                             for column in range(self.Column, self.right + 1))
                       for row in range(self.Row, self.bottom + 1))
        return result[0][0] if self.Rows.Count == self.Columns.Count == 1 else result

    @property
    def Value2(self):
        return self.values()

    @property
    def Formula(self):
        return self.values(True)

    @property
    def HasFormula(self):
        flags = [self.worksheet.Cells(r, c).HasFormula
                 for r in range(self.Row, self.bottom + 1) for c in range(self.Column, self.right + 1)]
        return True if all(flags) else None if any(flags) else False


class ListColumns:
    def __init__(self, table):
        self.table = table

    def __call__(self, index):
        column = self.table.left + index - 1
        return SimpleNamespace(DataBodyRange=Region(self.table.worksheet, self.table.top + 1, column, self.table.bottom, column))

    def Add(self):
        self.table.right += 1
        table = self.table
        class Added:
            @property
            def Name(self):
                return table.worksheet.ws.cell(table.top, table.right).value
            @Name.setter
            def Name(self, value):
                table.worksheet.ws.cell(table.top, table.right, value)
        return Added()


class Table:
    def __init__(self, worksheet, top, left, bottom, right):
        self.worksheet = worksheet
        self.top, self.left, self.bottom, self.right = top, left, bottom, right
        self.Name, self.SourceType, self.ShowTotals = 'Interns', 1, False
        self.ListColumns = ListColumns(self)
        self.ListRows = self

    @property
    def Range(self):
        return Region(self.worksheet, self.top, self.left, self.bottom, self.right)

    @property
    def HeaderRowRange(self):
        return Region(self.worksheet, self.top, self.left, self.top, self.right)

    @property
    def DataBodyRange(self):
        return Region(self.worksheet, self.top + 1, self.left, self.bottom, self.right) if self.bottom > self.top else None

    def Add(self):
        self.bottom += 1
        return SimpleNamespace(Range=Region(self.worksheet, self.bottom, self.left, self.bottom, self.right))

    def __call__(self, index):
        table = self
        class Row:
            def Delete(self):
                row = table.top + index
                table.worksheet.ws.delete_rows(row, 1)
                table.bottom -= 1
        return Row()


class Collection:
    def __init__(self, values):
        self.values = values
        self.Count = len(values)
    def __iter__(self):
        return iter(self.values)
    def __call__(self, name):
        return self.values[name - 1] if isinstance(name, int) else next(v for v in self.values if v.Name == name)


class Worksheet:
    def __init__(self, ws):
        self.ws, self.Name, self.ProtectContents = ws, ws.title, False
        self.ListObjects = Collection([])
        self.QueryTables = SimpleNamespace(Count=0)
    def Cells(self, row, column):
        return Cell(self, row, column)
    def Range(self, first, last):
        return Region(self, first.Row, first.Column, last.Row, last.Column)
    def Rows(self, row):
        worksheet = self
        return SimpleNamespace(Delete=lambda: worksheet.ws.delete_rows(row, 1))
    @property
    def UsedRange(self):
        return Region(self, 1, 1, self.ws.max_row, self.ws.max_column)


class Book:
    def __init__(self, filename, headers, rows, offset_table=False):
        self.filename = Path(filename)
        self.wb = Workbook()
        self.wb.active.title = 'Interns'
        self.worksheet = Worksheet(self.wb.active)
        top, left = (5, 3) if offset_table else (1, 1)
        for r, row in enumerate([headers, *rows], top):
            for c, value in enumerate(row, left):
                self.wb.active.cell(r, c, value)
        if offset_table:
            self.worksheet.ListObjects = Collection([Table(self.worksheet, top, left, top + len(rows), left + len(headers) - 1)])
        self.Worksheets = Collection([self.worksheet])
        self.ActiveSheet = self.worksheet
        self.FullName, self.Name, self.Path = str(filename), self.filename.name, str(self.filename.parent)
        self.ReadOnly, self.Saved, self.Date1904 = False, True, False
        self.fail_save = False
        self.Save()
    def SaveCopyAs(self, filename):
        self.wb.save(filename)
    def Save(self):
        if self.fail_save:
            raise RuntimeError('Save failed')
        self.wb.save(self.filename)
        self.Saved = True


def application(book):
    def counta(region):
        return sum(book.worksheet.Cells(r, c).Value2 is not None for r in range(region.Row, region.bottom + 1)
                   for c in range(region.Column, region.right + 1))
    return SimpleNamespace(Workbooks=[book], ActiveWorkbook=book,
                           WorksheetFunction=SimpleNamespace(CountA=counta))
