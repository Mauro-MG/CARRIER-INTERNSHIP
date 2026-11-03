"""Desktop Excel dashboard. Excel remains the system that saves SharePoint data."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import tkinter as tk
from tkinter import messagebox
import ttkbootstrap as ttk

import excel_store
from dashboard_data import Dashboard, display


NAVY, BLUE, PALE_BLUE, PAGE, CARD, MUTED = '#112E51', '#0A84E8', '#8DC4F2', '#F5F7FA', '#FFFFFF', '#64748B'


class HorizontalBars(tk.Canvas):
    def __init__(self, parent):
        super().__init__(parent, height=165, bg=CARD, highlightthickness=0)
        self.data = []
        self.bind('<Configure>', lambda _event: self.draw())

    def set_data(self, data):
        self.data = data
        self.draw()

    def draw(self):
        self.delete('all')
        width, height = max(self.winfo_width(), 1), max(self.winfo_height(), 1)
        if not self.data:
            self.create_text(width / 2, height / 2, text='No data available', fill=MUTED, font=('Segoe UI', 9))
            return
        maximum = max(value for _, value in self.data) or 1
        row_height, label_width = max(22, (height - 10) // len(self.data)), min(145, width * .48)
        for index, (label, value) in enumerate(self.data):
            y = 8 + index * row_height
            label = label if len(label) <= 23 else label[:21] + '…'
            self.create_text(label_width - 7, y + 8, text=label, anchor='e', fill=MUTED, font=('Segoe UI', 8))
            start, end = label_width + 4, width - 32
            self.create_rectangle(start, y + 3, start + (end - start) * value / maximum, y + 13, fill=BLUE, outline='')
            self.create_text(width - 10, y + 8, text=str(value), anchor='e', fill=NAVY, font=('Segoe UI', 8, 'bold'))


class Donut(tk.Canvas):
    def __init__(self, parent):
        super().__init__(parent, height=165, bg=CARD, highlightthickness=0)
        self.data = []
        self.bind('<Configure>', lambda _event: self.draw())

    def set_data(self, data):
        self.data = data
        self.draw()

    def draw(self):
        self.delete('all')
        width, height = max(self.winfo_width(), 1), max(self.winfo_height(), 1)
        total = sum(value for _, value in self.data)
        if not total:
            self.create_text(width / 2, height / 2, text='No data available', fill=MUTED, font=('Segoe UI', 9))
            return
        diameter = min(116, height - 26, width * .48)
        x, y = 22, (height - diameter) / 2
        palette, start = [BLUE, PALE_BLUE, '#315F93', '#B8DDF8', '#6A9FD1'], 0
        for index, (_label, value) in enumerate(self.data):
            extent = value / total * 360
            self.create_arc(x, y, x + diameter, y + diameter, start=start, extent=extent, fill=palette[index % len(palette)], outline=CARD, width=2, style='pieslice')
            start += extent
        inset = diameter * .31
        self.create_oval(x + inset, y + inset, x + diameter - inset, y + diameter - inset, fill=CARD, outline='')
        self.create_text(x + diameter / 2, y + diameter / 2, text=str(total), fill=NAVY, font=('Segoe UI', 17, 'bold'))
        legend_x, legend_y = x + diameter + 25, 42
        for index, (label, value) in enumerate(self.data[:5]):
            label, yy = (label if len(label) <= 18 else label[:16] + '…'), legend_y + index * 23
            self.create_oval(legend_x, yy, legend_x + 8, yy + 8, fill=palette[index % len(palette)], outline='')
            self.create_text(legend_x + 14, yy + 4, text=f'{label}  {value}', anchor='w', fill=MUTED, font=('Segoe UI', 8))


class DashboardApp:
    FILTERS = [('name', 'Full name'), ('role', 'Role'), ('university', 'University'), ('supervisor', 'Supervisor'), ('start_date', 'Start date')]

    def __init__(self, root):
        self.root, self.snapshot, self.dashboard, self.busy = root, None, None, False
        self.pool = ThreadPoolExecutor(max_workers=1)
        self.filter_values = {field: tk.StringVar(value='All') for field, _ in self.FILTERS}
        self.filter_boxes, self.cards, self.charts = {}, [], {}
        self.status = tk.StringVar(value='Open the source workbook in Excel, then select Connect to Excel.')
        self.loaded = tk.StringVar(value='Data not connected')
        root.title('Intern Program')
        root.geometry('1320x820')
        root.minsize(1000, 660)
        root.configure(bg=PAGE)
        self.build()
        root.protocol('WM_DELETE_WINDOW', self.close)

    def button(self, parent, text, action, style='primary'):
        button = ttk.Button(parent, text=text, command=action, bootstyle=style)
        self.buttons.append(button)
        return button

    def build(self):
        self.buttons = []
        page = tk.Frame(self.root, bg=PAGE)
        page.pack(fill='both', expand=True)
        header = tk.Frame(page, bg=PAGE, padx=24, pady=15)
        header.pack(fill='x')
        tk.Label(header, text='Intern Program', font=('Segoe UI', 22, 'bold'), fg=NAVY, bg=PAGE).pack(side='left')
        tk.Label(header, text='Talent today. A cooler tomorrow.', font=('Segoe UI', 9), fg=MUTED, bg=PAGE).pack(side='left', padx=12, pady=(10, 0))
        self.button(header, 'Connect to Excel', self.connect, 'success').pack(side='right')
        self.button(header, 'Refresh', self.refresh, 'outline-primary').pack(side='right', padx=8)
        content = tk.Frame(page, bg=PAGE, padx=24)
        content.pack(fill='both', expand=True)
        self.filters = tk.LabelFrame(content, text='Filters', font=('Segoe UI', 9, 'bold'), fg=NAVY, bg=CARD, bd=1, relief='solid', padx=12, pady=10)
        self.filters.pack(fill='x', pady=(0, 16))
        for index, (field, label) in enumerate(self.FILTERS):
            area = tk.Frame(self.filters, bg=CARD)
            area.grid(row=0, column=index, sticky='ew', padx=8)
            tk.Label(area, text=label, fg=NAVY, bg=CARD, font=('Segoe UI', 8, 'bold')).pack(anchor='w')
            box = ttk.Combobox(area, textvariable=self.filter_values[field], state='readonly', values=['All'])
            box.pack(fill='x', pady=(3, 0))
            box.bind('<<ComboboxSelected>>', lambda _event: self.render())
            self.filter_boxes[field] = box
            self.filters.columnconfigure(index, weight=1)
        self.button(self.filters, 'Clear filters', self.clear_filters, 'outline-secondary').grid(row=0, column=len(self.FILTERS), padx=8, pady=(14, 0))
        self.metrics_frame = tk.Frame(content, bg=PAGE)
        self.metrics_frame.pack(fill='x', pady=(0, 16))
        for index in range(5):
            card = tk.Frame(self.metrics_frame, bg=CARD, bd=1, relief='solid', padx=10, pady=7)
            card.grid(row=0, column=index, sticky='nsew', padx=5)
            self.metrics_frame.columnconfigure(index, weight=1)
            label = tk.Label(card, text='—', font=('Segoe UI', 9), fg=MUTED, bg=CARD)
            label.pack()
            value = tk.Label(card, text='—', font=('Segoe UI', 25, 'bold'), fg=NAVY, bg=CARD)
            value.pack()
            self.cards.append((label, value))
        grid = tk.Frame(content, bg=PAGE)
        grid.pack(fill='both', expand=True)
        for column, weight in enumerate((128, 78, 98)):
            grid.columnconfigure(column, weight=weight)
        grid.rowconfigure(0, weight=1)
        grid.rowconfigure(1, weight=1)
        self.make_panel(grid, 'Interns by role', 0, 0, 'role', HorizontalBars)
        self.make_panel(grid, 'Interns by gender', 0, 1, 'gender', Donut)
        self.make_panel(grid, 'Interns by university', 0, 2, 'university', HorizontalBars)
        self.make_panel(grid, 'Interns by supervisor', 1, 0, 'supervisor', HorizontalBars)
        self.make_recent_panel(grid, 1, 1)
        self.make_panel(grid, 'Interns by career', 1, 2, 'career', HorizontalBars)
        footer = tk.Frame(page, bg=PAGE, padx=24, pady=9)
        footer.pack(fill='x')
        tk.Label(footer, textvariable=self.status, fg=MUTED, bg=PAGE, font=('Segoe UI', 9)).pack(side='left')
        tk.Label(footer, textvariable=self.loaded, fg=MUTED, bg=PAGE, font=('Segoe UI', 9)).pack(side='right')

    def make_panel(self, parent, title, row, column, key, widget):
        frame = tk.Frame(parent, bg=CARD, bd=1, relief='solid', padx=10, pady=8)
        frame.grid(row=row, column=column, sticky='nsew', padx=5, pady=5)
        tk.Label(frame, text=title, fg='#07539A', bg=CARD, font=('Segoe UI', 10, 'bold')).pack(anchor='w')
        chart = widget(frame)
        chart.pack(fill='both', expand=True, pady=(4, 0))
        self.charts[key] = chart

    def make_recent_panel(self, parent, row, column):
        frame = tk.Frame(parent, bg=CARD, bd=1, relief='solid', padx=10, pady=8)
        frame.grid(row=row, column=column, sticky='nsew', padx=5, pady=5)
        tk.Label(frame, text='Recent interns', fg='#07539A', bg=CARD, font=('Segoe UI', 10, 'bold')).pack(anchor='w')
        holder = tk.Frame(frame, bg=CARD)
        holder.pack(fill='both', expand=True, pady=(5, 0))
        self.recent = ttk.Treeview(holder, show='headings', height=7)
        scroll = ttk.Scrollbar(holder, orient='vertical', command=self.recent.yview)
        self.recent.configure(yscrollcommand=scroll.set)
        self.recent.pack(side='left', fill='both', expand=True)
        scroll.pack(side='right', fill='y')

    def set_busy(self, busy):
        self.busy = busy
        for button in self.buttons:
            button.configure(state='disabled' if busy else 'normal')

    def run(self, task, complete):
        if self.busy:
            return
        self.set_busy(True)
        self.status.set('Loading data from Excel…')
        future = self.pool.submit(task)
        def poll():
            if not future.done():
                self.root.after(70, poll)
                return
            self.set_busy(False)
            try:
                complete(future.result())
            except Exception as error:
                self.status.set(str(error))
                messagebox.showerror('Could not load the dashboard', str(error))
        self.root.after(70, poll)

    def connect(self):
        self.run(lambda: excel_store.read(), self.loaded_snapshot)

    def refresh(self):
        if self.snapshot:
            self.run(lambda: excel_store.read(self.snapshot.path, self.snapshot.sheet), self.loaded_snapshot)
        else:
            self.connect()

    def loaded_snapshot(self, snapshot):
        self.snapshot, self.dashboard = snapshot, Dashboard.from_snapshot(snapshot)
        for field, _label in self.FILTERS:
            choices = self.dashboard.choices(field)
            self.filter_boxes[field].configure(values=choices)
            if self.filter_values[field].get() not in choices:
                self.filter_values[field].set('All')
        self.loaded.set(f'{len(snapshot.rows):,} records • {snapshot.sheet} • refreshed {datetime.now():%H:%M}')
        self.status.set('Connected to desktop Excel. Dashboard updates are local until Excel completes its SharePoint sync.')
        self.render()

    def clear_filters(self):
        for variable in self.filter_values.values():
            variable.set('All')
        self.render()

    def render(self):
        if not self.dashboard:
            return
        records = self.dashboard.filtered({field: value.get() for field, value in self.filter_values.items()})
        for widgets, (label, value) in zip(self.cards, self.dashboard.metrics(records)):
            widgets[0].configure(text=label)
            widgets[1].configure(text=str(value))
        for key, data in self.dashboard.charts(records).items():
            self.charts[key].set_data(data)
        rows, columns = self.dashboard.recent(records)
        self.recent.delete(*self.recent.get_children())
        self.recent.configure(columns=columns)
        for column in columns:
            self.recent.heading(column, text=column)
            self.recent.column(column, width=110, minwidth=75, stretch=True)
        for record in rows:
            self.recent.insert('', 'end', values=[display(record.get(column, ''), column) for column in columns])

    def close(self):
        self.pool.shutdown(wait=False)
        self.root.destroy()


if __name__ == '__main__':
    root = ttk.Window(themename='litera')
    DashboardApp(root)
    root.mainloop()
