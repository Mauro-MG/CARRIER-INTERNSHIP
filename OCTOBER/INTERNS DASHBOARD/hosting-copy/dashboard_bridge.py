"""JSON-lines presentation adapter. Business logic stays in the original modules."""
from datetime import datetime
import json
import sys

import excel_store
import excel_management
from intern_management import InternModel, load_overrides, parse_date
from dashboard_data import Dashboard, display


FILTERS = [('name', 'Full name'), ('role', 'Role'), ('university', 'University'),
           ('supervisor', 'Supervisor'), ('start_date', 'Start date')]


class DashboardBridge:
    def __init__(self):
        self.snapshot = None
        self.dashboard = None
        self.refreshed_at = None

    def handle(self, action, filters=None, parameters=None):
        if action in ('intern_list', 'intern_detail', 'intern_create', 'intern_update', 'intern_delete', 'intern_migrate'):
            return self.management(action, parameters or {})
        if action not in ('state', 'connect', 'refresh', 'render'):
            raise ValueError('Unknown dashboard action.')
        filters = {} if filters is None else filters
        if not isinstance(filters, dict) or any(
            key not in dict(FILTERS) or not isinstance(value, str)
            for key, value in filters.items()
        ):
            raise ValueError('Choose valid dashboard filters.')
        if action in ('connect', 'refresh'):
            # The existing read function owns Excel/COM behavior and workbook identity.
            if action == 'refresh' and self.snapshot:
                snapshot = excel_store.read(self.snapshot.path, self.snapshot.sheet)
            else:
                snapshot = excel_store.read()
            dashboard = Dashboard.from_snapshot(snapshot)
            self.snapshot, self.dashboard = snapshot, dashboard
            self.refreshed_at = datetime.now().strftime('%H:%M')
        return self.view(filters)

    def management(self, action, parameters):
        if not isinstance(parameters, dict):
            raise ValueError('Expected intern management parameters.')
        if not self.snapshot:
            if action == 'intern_list':
                return {'connected': False, 'rows': [], 'total': 0, 'schema': None, 'counts': {}}
            raise ValueError('Connect to the source workbook in Excel first.')
        overrides = load_overrides()
        model = InternModel(self.snapshot, overrides, parse_date(parameters.get('today')))
        if action == 'intern_list':
            return model.list(parameters)
        if action == 'intern_detail':
            return model.detail(parameters.get('id'))
        if parameters.get('revision') != self.snapshot.digest:
            raise ValueError('The displayed records changed. Refresh and reopen the form before saving.')
        if action == 'intern_migrate':
            snapshot, backup = excel_management.migrate(self.snapshot, overrides)
        elif action == 'intern_delete':
            snapshot, backup = excel_management.delete(self.snapshot, parameters.get('id'), overrides)
        else:
            if not model.schema()['ready']:
                raise ValueError('Prepare the workbook fields before saving interns.')
            record_id = parameters.get('id') if action == 'intern_update' else None
            changes = model.validate(parameters.get('fields'), parameters.get('extra'), record_id)
            snapshot, backup = excel_management.save(self.snapshot, changes, record_id, overrides)
        self.snapshot = snapshot
        self.dashboard = Dashboard.from_snapshot(snapshot)
        self.refreshed_at = datetime.now().strftime('%H:%M')
        return {'saved': True, 'backup': str(backup) if backup else None,
                'schema': InternModel(snapshot, overrides).schema()}

    def view(self, filters):
        choices = {field: self.dashboard.choices(field) if self.dashboard else ['All']
                   for field, _ in FILTERS}
        selected = {field: filters.get(field, 'All') if filters.get(field, 'All') in choices[field]
                    else 'All' for field, _ in FILTERS}
        result = {
            'connected': self.dashboard is not None,
            'filters': [{'key': field, 'label': label, 'choices': choices[field],
                         'selected': selected[field]} for field, label in FILTERS],
            'metrics': [[label, '—'] for label in
                        ('Total interns', 'Universities', 'Managers', 'Supervisors', 'Careers')],
            'charts': {key: [] for key in ('role', 'gender', 'university', 'supervisor', 'career')},
            'recent': {'columns': [], 'rows': []},
            'source': None,
        }
        if not self.dashboard:
            return result
        records = self.dashboard.filtered(selected)
        rows, columns = self.dashboard.recent(records)
        result.update(
            metrics=self.dashboard.metrics(records),
            charts=self.dashboard.charts(records),
            recent={'columns': columns,
                    'rows': [[display(row.get(column, ''), column) for column in columns] for row in rows]},
            source={'path': str(self.snapshot.path), 'sheet': self.snapshot.sheet,
                    'records': len(self.snapshot.rows), 'refreshedAt': self.refreshed_at},
        )
        return result


def main():
    sys.stdin.reconfigure(encoding='utf-8')
    sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)
    bridge = DashboardBridge()
    for line in sys.stdin:
        request = {}
        try:
            request = json.loads(line)
            if not isinstance(request, dict):
                raise ValueError('Expected a dashboard request.')
            data = bridge.handle(request.get('action'), request.get('filters'), request.get('parameters'))
            response = {'id': request.get('id'), 'ok': True, 'data': data}
        except Exception as error:
            response = {'id': request.get('id') if isinstance(request, dict) else None,
                        'ok': False, 'error': str(error)}
        print(json.dumps(response, ensure_ascii=False, allow_nan=False))


if __name__ == '__main__':
    main()
