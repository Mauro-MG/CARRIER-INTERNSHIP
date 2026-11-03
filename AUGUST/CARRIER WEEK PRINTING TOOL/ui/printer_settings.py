"""Printer selection window."""
from __future__ import annotations
import tkinter as tk
from tkinter import messagebox, ttk
from services.config_service import ConfigService
from services.printer_service import PrinterError, PrinterService

class PrinterSettingsDialog(tk.Toplevel):
    def __init__(self, parent: tk.Misc, printers: PrinterService, config: ConfigService) -> None:
        super().__init__(parent)
        self.title("Printer Settings")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        self.saved = False
        frame = ttk.Frame(self, padding=20)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="Printer:").grid(row=0, column=0, sticky="w", pady=(0, 6))
        self.value = tk.StringVar(value=config.config["printer"]["name"])
        try:
            choices = printers.list_printers()
        except PrinterError as exc:
            choices = []
            messagebox.showerror("Printer Error", str(exc), parent=self)
        combo = ttk.Combobox(frame, textvariable=self.value, values=choices, state="readonly", width=48)
        combo.grid(row=1, column=0, columnspan=2)
        if not self.value.get() and choices:
            combo.current(0)
        ttk.Button(frame, text="Cancel", command=self.destroy).grid(row=2, column=0, sticky="e", pady=(18, 0), padx=(0, 6))
        ttk.Button(frame, text="Save", style="success.TButton", command=lambda: self._save(config)).grid(row=2, column=1, sticky="w", pady=(18, 0))

    def _save(self, config: ConfigService) -> None:
        config.set_printer(self.value.get())
        self.saved = True
        self.destroy()

