"""Intern management model over existing workbook snapshots; no replacement database."""
import calendar
from datetime import date, datetime, timedelta
import json
import os
from pathlib import Path
import re
from uuid import uuid4

from dashboard_data import as_date, display, is_date_column, normalize


# Exact aliases avoid assigning one ambiguous workbook column to multiple fields.
# A JSON override can explicitly map a canonical key to an existing column name.
FIELDS = [
    ('name', 'Full name', 'Personal', 'text', True, ('Full Name', 'Nombre completo', 'Nombre', 'Name')),
    ('email', 'Email address', 'Personal', 'email', False, ('Email', 'Email Address', 'Correo', 'Correo electrónico')),
    ('phone', 'Phone number', 'Personal', 'tel', False, ('Phone', 'Phone number', 'Personal Phone', 'Teléfono personal', 'Celular')),
    ('emergency_name', 'Emergency contact name', 'Emergency contact', 'text', False, ('Emergency Contact Name', 'Contacto de emergencia (Nombre completo)', 'Contacto de emergencia')),
    ('emergency_relationship', 'Emergency contact relationship', 'Emergency contact', 'text', False, ('Emergency Contact Relationship', 'Parentesco')),
    ('emergency_phone', 'Emergency contact phone', 'Emergency contact', 'tel', False, ('Emergency Contact Phone', 'Teléfono de emergencia', 'Número Teléfonico', 'Número Telefónico')),
    ('intern_id', 'Intern ID', 'Internship', 'text', False, ('Intern ID', 'Inter ID', 'ID de practicante', 'Record ID')),
    ('start_date', 'Internship start date', 'Internship', 'date', True, ('Start Date', 'Fecha de Ingreso', 'Fecha Ingreso', 'Joining Date', 'Hire Date')),
    ('end_date', 'Internship end date', 'Internship', 'date', False, ('End Date', 'Internship End Date', 'Fecha de salida', 'Fecha de finalización', 'Fecha de Finalización IRPAC')),
    ('department', 'Department or team', 'Internship', 'text', False, ('Department', 'Department or team', 'Departamento', 'Area', 'Área', 'Team')),
    ('role', 'Role', 'Internship', 'text', False, ('Role', 'Rol', 'Position', 'Puesto', 'Cargo')),
    ('supervisor', 'Supervisor', 'Internship', 'text', False, ('Supervisor', 'Responsable', 'Mentor', 'Jefe')),
    ('status', 'Internship status', 'Internship', 'status', False, ('Internship Status', 'Internship status', 'Status', 'Estatus', 'Estado')),
    ('university', 'University', 'Academic', 'text', False, ('University', 'Universidad', 'School', 'Educational Institution')),
    ('career', 'Degree or academic program', 'Academic', 'text', False, ('Career', 'Carrera', 'Degree', 'Major', 'Programa')),
    ('semester', 'Current semester', 'Academic', 'text', False, ('Semester', 'Current semester', 'Semestre')),
    ('insurance_provider', 'Insurance provider', 'Insurance', 'text', False, ('Insurance Provider', 'Agencia del Seguro', 'Aseguradora')),
    ('insurance_policy', 'Insurance policy number', 'Insurance', 'text', False, ('Insurance Policy Number', 'Número de Póliza', 'Póliza')),
    ('insurance_expiry', 'Insurance policy expiration date', 'Insurance', 'date', False, ('Insurance Expiration Date', 'Insurance policy expiration date', 'Vencimiento de póliza')),
    ('graduation_estimate', 'Estimated graduation date', 'Academic', 'date', False, ('Estimated Graduation Date', 'Graduation Date', 'Fecha estimada de graduación')),
    ('hire_date', 'Hire date', 'Employment', 'date', False, ('Hire Date', 'Fecha de contratación')),
    ('recruitment_source', 'Recruitment source', 'Recruitment', 'select', False, ('Recruitment Source', 'Origen de reclutamiento', 'Fuente de reclutamiento')),
    ('recruitment_source_other', 'Other recruitment source', 'Recruitment', 'text', False, ('Other Recruitment Source', 'Otro origen de reclutamiento')),
    ('employee_referral', 'Employee referral', 'Recruitment', 'text', False, ('Employee Referral', 'Referencia de empleado')),
    ('observations', 'General observations', 'Profile', 'text', False, ('Observations', 'Notes', 'Observaciones generales')),
]
RECORD_KEY = 'Intern Record Key'
STATUS_ALIASES = {'active': 'Active', 'activo': 'Active', 'activa': 'Active',
                  'completed': 'Completed', 'completado': 'Completed', 'finalizado': 'Completed',
                  'inactive': 'Inactive', 'inactivo': 'Inactive', 'inactiva': 'Inactive',
                  'candidate': 'Candidate', 'candidato': 'Candidate', 'en proceso': 'In process',
                  'intern': 'Intern', 'practicante': 'Intern', 'hired': 'Hired', 'contratado': 'Hired',
                  'graduate': 'Graduate', 'egresado': 'Graduate', 'offboarded': 'Offboarded', 'baja': 'Offboarded'}
