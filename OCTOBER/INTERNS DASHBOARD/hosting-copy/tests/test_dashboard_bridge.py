from datetime import date
import unittest
from unittest.mock import patch
import excel_store
from dashboard_data import Dashboard, display
from dashboard_bridge import DashboardBridge


def sample():
    return excel_store.Snapshot(
        'https://example/Interns.xlsx', 'Interns', ['Interns'],
        ['Full Name', 'Role', 'Universidad', 'Supervisor', 'Fecha de Ingreso', 'Género', 'Carrera', 'Manager'],
        [('Ana', 'Engineering', 'UANL', 'Luis', date(2026, 1, 1), 'Femenino', 'Mecatrónica', 'Pat'),
         ('Cass', 'Engineering', 'UANL', 'Luis', date(2026, 2, 1), 'Masculino', 'Mecatrónica', 'Pat'),
         ('Pao', 'Design', 'TEC', 'Mia', date(2026, 3, 1), 'Femenino', 'Diseño', 'Sam')],
        'digest', 4,
    )


class DashboardBridgeTests(unittest.TestCase):
    def setUp(self):
        self.bridge = DashboardBridge()

    def test_connect_and_filtered_views_use_original_calculations(self):
        snapshot = sample()
        with patch('dashboard_bridge.excel_store.read', return_value=snapshot) as read:
            self.bridge.handle('connect')
            read.assert_called_once_with()
        filters = {'university': 'UANL'}
        actual = self.bridge.handle('render', filters)
        original = Dashboard.from_snapshot(snapshot)
        records = original.filtered(filters)
        self.assertEqual(actual['metrics'], original.metrics(records))
        self.assertEqual(actual['charts'], original.charts(records))
        rows, columns = original.recent(records)
        self.assertEqual(actual['recent'], {'columns': columns,
            'rows': [[display(row.get(column, ''), column) for column in columns] for row in rows]})
        self.assertEqual(actual['source']['path'], snapshot.path)

    def test_refresh_stays_bound_and_failed_read_preserves_last_data(self):
        with patch('dashboard_bridge.excel_store.read', return_value=sample()):
            before = self.bridge.handle('connect')
        with patch('dashboard_bridge.excel_store.read', side_effect=ValueError('Workbook closed')) as read:
            with self.assertRaisesRegex(ValueError, 'Workbook closed'):
                self.bridge.handle('refresh')
            read.assert_called_once_with(sample().path, sample().sheet)
        self.assertEqual(self.bridge.handle('state'), before)

    def test_refresh_without_connection_connects_like_original_ui(self):
        with patch('dashboard_bridge.excel_store.read', return_value=sample()) as read:
            self.bridge.handle('refresh')
            read.assert_called_once_with()

    def test_refresh_resets_choices_that_disappeared_and_clear_restores_all(self):
        with patch('dashboard_bridge.excel_store.read', return_value=sample()):
            self.bridge.handle('connect')
        updated = sample()
        updated.rows = updated.rows[2:]
        with patch('dashboard_bridge.excel_store.read', return_value=updated):
            view = self.bridge.handle('refresh', {'university': 'UANL'})
        university = next(field for field in view['filters'] if field['key'] == 'university')
        self.assertEqual(university['selected'], 'All')
        self.assertEqual(view['metrics'][0], ('Total interns', 1))
        self.assertTrue(all(field['selected'] == 'All' for field in self.bridge.handle('render')['filters']))

    def test_invalid_input_and_unconnected_view_do_not_touch_excel(self):
        with patch('dashboard_bridge.excel_store.read') as read:
            self.assertFalse(self.bridge.handle('state')['connected'])
            for action, filters in [('write', {}), ('connect', []), ('connect', {'other': 'x'}), ('connect', {'role': 1})]:
                with self.assertRaises(ValueError):
                    self.bridge.handle(action, filters)
            read.assert_not_called()
