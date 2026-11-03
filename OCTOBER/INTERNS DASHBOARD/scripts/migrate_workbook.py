"""Preview/apply the additive migration to the open Excel workbook; no replacement data store."""
import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import excel_store
import excel_management
from intern_management import InternModel, load_overrides


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true', help='Apply the previewed changes with a workbook backup first.')
    args = parser.parse_args()
    snapshot = excel_store.read()
    plan = InternModel(snapshot, load_overrides()).schema()
    print(f'Workbook: {snapshot.path}\nWorksheet: {snapshot.sheet}\nRecords: {len(snapshot.rows)}')
    print('Missing columns: ' + (', '.join(plan['missingColumns']) or 'None'))
    print('Existing columns and values are retained. Missing record keys are filled; no intern records are deleted.')
    if not args.apply:
        print('Preview only. Use --apply to migrate, or use the app’s Review workbook setup control.')
        return
    _, backup = excel_management.migrate(snapshot, load_overrides())
    print(f'Migration completed. Backup: {backup}' if backup else 'Workbook is already prepared; no changes made.')


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(str(error))
        raise SystemExit(1)
