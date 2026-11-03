"""Import validation preview dialog."""
from __future__ import annotations
from pathlib import Path
import tkinter as tk
from tkinter import ttk
from services.excel_importer import ImportResult

class ImportPreviewDialog(tk.Toplevel):
    def __init__(self, parent: tk.Misc, path: Path, result: ImportResult) -> None:
        super().__init__(parent)
        self.approved = False
        self.title("Confirm Import")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        body = ttk.Frame(self, padding=20)
        body.pack(fill="both", expand=True)
        text = [f"File:\n{path.name}", f"\nDetected source:\n{result.source}", "\nDetected fields:"]
        text.extend(f"{field:<10} → {column}" for field, column in result.column_mapping.items())
        text.append(f"\nRows found: {result.rows_read}\nValid rows: {len(result.records)}")
        ttk.Label(body, text="\n".join(text), justify="left").pack(anchor="w")
        buttons = ttk.Frame(body)
        buttons.pack(fill="x", pady=(18, 0))
        ttk.Button(buttons, text="Cancel", command=self.destroy).pack(side="right")
        ttk.Button(buttons, text="Import", style="success.TButton", command=self._approve).pack(side="right", padx=8)
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.wait_visibility()
        self.focus_set()

    def _approve(self) -> None:
        self.approved = True
        self.destroy()