PUBLIC_FIELDS = ('name', 'intern_id', 'start_date', 'end_date', 'department', 'role',
                 'supervisor', 'status', 'university', 'career', 'semester')
CURRENT_STATUSES = {'Active', 'Candidate', 'In process', 'Intern', 'Hired'}


def parse_date(value):
    if value is None or value == '':
        return None
    if isinstance(value, bool):
        return None
    try:
        converted = as_date(value)
        if converted:
            return converted
        text = str(value).strip()
        for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y'):
            try:
                return datetime.strptime(text, fmt).date()
            except ValueError:
                pass
    except (ValueError, OverflowError, TypeError):
        pass
    return None


def add_months(start, months):
    index = start.year * 12 + start.month - 1 + months
    year, month = divmod(index, 12)
    month += 1
    return date(year, month, min(start.day, calendar.monthrange(year, month)[1]))


def duration(start_value, end_value=None, status='Active', today=None):
    start = parse_date(start_value)
    stop = (today or date.today()) if status in CURRENT_STATUSES else parse_date(end_value)
    if not start or not stop or stop < start:
        reason = 'Start date missing or invalid' if not start else 'End date missing or invalid'
        if start and status in CURRENT_STATUSES and stop and stop < start:
            return {'months': 0, 'days': 0, 'text': 'Not started', 'asOf': stop.isoformat()}
        if start and stop and stop < start:
            reason = 'End date precedes start date'
        return {'months': None, 'days': None, 'text': reason, 'asOf': stop.isoformat() if stop else None}
    months = (stop.year - start.year) * 12 + stop.month - start.month
    if add_months(start, months) > stop:
        months -= 1
    days = (stop - add_months(start, months)).days
    return {'months': months, 'days': days, 'text': f'{months} months, {days} days', 'asOf': stop.isoformat()}


def field_mapping(headers, overrides=None):
    overrides = overrides or {}
    if set(overrides) - {field[0] for field in FIELDS}:
        raise ValueError('Field mapping contains an unknown management field.')
    normalized = {}
    for header in headers:
        normalized.setdefault(normalize(header), []).append(header)
    result, used = {}, set()
    for key, label, _group, _kind, _required, aliases in FIELDS:
        if key in overrides:
            column = overrides[key]
            if column not in headers:
                raise ValueError(f'Configured column for {label} was not found: {column}')
        else:
            candidates = []
            for alias in (label, *aliases):
                candidates = normalized.get(normalize(alias), [])
                if candidates:
                    break
            if len(candidates) > 1:
                raise ValueError(f'More than one column matches {label}. Configure an explicit field mapping.')
            column = candidates[0] if candidates else None
        if column in used:
            raise ValueError(f'{column} is assigned to more than one field. Configure an explicit field mapping.')
        result[key] = column
        if column:
            used.add(column)
    return result


def load_overrides():
    filename = os.environ.get('DASHBOARD_FIELD_MAP')
    if not filename:
        return {}
    value = json.loads(Path(filename).read_text(encoding='utf-8-sig'))
    if not isinstance(value, dict) or not all(isinstance(v, str) for v in value.values()):
        raise ValueError('DASHBOARD_FIELD_MAP must name a JSON object of field keys and workbook headers.')
    return value


