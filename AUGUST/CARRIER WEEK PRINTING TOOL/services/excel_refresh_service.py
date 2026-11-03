"""Refresh Excel/Power Query connections in the database workbook."""

from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path


class ExcelRefreshError(RuntimeError):
    """Raised when Microsoft Excel cannot refresh the linked workbook."""


class ExcelRefreshService:
    def refresh(self, path: Path, timeout_seconds: int = 180) -> None:
        if not path.exists():
            raise ExcelRefreshError(f"Database workbook not found:\n{path}")
        try:
            import pythoncom
            import win32com.client
        except ImportError as exc:
            raise ExcelRefreshError(
                "Microsoft Excel refresh support is unavailable. Install pywin32 and try again."
            ) from exc

        excel = workbook = launched_process = None
        pythoncom.CoInitialize()
        try:
            try:
                excel = win32com.client.DispatchEx("Excel.Application")
            except Exception:
                excel, launched_process = self._launch_and_attach_excel(
                    pythoncom, win32com.client
                )
            excel.Visible = False
            excel.DisplayAlerts = False
            workbook = excel.Workbooks.Open(str(path.resolve()), UpdateLinks=3, ReadOnly=False)
            workbook.RefreshAll()

            try:
                excel.CalculateUntilAsyncQueriesDone()
            except Exception:
                pass

            deadline = time.monotonic() + timeout_seconds
            while self._is_refreshing(workbook):
                if time.monotonic() >= deadline:
                    raise ExcelRefreshError(
                        f"Excel did not finish refreshing within {timeout_seconds} seconds."
                    )
                pythoncom.PumpWaitingMessages()
                time.sleep(0.25)

            excel.CalculateFull()
            workbook.Save()
        except ExcelRefreshError:
            raise
        except Exception as exc:
            raise ExcelRefreshError(
                "Unable to refresh students.xlsx. Close the workbook in Excel, confirm OneDrive is "
                f"available, and try again.\n\n{exc}"
            ) from exc
        finally:
            if workbook is not None:
                try:
                    workbook.Close(SaveChanges=False)
                except Exception:
                    pass
            if excel is not None:
                try:
                    excel.Quit()
                except Exception:
                    pass
            if launched_process is not None:
                try:
                    launched_process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    launched_process.terminate()
            pythoncom.CoUninitialize()

    @staticmethod
    def _launch_and_attach_excel(pythoncom, win32_client):
        """Start Excel directly when its COM server cannot self-launch."""
        executable = ExcelRefreshService._excel_executable()
        if executable is None:
            raise ExcelRefreshError("Microsoft Excel could not be found on this computer.")
        process = subprocess.Popen(
            [str(executable), "/x", "/e"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            try:
                active = pythoncom.GetActiveObject("Excel.Application")
                dispatch = active.QueryInterface(pythoncom.IID_IDispatch)
                return win32_client.Dispatch(dispatch), process
            except Exception:
                time.sleep(0.5)
        try:
            process.terminate()
        except OSError:
            pass
        raise ExcelRefreshError("Microsoft Excel started but could not be controlled by the application.")

    @staticmethod
    def _excel_executable() -> Path | None:
        try:
            import winreg

            registry_paths = (
                r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\excel.exe",
                r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\App Paths\excel.exe",
            )
            for root in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
                for registry_path in registry_paths:
                    try:
                        with winreg.OpenKey(root, registry_path) as key:
                            value = winreg.QueryValueEx(key, "")[0]
                        candidate = Path(os.path.expandvars(str(value))).resolve()
                        if candidate.exists():
                            return candidate
                    except OSError:
                        continue
        except ImportError:
            pass
        candidates = (
            Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "Microsoft Office/root/Office16/EXCEL.EXE",
            Path(os.environ.get("ProgramFiles(x86)", "C:/Program Files (x86)")) / "Microsoft Office/root/Office16/EXCEL.EXE",
        )
        return next((candidate for candidate in candidates if candidate.exists()), None)

    @staticmethod
    def _is_refreshing(workbook) -> bool:
        for connection in workbook.Connections:
            for attribute in ("OLEDBConnection", "ODBCConnection"):
                try:
                    if bool(getattr(connection, attribute).Refreshing):
                        return True
                except Exception:
                    continue
        for sheet in workbook.Worksheets:
            try:
                for table in sheet.QueryTables:
                    if bool(table.Refreshing):
                        return True
            except Exception:
                continue
        return False
