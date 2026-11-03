import unittest
from dashboard_data import Dashboard, display, find_column


class Snapshot:
    headers = ['Full Name', 'Role', 'Universidad', 'Supervisor', 'Fecha de Ingreso', 'Género', 'Carrera']
    rows = [
        ('Ana', 'Engineering', 'UANL', 'Luis', '2026-01-01', 'Femenino', 'Mecatrónica'),
        ('Cass', 'Engineering', 'UANL', 'Luis', '2026-02-01', 'Masculino', 'Mecatrónica'),
        ('Pao', 'Design', 'TEC', 'Mia', '2026-03-01', 'Femenino', 'Diseño'),
    ]


class DashboardDataTests(unittest.TestCase):
    def setUp(self):
        self.dashboard = Dashboard.from_snapshot(Snapshot())

    def test_spanish_headers_are_detected(self):
        self.assertEqual(self.dashboard.columns['university'], 'Universidad')
        self.assertEqual(self.dashboard.columns['start_date'], 'Fecha de Ingreso')
        self.assertEqual(self.dashboard.columns['gender'], 'Género')
        self.assertEqual(find_column(['No matching field'], 'role'), None)
        self.assertEqual(find_column(['Rol'], 'role'), 'Rol')

    def test_filters_metrics_and_counts(self):
        records = self.dashboard.filtered({'university': 'UANL'})
        self.assertEqual(len(records), 2)
        self.assertEqual(self.dashboard.metrics(records)[0], ('Total interns', 2))
        self.assertEqual(self.dashboard.charts(records)['role'], [('Engineering', 2)])
        self.assertEqual(self.dashboard.metrics(records)[2], ('Managers', '—'))

    def test_choices_follow_most_common_values(self):
        self.assertEqual(self.dashboard.choices('university'), ['All', 'UANL', 'TEC'])

    def test_excel_date_serials_are_rendered_as_dates(self):
        self.assertEqual(display(46022, 'Fecha de Ingreso'), '31/12/2025')
        self.assertEqual(display(36526, 'Fecha de Nacimiento'), '01/01/2000')