class InternModel:
    def __init__(self, snapshot, overrides=None, today=None):
        self.snapshot = snapshot
        self.today = today or date.today()
        self.mapping = field_mapping(snapshot.headers, overrides)
        self.records = []
        for index, values in enumerate(snapshot.rows):
            if not any(value is not None and str(value).strip() for value in values):
                continue
            raw = dict(zip(snapshot.headers, values))
            self.records.append((index, raw))

    def schema(self):
        missing = [label for key, label, *_ in FIELDS if not self.mapping[key]]
        if RECORD_KEY not in self.snapshot.headers:
            missing.append(RECORD_KEY)
        required_missing = [label for key, label, _group, _kind, required, _ in FIELDS
                            if required and not self.mapping[key]]
        # A status column is needed to preserve participant history safely, and the
        # stable key prevents an edit/delete from targeting a shifted Excel row.
        if not self.mapping['status']:
            required_missing.append('Internship status')
        if RECORD_KEY not in self.snapshot.headers:
            required_missing.append(RECORD_KEY)
        keys = [str(raw.get(RECORD_KEY) or '').strip() for _, raw in self.records]
        valid_keys = bool(RECORD_KEY in self.snapshot.headers) and all(keys) and len(keys) == len(set(keys))
        if RECORD_KEY in self.snapshot.headers and not valid_keys and any(keys):
            nonempty = [key for key in keys if key]
            if len(nonempty) != len(set(nonempty)):
                raise ValueError('Duplicate Intern Record Keys. Resolve these in Excel before editing.')
        fields = [{'key': key, 'label': label, 'group': group, 'type': kind,
                   'required': required, 'column': self.mapping[key], 'sensitive': key not in PUBLIC_FIELDS}
                  for key, label, group, kind, required, _ in FIELDS]
        used = set(self.mapping.values()) | {RECORD_KEY}
        return {'fields': fields, 'missingColumns': missing, 'requiredMissing': required_missing,
                'optionalMissing': [label for label in missing if label not in required_missing],
                'ready': not required_missing and valid_keys,
                'revision': self.snapshot.digest,
                'extraColumns': [header for header in self.snapshot.headers if header not in used],
                'extraFields': [{'key': header, 'label': header, 'type': 'date' if is_date_column(header) else 'text'}
                                for header in self.snapshot.headers if header not in used]}

    def identity(self, index, raw):
        return str(raw.get(RECORD_KEY) or f'legacy-{index}').strip()

    def values(self, raw):
        result = {}
        for key, _label, _group, kind, _required, _ in FIELDS:
            value = raw.get(self.mapping[key], '')
            if kind == 'date' and parse_date(value):
                value = parse_date(value).isoformat()
            elif value is None:
                value = ''
            else:
                value = str(value).strip()
            if key == 'status':
                value = STATUS_ALIASES.get(normalize(value), value or 'Active')
            result[key] = value
        return result

    def row(self, index, raw):
        values = self.values(raw)
        return {'id': self.identity(index, raw), **{key: values[key] for key in PUBLIC_FIELDS},
                'duration': duration(values['start_date'], values['end_date'], values['status'], self.today)}

    def list(self, query):
        status = query.get('status', 'Active')
        statuses = ('Active', 'Completed', 'Inactive', 'Candidate', 'In process', 'Intern', 'Hired', 'Graduate', 'Offboarded')
        if status not in ('All', 'Former', *statuses):
            raise ValueError('Choose a valid status filter.')
        search = normalize(query.get('search', ''))
        rows = [self.row(index, raw) for index, raw in self.records]
        counts = {label: sum(row['status'] == label for row in rows) for label in statuses}
        if status == 'Former':
            rows = [row for row in rows if row['status'] != 'Active']
        elif status != 'All':
            rows = [row for row in rows if row['status'] == status]
        if search:
            rows = [row for row in rows if search in normalize(' '.join(str(row[key]) for key in PUBLIC_FIELDS))]
        sort = query.get('sort', 'name')
        if sort not in ('name', 'start_date', 'duration'):
            raise ValueError('Choose a valid sort order.')
        direction = query.get('direction', 'asc')
        if direction not in ('asc', 'desc'):
            raise ValueError('Choose a valid sort direction.')
        def sort_value(row):
            if sort == 'start_date':
                return parse_date(row['start_date'])
            if sort == 'duration':
                return (row['duration']['months'], row['duration']['days']) if row['duration']['months'] is not None else None
            return row['name'].casefold()
        known = [row for row in rows if sort_value(row) is not None]
        unknown = [row for row in rows if sort_value(row) is None]
        rows = sorted(known, key=lambda row: (sort_value(row), row['name'].casefold()), reverse=direction == 'desc') + unknown
        try:
            page, page_size = int(query.get('page', 1)), int(query.get('pageSize', 25))
        except (ValueError, TypeError):
            raise ValueError('Choose a valid table page.')
        if page < 1 or page_size not in (10, 25, 50, 100):
            raise ValueError('Choose a valid table page.')
        return {'rows': rows[(page - 1) * page_size:page * page_size], 'total': len(rows),
                'page': page, 'pageSize': page_size, 'counts': counts, 'asOf': self.today.isoformat(),
                'schema': self.schema(), 'connected': True}

    def locate(self, record_id):
        matches = [(index, raw) for index, raw in self.records if self.identity(index, raw) == record_id]
        if len(matches) != 1:
            raise ValueError('Intern record was not found uniquely. Refresh and try again.')
        return matches[0]

    def detail(self, record_id):
        index, raw = self.locate(record_id)
        used = set(self.mapping.values()) | {RECORD_KEY}
        extras = {column: parse_date(raw.get(column)).isoformat() if is_date_column(column) and parse_date(raw.get(column))
                  else display(raw.get(column), column) if raw.get(column) is not None else ''
                  for column in self.snapshot.headers if column not in used}
        # The old manually maintained Months column is kept, but never edited here.
        return {'record': self.row(index, raw), 'values': self.values(raw), 'extra': extras,
                'schema': self.schema()}

    def validate(self, fields, extras=None, record_id=None):
        if not isinstance(fields, dict) or not all(isinstance(key, str) and isinstance(value, str) for key, value in fields.items()):
            raise ValueError('Intern fields must be text values.')
        if set(fields) - set(self.mapping):
            raise ValueError('Unknown intern field.')
        extras = extras or {}
        if not isinstance(extras, dict) or not all(isinstance(value, str) for value in extras.values()):
            raise ValueError('Administrative fields must be text values.')
        used = set(self.mapping.values()) | {RECORD_KEY}
        allowed_extra = set(self.snapshot.headers) - used
        if set(extras) - allowed_extra or any(normalize(key) in ('months', 'monthsasintern') for key in extras):
            raise ValueError('Unknown or read-only administrative field.')
        old = self.values(self.locate(record_id)[1]) if record_id else {}
        merged = {**old, **{key: value.strip() for key, value in fields.items()}}
        if not record_id:
            merged.setdefault('status', 'Active')
        changes = {}
        for key, label, _group, kind, required, _ in FIELDS:
            value = merged.get(key, '')
            if len(value) > 2000:
                raise ValueError(f'{label} must be no longer than 2,000 characters.')
            if required and (not record_id or key in fields) and not value:
                raise ValueError(f'{label} is required.')
            if not record_id and key not in fields and key != 'status':
                continue
            if record_id and key not in fields:
                continue
            if kind == 'date' and value:
                converted = parse_date(value)
                if not converted or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
                    raise ValueError(f'{label} must be a valid date (YYYY-MM-DD).')
                value = converted
            if kind == 'email' and value and not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', value):
                raise ValueError('Enter a valid email address.')
            if kind == 'status' and value not in ('Active', 'Completed', 'Inactive', 'Candidate', 'In process', 'Intern', 'Hired', 'Graduate', 'Offboarded'):
                raise ValueError('Choose a valid participant status.')
            if not self.mapping[key]:
                if value:
                    raise ValueError(f'{label} is not available in this workbook. Add the column in Excel first.')
                continue
            changes[self.mapping[key]] = value if value != '' else None
        if not record_id or set(fields) & {'start_date', 'end_date', 'status'}:
            start, end = parse_date(merged.get('start_date')), parse_date(merged.get('end_date'))
            if merged.get('status') not in CURRENT_STATUSES and not end:
                raise ValueError('An end date is required for former participants.')
            if start and end and end < start:
                raise ValueError('Internship end date cannot precede the start date.')
            if merged.get('status') not in CURRENT_STATUSES and end and end > self.today:
                raise ValueError('A departing intern’s end date cannot be in the future.')
        for column, value in extras.items():
            if len(value) > 2000:
                raise ValueError(f'{column} must be no longer than 2,000 characters.')
            if value and is_date_column(column):
                parsed = parse_date(value)
                if not parsed or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
                    raise ValueError(f'{column} must be a valid date (YYYY-MM-DD).')
                value = parsed
            changes[column] = value if value else None
        if not record_id:
            changes[RECORD_KEY] = str(uuid4())
        return changes
