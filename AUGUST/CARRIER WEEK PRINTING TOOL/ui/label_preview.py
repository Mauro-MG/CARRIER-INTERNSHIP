"""Aspect-preserving label preview widget."""
from __future__ import annotations
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk

class LabelPreview(ttk.Frame):
    def __init__(self, parent: tk.Misc) -> None:
        super().__init__(parent)
        self.image: Image.Image | None = None
        self.photo: ImageTk.PhotoImage | None = None
        self.canvas = tk.Canvas(self, background="#eeeeee", highlightthickness=1, highlightbackground="#cccccc")
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Configure>", lambda _event: self._redraw())

    def show_image(self, image: Image.Image) -> None:
        self.image = image.copy()
        self._redraw()

    def clear(self) -> None:
        self.image = None
        self.canvas.delete("all")
        self.canvas.create_text(self.canvas.winfo_width() // 2, self.canvas.winfo_height() // 2, text="Select a student to preview the label", fill="#666666")

    def _redraw(self) -> None:
        if self.image is None:
            self.clear()
            return
        width, height = max(10, self.canvas.winfo_width() - 24), max(10, self.canvas.winfo_height() - 24)
        preview = self.image.copy()
        preview.thumbnail((width, height), Image.Resampling.LANCZOS)
        self.photo = ImageTk.PhotoImage(preview)
        self.canvas.delete("all")
        self.canvas.create_image(self.canvas.winfo_width() // 2, self.canvas.winfo_height() // 2, image=self.photo, anchor="center")
