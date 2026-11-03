"""Reusable, keyboard-accessible inputs and task editor for the desktop app."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox
from typing import Callable

import ttkbootstrap as ttk
from ttkbootstrap.widgets import DateEntry


def fit_dialog(dialog, parent, width: int, height: int) -> None:
    """Keep dialogs on screen, including on smaller laptop displays."""
    parent.update_idletasks()
    width = min(width, parent.winfo_screenwidth() - 60)
    height = min(height, parent.winfo_screenheight() - 100)
    x = max(0, min(parent.winfo_rootx() + (parent.winfo_width() - width) // 2,
                   parent.winfo_screenwidth() - width))
    y = max(0, min(parent.winfo_rooty() + (parent.winfo_height() - height) // 2,
                   parent.winfo_screenheight() - height - 60))
    dialog.geometry(f"{width}x{height}+{x}+{y}")
    dialog.transient(parent)
    dialog.bind("<Escape>", lambda _event: dialog.destroy())


class TaskField(ttk.Frame):
    """One consistent input implementation shared by single and batch editing."""

    def __init__(self, parent, field_name: str, options: dict[str, list[str]],
                 value: str = "", compact: bool = False,
                 multi_value_fields: set[str] | frozenset[str] | None = None) -> None:
        super().__init__(parent)
        self.columnconfigure(0, weight=1)
        self.field_name = field_name
        self.options = options
        self.multi_value_fields = multi_value_fields or frozenset()
        self.menu_vars: dict[str, tk.BooleanVar] = {}
        if field_name == "Description":
            self.input = tk.Text(self, height=3 if compact else 5, wrap="word",
                                 font="TkDefaultFont", relief="solid", borderwidth=1,
                                 padx=8, pady=6, undo=True, width=20)
            self.input.insert("1.0", value)
            scroll = ttk.Scrollbar(self, command=self.input.yview)
            scroll.grid(row=0, column=1, sticky="ns")
            self.input.configure(yscrollcommand=scroll.set)
        elif field_name == "Due Date":
            self.input = DateEntry(self, dateformat="%m/%d/%Y", bootstyle="primary")
            self.input.entry.delete(0, "end")
            self.input.entry.insert(0, value)
        elif field_name in self.multi_value_fields:
            self.input = ttk.Entry(self)
            self.input.insert(0, value)
            self.menu = tk.Menu(self, tearoff=False, postcommand=self._populate_menu)
            self.choose = ttk.Menubutton(self, text="Choose", menu=self.menu,
                                        bootstyle="secondary-outline")
            self.choose.grid(row=0, column=1, padx=(6, 0))
        elif field_name in options:
            self.input = ttk.Combobox(self, values=options[field_name], state="normal")
            self.input.set(value)
        else:
            self.input = ttk.Entry(self)
            self.input.insert(0, value)
        self.input.grid(row=0, column=0, sticky="nsew")
        self.rowconfigure(0, weight=1)

    def _populate_menu(self) -> None:
        chosen = [part.strip() for part in self.get().split(",") if part.strip()]
        values = list(dict.fromkeys(self.options.get(self.field_name, []) + chosen))
        self.menu.delete(0, "end")
        self.menu_vars.clear()
        for value in values:
            var = tk.BooleanVar(value=value in chosen)
            self.menu_vars[value] = var
            self.menu.add_checkbutton(label=value, variable=var, command=self._apply_choices)
        if not values:
            self.menu.add_command(label="Add options in Manage options", state="disabled")

    def _apply_choices(self) -> None:
        self.input.delete(0, "end")
        self.input.insert(0, ", ".join(value for value, var in self.menu_vars.items() if var.get()))

    def get(self) -> str:
        if isinstance(self.input, tk.Text):
            return self.input.get("1.0", "end-1c").strip()
        if isinstance(self.input, DateEntry):
            return self.input.entry.get().strip()
        return self.input.get().strip()

    def focus_input(self) -> None:
        target = self.input.entry if isinstance(self.input, DateEntry) else self.input
        target.focus_set()


class RowEditorDialog(ttk.Toplevel):
    """Tabbed draft editor: nothing is committed until Save succeeds."""

    GROUPS = {
        "Task details": ["Name", "Labels", "Estimated Time", "Task Type", "Description"],
        "Assignment": ["Assignee", "Project", "Priority", "Status"],
        "Dates & tracking": ["Due Date", "ECN"],
    }

    def __init__(self, parent, values: dict[str, str], options: dict[str, list[str]],
                 on_save: Callable[[dict[str, str]], None],
                 validate: Callable[[dict[str, str]], list[str]],
                 field_help: dict[str, str], title: str = "Edit task",
                 multi_value_fields: set[str] | frozenset[str] | None = None) -> None:
        super().__init__(parent)
        self.title(title)
        fit_dialog(self, parent, 760, 600)
        self.minsize(600, 530)
        self.on_save = on_save
        self.validate = validate
        self.inputs: dict[str, TaskField] = {}
        self.field_tabs = {}
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        header = ttk.Frame(self, padding=(20, 16, 20, 10))
        header.grid(row=0, column=0, sticky="ew")
        ttk.Label(header, text=title, font=("Segoe UI", 16, "bold")).pack(anchor="w")
        ttk.Label(header, text="Edit a draft, then save. Name is required.  •  Ctrl+Enter to save",
                  bootstyle="secondary").pack(anchor="w", pady=(4, 0))

        self.notebook = ttk.Notebook(self)
        self.notebook.grid(row=1, column=0, sticky="nsew", padx=20)
        for title, fields in self.GROUPS.items():
            page = ttk.Frame(self.notebook, padding=16)
            page.columnconfigure(1, weight=1)
            self.notebook.add(page, text=title)
            for index, name in enumerate(fields):
                ttk.Label(page, text="Name *" if name == "Name" else name).grid(
                    row=index, column=0, sticky="nw", padx=(0, 16), pady=(8, 10))
                widget = TaskField(
                    page, name, options, values.get(name, ""),
                    multi_value_fields=multi_value_fields,
                )
                widget.grid(row=index, column=1, sticky="nsew", pady=(4, 6))
                self.inputs[name] = widget
                self.field_tabs[name] = page
                if name == "Description":
                    page.rowconfigure(index, weight=1)
                widget.input.bind("<FocusIn>", lambda _event, n=name: self.help_text.set(field_help.get(n, "")))
            if title == "Dates & tracking":
                ttk.Label(page, text="Use MM/DD/YYYY or the calendar. Leave optional dates blank.",
                          wraplength=500, bootstyle="secondary").grid(
                              row=len(fields), column=0, columnspan=2, sticky="w", pady=12)

        footer = ttk.Frame(self, padding=(20, 12, 20, 16))
        footer.grid(row=2, column=0, sticky="ew")
        footer.columnconfigure(0, weight=1)
        multi_names = ", ".join(sorted(multi_value_fields or []))
        multi_help = f"{multi_names} supports multiple values through Choose." if multi_names else "Review the field guidance before saving."
        self.help_text = tk.StringVar(value=multi_help)
        help_label = ttk.Label(footer, textvariable=self.help_text, wraplength=440,
                               bootstyle="secondary")
        help_label.grid(row=0, column=0, sticky="w", padx=(0, 12))
        footer.bind("<Configure>", lambda event: help_label.configure(wraplength=max(180, event.width - 240)))
        ttk.Button(footer, text="Cancel", command=self.destroy, bootstyle="secondary-outline").grid(row=0, column=1, padx=8)
        self.save_button = ttk.Button(footer, text="Save task", command=self._save, bootstyle="primary")
        self.save_button.grid(row=0, column=2)
        self.bind("<Control-Return>", lambda _event: self._save())
        self.grab_set()
        self.after_idle(self.inputs["Name"].focus_input)

    def _save(self) -> None:
        values = {name: widget.get() for name, widget in self.inputs.items()}
        errors = self.validate(values)
        if errors:
            messagebox.showerror("Check task fields", "\n".join(errors), parent=self)
            return
        self.on_save(values)
        self.destroy()
