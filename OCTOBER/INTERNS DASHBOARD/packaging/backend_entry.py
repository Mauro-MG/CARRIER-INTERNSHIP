"""Frozen backend entry point; the existing business modules remain in place."""
import json
import sys

import dashboard_bridge


def diagnostics():
    import pythoncom
    import pywintypes
    import win32com.client
    import win32timezone
    import openpyxl
    import workbook_store
    from datetime import date
    from intern_management import duration
    pythoncom.CoInitialize()
    pythoncom.CoUninitialize()
    return {'ok': duration('2024-02-29', today=date(2025, 2, 28))['months'] == 12,
            'frozen': bool(getattr(sys, 'frozen', False)), 'python': sys.version.split()[0],
            'excelSupport': True, 'localWorkbookSupport': True, 'openpyxl': openpyxl.__version__}


if __name__ == '__main__':
    if '--diagnostics' in sys.argv:
        print(json.dumps(diagnostics()))
    else:
        dashboard_bridge.main()
