from contextlib import contextmanager
from datetime import date
from pathlib import Path
import shutil
import unittest
from unittest.mock import patch
from uuid import uuid4
from openpyxl import load_workbook

import excel_store
import excel_management
from dashboard_bridge import DashboardBridge
from intern_management import InternModel, FIELDS, RECORD_KEY, duration, field_mapping
from fake_excel import Book, application


class DurationTests(unittest.TestCase):
    def test_partial_month_calendar_boundaries_and_leap_years(self):
        for start, stop, months, days in [
            ('2026-01-15', '2026-02-14', 0, 30),
            ('2026-01-15', '2026-02-15', 1, 0),
            ('2026-01-31', '2026-02-28', 1, 0),
            ('2024-01-31', '2024-02-29', 1, 0),
            ('2024-02-29', '2025-02-28', 12, 0),
            ('2026-01-31', '2026-03-30', 1, 30),
            ('2026-01-01', '2026-10-14', 9, 13),
        ]:
            with self.subTest(start=start, stop=stop):
                result = duration(start, today=date.fromisoformat(stop))
                self.assertEqual((result['months'], result['days']), (months, days))

    def test_former_intern_duration_stops_at_end_and_active_changes_over_time(self):
        for status in ('Completed', 'Inactive'):
            first = duration('2026-01-01', '2026-04-12', status, date(2026, 5, 1))
            later = duration('2026-01-01', '2026-04-12', status, date(2026, 10, 1))
            self.assertEqual(first, later)
            self.assertEqual((first['months'], first['days']), (3, 11))
        self.assertEqual(duration('2026-01-01', today=date(2026, 2, 1))['months'], 1)
        self.assertEqual(duration('2026-01-01', today=date(2026, 3, 1))['months'], 2)

    def test_missing_invalid_reversed_and_future_dates(self):
        for start in ('', 'bad', '2026-02-30', True):
            self.assertIsNone(duration(start, today=date(2026, 10, 1))['months'])
        self.assertIsNone(duration('2026-01-01', '', 'Completed')['months'])
        self.assertIsNone(duration('2026-02-01', '2026-01-01', 'Inactive')['months'])
        self.assertEqual(duration('2027-01-01', today=date(2026, 10, 1))['text'], 'Not started')


class ManagementPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(__file__).resolve().parent / ('run_' + uuid4().hex)
        self.root.mkdir()
        self.addCleanup(shutil.rmtree, self.root)
        self.book = Book(self.root / 'interns.xlsx',
                         ['Full Name', 'Fecha de Ingreso', 'Universidad', 'Contacto de emergencia (Nombre completo)',
                          'Parentesco', 'Número Teléfonico', 'Agencia del Seguro', 'Número de Póliza', 'Months', 'Legacy Notes'],
                         [('Ana', 46023, 'UANL', 'Emergency Person', 'Sibling', '001555', 'Provider', '001234', 42, '=1+1')],
                         offset_table=True)
        self.app = application(self.book)
        @contextmanager
        def connection():
            yield self.app
        self.patch = patch('excel_store.connection', connection)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.backups = self.root / 'backups'
        self.envpatch = patch.dict('os.environ', {'DASHBOARD_BACKUP_DIR': str(self.backups)})
        self.envpatch.start()
        self.addCleanup(self.envpatch.stop)

    def read(self):
        return excel_store.read(str(self.book.filename), 'Interns')

    def prepare(self):
        return excel_management.migrate(self.read(), backup_dir=self.backups)[0]

    def test_migration_preserves_every_existing_value_and_reuses_emergency_insurance_columns(self):
        before = self.read()
        after, backup = excel_management.migrate(before, backup_dir=self.backups)
        self.assertEqual(after.rows[0][:len(before.headers)], before.rows[0])
        self.assertEqual(after.headers[:len(before.headers)], before.headers)
        model = InternModel(after)
        self.assertTrue(model.schema()['ready'])
        self.assertEqual(model.mapping['insurance_policy'], 'Número de Póliza')
        self.assertEqual(model.mapping['emergency_phone'], 'Número Teléfonico')
        self.assertNotIn('Emergency contact name', after.headers)
        self.assertEqual(model.values(dict(zip(after.headers, after.rows[0])))['status'], 'Active')
        self.assertTrue(backup.exists())
        second, second_backup = excel_management.migrate(after, backup_dir=self.backups)
        self.assertIsNone(second_backup)
        self.assertEqual(second.digest, after.digest)

    def test_create_edit_complete_and_retrieve_persisted_information(self):
        snapshot = self.prepare()
        model = InternModel(snapshot, today=date(2026, 10, 14))
        fields = {field[0]: '' for field in FIELDS}
        fields.update(name='New Intern', start_date='2026-02-28', status='Active', email='intern@example.com',
                      phone='00123', emergency_name='Contact', emergency_relationship='Parent', emergency_phone='00555',
                      department='Engineering', university='TEC', career='Engineering', semester='6',
                      insurance_provider='Health Co', insurance_policy='00009', insurance_expiry='2027-02-28')
        changes = model.validate(fields)
        added, _ = excel_management.save(snapshot, changes, backup_dir=self.backups)
        self.assertEqual(len(added.rows), 2)
        new_id = changes[RECORD_KEY]
        detail = InternModel(self.read()).detail(new_id)
        self.assertEqual(detail['values']['insurance_policy'], '00009')
        self.assertEqual(detail['values']['emergency_phone'], '00555')
        self.assertEqual(detail['values']['phone'], '00123')
        self.assertEqual(detail['values']['insurance_expiry'], '2027-02-28')
        edits = InternModel(added, today=date(2026, 10, 14)).validate({'name': 'Updated Intern'}, record_id=new_id)
        edited, _ = excel_management.save(added, edits, new_id, backup_dir=self.backups)
        self.assertEqual(InternModel(edited).detail(new_id)['values']['insurance_policy'], '00009')
        self.assertEqual(edited.rows[0][:10], snapshot.rows[0][:10])
        changes = InternModel(edited, today=date(2026, 10, 14)).validate({'status': 'Completed', 'end_date': '2026-08-28'}, record_id=new_id)
        completed, _ = excel_management.save(edited, changes, new_id, backup_dir=self.backups)
        current = InternModel(self.read(), today=date(2026, 10, 14))
        self.assertEqual(current.list({'status': 'Active'})['total'], 1)
        former = current.list({'status': 'Former'})
        self.assertEqual(former['total'], 1)
        self.assertEqual(former['rows'][0]['duration']['months'], 6)
        self.assertEqual(len(completed.rows), 2)
        raw = load_workbook(self.book.filename)
        self.addCleanup(raw.close)
        self.assertEqual(raw['Interns']['L6'].value, '=1+1')

    def test_plain_sheet_blank_rows_preserve_physical_row_and_literal_text(self):
        self.book = Book(self.root / 'plain.xlsx', ['Full Name', 'Start Date'], [('Ana', 46023), (None, None), ('Bob', 46054)])
        self.app = application(self.book)
        snapshot = self.prepare()
        model = InternModel(snapshot)
        bob = model.list({'search': 'Bob'})['rows'][0]
        changed = model.validate({'name': '=literal'}, record_id=bob['id'])
        excel_management.save(snapshot, changed, bob['id'], backup_dir=self.backups)
        raw = load_workbook(self.book.filename)
        self.addCleanup(raw.close)
        self.assertIsNone(raw.active['A3'].value)
        self.assertEqual(raw.active['A4'].value, '=literal')
        self.assertEqual(raw.active['A4'].data_type, 's')

    def test_delete_removes_only_the_selected_record_and_keeps_a_backup(self):
        snapshot = self.prepare()
        model = InternModel(snapshot)
        record_id = model.list({})['rows'][0]['id']
        updated, backup = excel_management.delete(snapshot, record_id, backup_dir=self.backups)
        self.assertEqual(updated.rows, [])
        self.assertTrue(backup.exists())
        with self.assertRaisesRegex(ValueError, 'not found'):
            InternModel(updated).detail(record_id)

    def test_stale_snapshot_and_formula_edits_are_blocked_without_changing_existing_data(self):
        snapshot = self.prepare()
        model = InternModel(snapshot)
        record_id = model.list({})['rows'][0]['id']
        with self.assertRaisesRegex(ValueError, 'formula'):
            excel_management.save(snapshot, {'Legacy Notes': 'Replace'}, record_id, backup_dir=self.backups)
        self.book.worksheet.ws['C6'] = 'External edit'
        with self.assertRaisesRegex(ValueError, 'changed'):
            excel_management.save(snapshot, {'Full Name': 'Oops'}, record_id, backup_dir=self.backups)
        self.assertEqual(self.book.worksheet.ws['C6'].value, 'External edit')

    def test_invalid_required_fields_status_dates_and_extra_fields_are_rejected(self):
        model = InternModel(self.prepare(), today=date(2026, 10, 14))
        base = {'name': 'New', 'start_date': '2026-01-01'}
        for fields in ({'name': ''}, {**base, 'email': 'bad'}, {**base, 'start_date': '2026-02-30'},
                       {**base, 'status': 'Completed'}, {**base, 'end_date': '2025-01-01'},
                       {**base, 'status': 'Inactive', 'end_date': '2027-01-01'}, {**base, 'other': 'x'}):
            with self.subTest(fields=fields), self.assertRaises(ValueError):
                model.validate(fields)
        with self.assertRaises(ValueError):
            model.validate(base, {'Months': '100'})
        with self.assertRaises(ValueError):
            model.validate(base, {'Unknown': 'x'})

    def test_optional_columns_do_not_block_registration(self):
        self.book = Book(self.root / 'minimal.xlsx',
                         ['Full Name', 'Start Date', 'Internship Status', RECORD_KEY],
                         [('Existing Intern', date(2026, 1, 1), 'Active', str(uuid4()))], offset_table=True)
        self.app = application(self.book)
        snapshot = self.read()
        model = InternModel(snapshot)
        schema = model.schema()
        self.assertTrue(schema['ready'])
        self.assertIn('Email address', schema['optionalMissing'])
        changes = model.validate({'name': 'Minimal Intern', 'start_date': '2026-10-01', 'status': 'Active'})
        added, _ = excel_management.save(snapshot, changes, backup_dir=self.backups)
        self.assertEqual(InternModel(added).list({'search': 'Minimal'})['total'], 1)

    def test_public_list_excludes_sensitive_values_and_detail_retains_unknown_columns(self):
        model = InternModel(self.prepare())
        listing = model.list({})
        row = listing['rows'][0]
        for field in ('insurance_policy', 'emergency_phone', 'email', 'phone', 'extra'):
            self.assertNotIn(field, row)
        details = model.detail(row['id'])
        self.assertEqual(details['extra']['Months'], '42')
        self.assertEqual(details['extra']['Legacy Notes'], '=1+1')
        self.assertEqual(model.list({'search': 'uanl'})['total'], 1)

    def test_bridge_requires_revision_and_updates_existing_dashboard_after_save(self):
        snapshot = self.prepare()
        bridge = DashboardBridge()
        bridge.handle('connect')
        with self.assertRaisesRegex(ValueError, 'displayed records changed'):
            bridge.handle('intern_create', parameters={'revision': 'old', 'fields': {'name': 'New', 'start_date': '2026-01-01'}})
        bridge.handle('intern_create', parameters={'revision': snapshot.digest, 'fields': {'name': 'New', 'start_date': '2026-01-01'}})
        self.assertEqual(bridge.handle('render')['metrics'][0], ('Total interns', 2))

    def test_ambiguous_field_mapping_requires_configuration(self):
        headers = ['Full Name', 'Name', 'Supervisor', 'Supervisor ']
        with self.assertRaisesRegex(ValueError, 'More than one'):
            field_mapping(headers)
        mapped = field_mapping(headers, {'supervisor': 'Supervisor'})
        self.assertEqual(mapped['supervisor'], 'Supervisor')

    def test_existing_administrative_dates_are_edited_as_dates_and_other_values_remain(self):
        table = self.book.worksheet.ListObjects(1)
        table.ListColumns.Add().Name = 'Graduation Date'
        self.book.worksheet.Cells(6, table.right).Value2 = 47000
        snapshot = self.prepare()
        model = InternModel(snapshot)
        record_id = model.list({})['rows'][0]['id']
        changes = model.validate({'graduation_estimate': '2029-06-30'}, record_id=record_id)
        self.assertEqual(changes['Graduation Date'], date(2029, 6, 30))
        updated, _ = excel_management.save(snapshot, changes, record_id, backup_dir=self.backups)
        self.assertEqual(InternModel(updated).detail(record_id)['values']['graduation_estimate'], '2029-06-30')
        self.assertEqual(updated.rows[0][:10], snapshot.rows[0][:10])

    def test_failed_save_reports_uncertainty_and_backup_without_retry(self):
        snapshot = self.prepare()
        record_id = InternModel(snapshot).list({})['rows'][0]['id']
        self.book.fail_save = True
        with self.assertRaisesRegex(RuntimeError, 'may already be in Excel'):
            excel_management.save(snapshot, {'Full Name': 'Changed'}, record_id, backup_dir=self.backups)
        self.assertEqual(self.book.worksheet.ws['C6'].value, 'Changed')
        self.assertGreaterEqual(len(list(self.backups.glob('*.xlsx'))), 2)
