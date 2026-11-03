"""Pure dashboard transformations, kept independent from Excel and the UI."""
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, timedelta
import re
import unicodedata


def normalize(value):
    value = unicodedata.normalize('NFKD', str(value or ''))
    value = ''.join(char for char in value if not unicodedata.combining(char))
    return re.sub(r'[^a-z0-9]+', '', value.lower())


FIELD_ALIASES = {
    'name': ('fullname', 'nombrecompleto', 'name', 'nombre'),
    'role': ('role', 'rol', 'puesto', 'internrole', 'position', 'cargo'),
    'university': ('university', 'universidad', 'school'),
    'manager': ('manager', 'gerente', 'peoplemanager', 'linemanager'),
    'supervisor': ('supervisor', 'responsable', 'jefe', 'mentor'),
    'start_date': ('startdate', 'fechadeingreso', 'fechaingreso', 'joiningdate', 'hiredate'),
    'birth_date': ('birthdate', 'fechadenacimiento', 'fechanacimiento', 'dateofbirth', 'dob'),
    'gender': ('gender', 'genero', 'sexo'),
    'career': ('career', 'carrera', 'degree', 'major', 'programa'),
}


def find_column(headers, field):
    normalized = {normalize(header): header for header in headers}
    for alias in FIELD_ALIASES[field]:
        if alias in normalized:
            return normalized[alias]
    for alias in FIELD_ALIASES[field]:
        match = next((header for key, header in normalized.items() if alias in key), None)
        if match:
            return match
    return None


def is_date_column(column):
    normalized = normalize(column)
    return 'fecha' in normalized or 'date' in normalized or normalized in FIELD_ALIASES['birth_date']


def as_date(value):
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, (int, float)) and 1 <= value <= 100000:
        # Excel's 1900 date system, including Excel's historical day-60 behavior.
        return (datetime(1899, 12, 30) + timedelta(days=value)).date()
    return None


def display(value, column=None):
    if value is None or str(value).strip() == '':
        return 'Not specified'
    converted = as_date(value) if is_date_column(column) else None
    if converted:
        return converted.strftime('%d/%m/%Y')
    if isinstance(value, (datetime, date)):
        return value.strftime('%d/%m/%Y')
    return str(value).strip()


def counter(records, column, limit=8):
    if not column:
        return []
    values = Counter(display(row.get(column), column) for row in records)
    return sorted(values.items(), key=lambda item: (-item[1], item[0].casefold()))[:limit]


@dataclass(frozen=True)
class Dashboard:
    headers: list
    records: list
    columns: dict

    @classmethod
    def from_snapshot(cls, snapshot):
        records = [dict(zip(snapshot.headers, row)) for row in snapshot.rows]
        return cls(snapshot.headers, records, {field: find_column(snapshot.headers, field) for field in FIELD_ALIASES})

    def choices(self, field):
        column = self.columns.get(field)
        return ['All'] + [label for label, _ in counter(self.records, column, limit=1000)]

    def filtered(self, filters):
        result = self.records
        for field, selected in filters.items():
            column = self.columns.get(field)
            if column and selected and selected != 'All':
                result = [row for row in result if display(row.get(column), column) == selected]
        return result

    def metrics(self, records):
        return [
            ('Total interns', len(records)),
            ('Universities', len({display(row.get(self.columns['university']), self.columns['university']) for row in records}) if self.columns['university'] else '—'),
            ('Managers', len({display(row.get(self.columns['manager']), self.columns['manager']) for row in records}) if self.columns['manager'] else '—'),
            ('Supervisors', len({display(row.get(self.columns['supervisor']), self.columns['supervisor']) for row in records}) if self.columns['supervisor'] else '—'),
            ('Careers', len({display(row.get(self.columns['career']), self.columns['career']) for row in records}) if self.columns['career'] else '—'),
        ]

    def charts(self, records):
        return {key: counter(records, self.columns[key]) for key in ('role', 'gender', 'university', 'supervisor', 'career')}

    def recent(self, records, limit=8):
        name, start = self.columns['name'], self.columns['start_date']
        if start:
            records = sorted(records, key=lambda record: as_date(record.get(start)) or date.min, reverse=True)
        return records[:limit], [column for column in (name, start, self.columns['role'], self.columns['university']) if column]
