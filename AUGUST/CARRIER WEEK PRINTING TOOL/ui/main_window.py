"""Main ttkbootstrap application window."""
from __future__ import annotations
import logging
import threading
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import pandas as pd
from services.config_service import ConfigService
from services.database_service import DatabaseLockedError, DatabaseService, QueryBackedDatabaseError
from services.excel_importer import ExcelImporter, ImportValidationError, search_key
from services.excel_refresh_service import ExcelRefreshError, ExcelRefreshService
from services.label_renderer import LabelRenderer, LabelTemplateError
from services.printer_service import PrinterError, PrinterService
from services.student_search import matches_student_search
from ui.import_dialog import ImportPreviewDialog
from ui.label_preview import LabelPreview
from ui.printer_settings import PrinterSettingsDialog

LOGGER = logging.getLogger(__name__)

class MainWindow(ttk.Frame):
    def __init__(self, parent: tk.Tk, root_path: Path, config: ConfigService, resource_path: Path | None = None) -> None:
        super().__init__(parent, padding=16)
        self.parent, self.root_path, self.config_service = parent, root_path, config
        self.resource_path = resource_path or root_path
        self.database = DatabaseService(root_path / "database" / "students.xlsx")
        self.importer = ExcelImporter()
        self.excel_refresh = ExcelRefreshService()
        self.printers = PrinterService()
        self.renderer = LabelRenderer(self.resource_path / "assets" / "label_template.png", self.resource_path / "assets" / "fonts", config.config)
        self.frame = pd.DataFrame()
        self.selected: dict[str, object] | None = None
        self.current_image = None
        self.search_var, self.source_var, self.status_var = tk.StringVar(), tk.StringVar(value="All"), tk.StringVar(value="All")
        self.status_text = tk.StringVar(value="Loading...")
        self.pack(fill="both", expand=True)
        self._build()
        self.refresh()
        self.parent.after(250, self._warn_missing_printer)

    def _build(self) -> None:
        ttk.Label(self, text="STUDENT LABEL PRINTER", font=("Segoe UI", 20, "bold")).pack(anchor="w", pady=(0, 14))
        toolbar = ttk.Frame(self); toolbar.pack(fill="x")
        ttk.Button(toolbar, text="Import Responses Excel", style="primary.TButton", command=self.import_excel).pack(side="left")
        ttk.Button(toolbar, text="Refresh Database", command=self.refresh_database).pack(side="left", padx=8)
        ttk.Button(toolbar, text="Printer Settings", command=self.printer_settings).pack(side="left")
        filters = ttk.Frame(self); filters.pack(fill="x", pady=14)
        ttk.Label(filters, text="Search name, career, or Unique ID:").grid(row=0, column=0, sticky="w")
        search = ttk.Entry(filters, textvariable=self.search_var, width=44); search.grid(row=0, column=1, padx=(6, 18), sticky="ew")
        ttk.Label(filters, text="Source:").grid(row=0, column=2)
        ttk.Combobox(filters, textvariable=self.source_var, values=("All", "Carrier Week", "Carrier Day"), state="readonly", width=15).grid(row=0, column=3, padx=(6, 18))
        ttk.Label(filters, text="Status:").grid(row=0, column=4)
        ttk.Combobox(filters, textvariable=self.status_var, values=("All", "Pending", "Printed"), state="readonly", width=12).grid(row=0, column=5, padx=(6, 0))
        filters.columnconfigure(1, weight=1)
        for var in (self.search_var, self.source_var, self.status_var): var.trace_add("write", lambda *_: self._populate())

        pane = ttk.Panedwindow(self, orient="horizontal"); pane.pack(fill="both", expand=True)
        left, right = ttk.Labelframe(pane, text=" Students ", padding=8), ttk.Labelframe(pane, text=" Label Preview ", padding=8)
        pane.add(left, weight=3); pane.add(right, weight=2)
        columns = ("UniqueID", "Nombre completo", "Carrera", "Semestre", "Source", "Printed")
        self.tree = ttk.Treeview(left, columns=columns, show="headings", selectmode="browse")
        widths = (145, 220, 150, 85, 110, 75)
        for column, width in zip(columns, widths):
            self.tree.heading(column, text=column, command=lambda c=column: self._sort(c))
            self.tree.column(column, width=width, minwidth=60)
        scrollbar = ttk.Scrollbar(left, orient="vertical", command=self.tree.yview); self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side="left", fill="both", expand=True); scrollbar.pack(side="right", fill="y")
        self.tree.bind("<<TreeviewSelect>>", self._select)
        self.preview = LabelPreview(right); self.preview.pack(fill="both", expand=True)
        self.print_status = ttk.Label(right, text="Status: No student selected"); self.print_status.pack(anchor="w", pady=(10, 6))
        self.print_button = ttk.Button(right, text="PRINT LABEL", style="success.TButton", state="disabled", command=self.print_label)
        self.print_button.pack(fill="x")
        ttk.Separator(self).pack(fill="x", pady=(12, 6))
        ttk.Label(self, textvariable=self.status_text).pack(anchor="w")

    def _database_error(self, exc: Exception) -> None:
        LOGGER.error("Database operation failed", exc_info=(type(exc), exc, exc.__traceback__))
        if isinstance(exc, QueryBackedDatabaseError):
            message = str(exc)
        else:
            message = "Unable to update the student database.\n\nPlease close students.xlsx in Excel and try again."
        messagebox.showerror("Database Error", message, parent=self.parent)

    def refresh(self) -> None:
        try: self.frame = self.database.load()
        except Exception as exc:
            self._database_error(exc); return
        self.selected = None; self.current_image = None; self.print_button.configure(state="disabled"); self.preview.clear(); self._populate(); self._status()

    def refresh_database(self) -> None:
        self._busy("Refreshing OneDrive data in Excel...")
        def work():
            try:
                self.excel_refresh.refresh(self.database.path)
                error = None
            except Exception as exc:
                error = exc
            self.parent.after(0, lambda: self._finish_database_refresh(error))
        threading.Thread(target=work, daemon=True).start()

    def _finish_database_refresh(self, error: Exception | None) -> None:
        self._busy(None)
        if error:
            LOGGER.error("Database refresh failed", exc_info=(type(error), error, error.__traceback__))
            title = "Excel Refresh Error" if isinstance(error, ExcelRefreshError) else "Database Error"
            messagebox.showerror(title, str(error), parent=self.parent)
            return
        self.refresh()
        messagebox.showinfo("Database Refreshed", "OneDrive data was refreshed and the student list is up to date.", parent=self.parent)

    def _filtered(self) -> pd.DataFrame:
        frame = self.frame.copy()
        query = self.search_var.get()
        if query:
            frame = frame[frame.apply(lambda row: matches_student_search(row, query), axis=1)]
        if self.source_var.get() != "All": frame = frame[frame["Source"] == self.source_var.get()]
        if self.status_var.get() == "Printed": frame = frame[frame["Printed"] == "Yes"]
        elif self.status_var.get() == "Pending": frame = frame[frame["Printed"] != "Yes"]
        return frame

    def _populate(self) -> None:
        if not hasattr(self, "tree"): return
        self.tree.delete(*self.tree.get_children())
        for _, row in self._filtered().iterrows():
            uid = str(row["UniqueID"])
            self.tree.insert("", "end", iid=uid, values=tuple(row[c] for c in ("UniqueID", "Nombre completo", "Carrera", "Semestre", "Source", "Printed")))

    def _sort(self, column: str) -> None:
        self.frame = self.frame.sort_values(column, key=lambda values: values.astype(str).map(search_key), kind="stable")
        self._populate()

    def _select(self, _event=None) -> None:
        selected = self.tree.selection()
        if not selected: return
        uid = selected[0]
        row = self.frame[self.frame["UniqueID"].astype(str) == uid].iloc[0].to_dict()
        self.selected = row
        try:
            self.current_image = self.renderer.render(row)
            self.current_image.save(self.root_path / "temp" / "current_label.png")
            self.preview.show_image(self.current_image)
            self.print_button.configure(state="normal")
            self.print_status.configure(text=f"Status: {'Printed' if row['Printed'] == 'Yes' else 'Not printed'} | Count: {row['PrintCount']}")
        except LabelTemplateError as exc:
            self.current_image = None; self.print_button.configure(state="disabled")
            messagebox.showerror("Template Missing", str(exc), parent=self.parent)
        except Exception as exc:
            LOGGER.exception("Label render failed")
            messagebox.showerror("Label Error", f"Unable to render the label.\n\n{exc}", parent=self.parent)

    def import_excel(self) -> None:
        filename = filedialog.askopenfilename(parent=self.parent, title="Import Responses Excel", filetypes=(("Excel files", "*.xlsx *.xls"), ("All files", "*.*")))
        if not filename: return
        path = Path(filename)
        try: result = self.importer.read(path)
        except ImportValidationError as exc:
            LOGGER.exception("Import validation failed"); messagebox.showerror("Import Error", str(exc), parent=self.parent); return
        preview = ImportPreviewDialog(self.parent, path, result); self.parent.wait_window(preview)
        if not preview.approved: return
        self._busy("Importing...")
        def work():
            try: outcome = self.database.upsert(result.records); error = None
            except Exception as exc: outcome, error = None, exc
            self.parent.after(0, lambda: self._finish_import(result, outcome, error))
        threading.Thread(target=work, daemon=True).start()

    def _finish_import(self, result, outcome, error) -> None:
        self._busy(None)
        if error:
            self._database_error(error); return
        new, updated, total = outcome
        for warning in result.warnings: LOGGER.warning(warning)
        self.refresh()
        messagebox.showinfo("Import Completed", f"Import completed\n\nSource: {result.source}\n\nRows read: {result.rows_read}\nNew students: {new}\nUpdated students: {updated}\nSkipped rows: {result.skipped_rows}\n\nTotal students in database: {total}", parent=self.parent)

    def print_label(self) -> None:
        if not self.selected or self.current_image is None: return
        if self.selected["Printed"] == "Yes":
            confirm = messagebox.askyesno("Reprint Label", f"This label has already been printed.\n\nLast printed:\n{self.selected['PrintedAt']}\n\nPrint count:\n{self.selected['PrintCount']}\n\nDo you want to print it again?", parent=self.parent)
            if not confirm: return
        image, uid = self.current_image.copy(), str(self.selected["UniqueID"])
        printer = self.config_service.config["printer"]["name"]
        self._busy("Submitting print job...")
        def work():
            try:
                self.printers.print_image(image, printer)
                self.database.mark_printed(uid)
                error = None
            except Exception as exc: error = exc
            self.parent.after(0, lambda: self._finish_print(error))
        threading.Thread(target=work, daemon=True).start()

    def _finish_print(self, error) -> None:
        self._busy(None)
        if error:
            LOGGER.error("Print failed", exc_info=(type(error), error, error.__traceback__)); messagebox.showerror("Print Error", str(error), parent=self.parent); return
        self.refresh(); messagebox.showinfo("Print Submitted", "The label was successfully submitted to Windows.", parent=self.parent)

    def printer_settings(self) -> None:
        dialog = PrinterSettingsDialog(self.parent, self.printers, self.config_service); self.parent.wait_window(dialog)
        if dialog.saved: self._status()

    def _warn_missing_printer(self) -> None:
        name = self.config_service.config["printer"]["name"]
        if not name: return
        try: available = self.printers.is_available(name)
        except PrinterError: available = False
        if not available: messagebox.showwarning("Printer Unavailable", f"The saved printer is unavailable:\n{name}\n\nChoose another printer in Printer Settings.", parent=self.parent)

    def _busy(self, text: str | None) -> None:
        self.parent.configure(cursor="watch" if text else "")
        if text: self.status_text.set(text)
        else: self._status()

    def _status(self) -> None:
        total = len(self.frame)
        printed = int((self.frame["Printed"] == "Yes").sum()) if not self.frame.empty else 0
        printer = self.config_service.config["printer"]["name"] or "Not configured"
        self.status_text.set(f"Students: {total} | Pending: {total - printed} | Printed: {printed} | Printer: {printer}")
