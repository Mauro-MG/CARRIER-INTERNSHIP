import threading
import re
from copy import copy
from datetime import datetime
from pathlib import Path

import pandas as pd
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from tkinter import filedialog, messagebox
from tkinter.scrolledtext import ScrolledText

from openpyxl import load_workbook
from openpyxl.styles import PatternFill
from copy import copy
from openpyxl.utils import range_boundaries, get_column_letter, column_index_from_string
from openpyxl.worksheet.datavalidation import DataValidation
DDL_MAP = {
    "B": "L0 Meeting Review Date",
    "N": "Event/source",
    "O": "Bussiness",
    "U": "Yes/no list",
    "Z": "Engineering Complexity",
    "AB": "Engineering Complexity",
    "AE": "Quotes",
    "AF": "Quotes",
    "AG": "Change type",
    "AL": "Proposed Governance",
    "AM": "Testplan",
    "AN": "Yes/no list",
    "AQ": "Test Location",
}
DDL_COLUMNS = ["B", "N", "O", "U", "Z", "AB", "AE", "AF", "AG", "AL", "AM", "AN", "AQ"]
DROPDOWN_RANGES = {
    "Engineering Complexity": "'DropDowns'!$A$2:$A$4",
    "Quotes": "'DropDowns'!$A$7:$A$9",
    "Yes/no list": "'DropDowns'!$A$12:$A$14",
    "Change type": "'DropDowns'!$A$17:$A$32",
}

class L0ProcessorGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("L0 Project Processor")
        self.root.geometry("1100x750")

        self.new_data_path = ttk.StringVar()
        self.master_file_path = ttk.StringVar()
        self.status_var = ttk.StringVar(value="Ready")
        self.progress_var = ttk.IntVar(value=0)

        self.updated_logs = []
        self.added_logs = []
        self.not_found_logs = []

        self._build_ui()

    def _build_ui(self):
        top_frame = ttk.Frame(self.root, padding=15)
        top_frame.pack(fill=X)

        ttk.Label(top_frame, text="New Data File:", width=16).grid(row=0, column=0, sticky=W, pady=6)
        ttk.Entry(top_frame, textvariable=self.new_data_path, width=80).grid(row=0, column=1, padx=5, pady=6, sticky=EW)
        ttk.Button(top_frame, text="Browse", bootstyle=PRIMARY, command=self.browse_new_data).grid(row=0, column=2, padx=5, pady=6)

        ttk.Label(top_frame, text="Master File:", width=16).grid(row=1, column=0, sticky=W, pady=6)
        ttk.Entry(top_frame, textvariable=self.master_file_path, width=80).grid(row=1, column=1, padx=5, pady=6, sticky=EW)
        ttk.Button(top_frame, text="Browse", bootstyle=PRIMARY, command=self.browse_master_file).grid(row=1, column=2, padx=5, pady=6)

        top_frame.columnconfigure(1, weight=1)

        action_frame = ttk.Frame(self.root, padding=(15, 0, 15, 10))
        action_frame.pack(fill=X)

        ttk.Button(
            action_frame,
            text="Run Process",
            bootstyle=SUCCESS,
            command=self.start_processing
        ).pack(side=LEFT)


        self.progress = ttk.Progressbar(
            action_frame,
            variable=self.progress_var,
            maximum=100,
        )
        self.progress.pack(side=LEFT, fill=X, expand=True, padx=10)

        self.progress_label = ttk.Label(action_frame, text="0%")
        self.progress_label.pack(side=LEFT, padx=5)

        notebook = ttk.Notebook(self.root, bootstyle=PRIMARY)
        notebook.pack(fill=BOTH, expand=True, padx=15, pady=10)

        self.updated_text = ScrolledText(notebook, wrap="word", font=("Consolas", 10))
        self.added_text = ScrolledText(notebook, wrap="word", font=("Consolas", 10))
        self.not_found_text = ScrolledText(notebook, wrap="word", font=("Consolas", 10))

        notebook.add(self.updated_text, text="Updated")
        notebook.add(self.added_text, text="Added")
        notebook.add(self.not_found_text, text="Not Found / Moved")


    def browse_new_data(self):
        file_path = filedialog.askopenfilename(
            title="Select New Data File",
            filetypes=[("Excel files", "*.xlsx *.xlsm *.xls"), ("All files", "*.*")]
        )
        if file_path:
            self.new_data_path.set(file_path)

    def browse_master_file(self):
        file_path = filedialog.askopenfilename(
            title="Select Master File",
            filetypes=[("Excel files", "*.xlsx *.xlsm *.xls"), ("All files", "*.*")]
        )
        if file_path:
            self.master_file_path.set(file_path)

    def set_progress(self, value, status=None):
        value = int(value)
        self.progress_var.set(value)

        # Update % label
        self.progress_label.config(text=f"{value}%")

        if status:
            self.status_var.set(status)

        self.root.update_idletasks()

    def append_log(self, widget, text):
        widget.insert("end", text + "\n")
        widget.see("end")
        self.root.update_idletasks()

    def clear_logs(self):
        self.updated_text.delete("1.0", "end")
        self.added_text.delete("1.0", "end")
        self.not_found_text.delete("1.0", "end")

    def start_processing(self):
        if not self.new_data_path.get().strip():
            messagebox.showerror("Missing file", "Please select the New Data file.")
            return
        if not self.master_file_path.get().strip():
            messagebox.showerror("Missing file", "Please select the Master file.")
            return

        self.clear_logs()
        self.updated_logs.clear()
        self.added_logs.clear()
        self.not_found_logs.clear()

        threading.Thread(target=self.run_processing, daemon=True).start()

    def run_processing(self):
        try:
            self.set_progress(5, "Loading files...")

            # =========================
            # 1. LOAD FILES
            # =========================
            new_data_file = self.new_data_path.get().strip()
            master_file = self.master_file_path.get().strip()
            master_sheet = 'L0_meeting'

            data_df = pd.read_excel(new_data_file)
            data_df.columns = data_df.columns.str.strip().str.replace(r'\s+', ' ', regex=True)

            self.set_progress(12, "Preparing keys...")

            # =========================
            # 2. PREPARE KEYS
            # =========================
            data_df['ID'] = data_df['ID'].fillna('').astype(str).str.strip().str.replace(r'\.0$', '', regex=True)
            data_df['Site'] = data_df['Site'].fillna('').astype(str).str.strip()
            data_df['UniqueID'] = data_df['ID'] + " " + data_df['Site']

            

            # =========================
            # 3. PREPARE PIPELINE VALUE
            # =========================
            if 'L0 Pipeline Annualized $M' in data_df.columns:
                data_df['L0 Pipeline Annualized $M'] = pd.to_numeric(
                    data_df['L0 Pipeline Annualized $M'], errors='coerce'
                )
                data_df['L0 Pipeline Annualized $'] = data_df['L0 Pipeline Annualized $M'] * 1_000
            elif 'L0 Pipeline Annualized $' in data_df.columns:
                data_df['L0 Pipeline Annualized $'] = pd.to_numeric(
                    data_df['L0 Pipeline Annualized $'], errors='coerce'
                )
            else:
                data_df['L0 Pipeline Annualized $'] = None

            self.set_progress(28, "Validating Unique IDs...")

            # =========================
            # 2B. FILTER NEW DATA
            # =========================
            allowed_sites = [
                "Charlotte, NC",
                "CHVAC - RHQ",
                "CMX-C new site - CML",
                "CMX-C new site - RES",
                "CMX-F",
                "CMX-G",
                "CMX-T",
                "Collierville, TN",
                "Indianapolis, IN",
                "HVAC HQ",
                "Mexico Commercial (B)",
                "Mexico Light Commercial (D)",
                "Mexico Light Commercial (C)",
                "Mexico Plant E",
                "Mexico Residential (A)",
                "RCD (Replacement Components)",
                "RHQ - HVAC Americas",
                "RHQ HVAC Americas",
                "C - CHVAC - NA – HQ",
                "CCS WHQ"
            ]

            allowed_categories = ["Schedule B", "Schedule C"]

            data_df['BU'] = data_df['BU'].fillna('').astype(str).str.strip()
            data_df['Site'] = data_df['Site'].fillna('').astype(str).str.strip()
            data_df['Classification'] = data_df['Classification'].fillna('').astype(str).str.strip()

            filtered_df = data_df[
                (data_df['Site'].isin(allowed_sites)) &
                (data_df['Classification'].isin(allowed_categories))
            ].copy()

            self.set_progress(20, f"Filtered rows: {len(filtered_df)}")

            # =========================
            # 4. VALIDATE UNIQUE ID
            # =========================
            pattern = r"^\d{5} .+$"
            valid_mask = filtered_df['UniqueID'].str.match(pattern)
            invalid_ids = filtered_df[~valid_mask]
            valid_data_df = filtered_df[valid_mask]

            self.set_progress(36, f"Valid rows: {len(valid_data_df)} | Invalid: {len(invalid_ids)}")

            # =========================
            # 5. OPEN MASTER WORKBOOK
            # =========================
            wb = load_workbook(master_file)
            ws = wb[master_sheet]
            

            wb_values = load_workbook(master_file, data_only=True)
            ws_values = wb_values[master_sheet]

            def find_last_used_row(ws, cols_to_check):
                for row in range(ws.max_row, 0, -1):
                    for col in cols_to_check:
                        value = ws[f"{col}{row}"].value
                        if value not in (None, ''):
                            return row
                return 1
            def find_dropdown_column(ws_dropdowns, header_name):
                target = str(header_name).strip().lower()

                for row in range(1, min(ws_dropdowns.max_row, 10) + 1):
                    for col in range(1, ws_dropdowns.max_column + 1):
                        value = ws_dropdowns.cell(row=row, column=col).value

                        if value is not None and str(value).strip().lower() == target:
                            return col

                return None


            def build_dropdown_formula(ws_dropdowns, header_name):
                if header_name in DROPDOWN_RANGES:
                    return DROPDOWN_RANGES[header_name]

                col_idx = find_dropdown_column(ws_dropdowns, header_name)

                if col_idx is None:
                    print(f"Dropdown header not found: {header_name}")
                    return None

                start_row = None
                end_row = None

                for r in range(2, ws_dropdowns.max_row + 1):
                    value = ws_dropdowns.cell(row=r, column=col_idx).value
 
                    if value not in (None, ""):
                        if start_row is None:
                            start_row = r
                        end_row = r

                if start_row is None:
                    print(f"No dropdown values found for: {header_name}")
                    return None

                col_letter = get_column_letter(col_idx)
                return f"'dropdowns'!${col_letter}${start_row}:${col_letter}${end_row}"


            def apply_dropdown_validations(wb, ws, start_row, end_row):
                if "DropDowns" not in wb.sheetnames:
                    print("Sheet 'dropdowns' not found. Cannot apply dropdowns.")
                    return

                ws_dropdowns = wb["DropDowns"]

                print("\n========== APPLYING DROPDOWN VALIDATIONS ==========")

                for target_col, header_name in DDL_MAP.items():
                    formula = build_dropdown_formula(ws_dropdowns, header_name)

                    if formula is None:
                        print(f"Skipped {target_col}: {header_name}")
                        continue

                    dv = DataValidation(
                        type="list",
                        formula1=formula,
                        allow_blank=True
                    )

                    ws.add_data_validation(dv)

                    cell_range = f"{target_col}{start_row}:{target_col}{end_row}"
                    dv.add(cell_range)

                    print(f"Applied {header_name} -> {cell_range} using {formula}")

                print("==================================================\n")

            def copy_row_format(ws, source_row, target_row, max_col):
                for col in range(1, max_col + 1):
                    source_cell = ws.cell(row=source_row, column=col)
                    target_cell = ws.cell(row=target_row, column=col)

                    if source_cell.has_style:
                        target_cell.font = copy(source_cell.font)
                        target_cell.fill = copy(source_cell.fill)
                        target_cell.border = copy(source_cell.border)
                        target_cell.alignment = copy(source_cell.alignment)
                        target_cell.protection = copy(source_cell.protection)
                        target_cell.number_format = source_cell.number_format
            
            def is_blank(value):
                if value is None:
                    return True
                try:
                    if pd.isna(value):
                        return True
                except Exception:
                    pass
                return str(value).strip() == ''

            last_row = find_last_used_row(ws, ['A', 'E', 'F', 'G', 'I', 'J', 'L', 'M'])
            next_row = last_row + 1
            template_row = last_row

            self.set_progress(45, "Rebuilding master Unique IDs...")


            # =========================
            # 5B. REBUILD COLUMN E FOR EXISTING ROWS
            # =========================
            for r in range(2, last_row + 1):
                id_value = ws[f'A{r}'].value
                site_value = ws[f'I{r}'].value

                id_text = '' if id_value is None else str(id_value).strip().replace('.0', '')
                site_text = '' if site_value is None else str(site_value).strip()

                if id_text or site_text:
                    ws[f'E{r}'] = f"{id_text} {site_text}".strip()

            # =========================
            # 5C. BUILD MASTER LOOKUP
            # =========================
            master_lookup = {}

            for r in range(2, last_row + 1):
                unique_id = ws[f'E{r}'].value
                if unique_id is not None and str(unique_id).strip() != '':
                    master_lookup[str(unique_id).strip()] = r

           

            # =========================
            # 6. INSERT OR UPDATE
            # =========================
            added_count = 0
            updated_count = 0
            unchanged_count = 0
            _50k_count = 0

            yellow_fill = PatternFill(start_color='FFFF00', end_color='FFFF00', fill_type='solid')


            total_valid = max(len(valid_data_df), 1)

            for idx, (_, row) in enumerate(valid_data_df.iterrows(), start=1):
                unique_id = str(row.get('UniqueID', '')).strip()

                new_id = str(row.get('ID', '')).strip()
                new_name = row.get('Name', row.get('Project description', ''))
                new_owner = row.get('Project Owner', '')
                new_site = row.get('Site', '')
                new_savings = row.get('L0 Pipeline Annualized $', None)
                new_stage = row.get('L0 Stage', '')
                new_category = row.get('Category', '')

                new_savings_num = pd.to_numeric(new_savings, errors='coerce')
                if not pd.isna(new_savings_num):
                    new_savings_num = round(float(new_savings_num), 3)

                if unique_id in master_lookup:
                    master_row = master_lookup[unique_id]
                    changed = False
                    reasons = []

                    current_site = ws_values[f'I{master_row}'].value
                    current_stage = ws_values[f'L{master_row}'].value
                    current_category = ws_values[f'M{master_row}'].value
                    current_savings = ws_values[f'J{master_row}'].value

                    stage_formula = ws[f'L{master_row}'].value
                    category_formula = ws[f'M{master_row}'].value
                    savings_formula = ws[f'J{master_row}'].value

                    stage_is_formula = isinstance(stage_formula, str) and stage_formula.startswith("=")
                    category_is_formula = isinstance(category_formula, str) and category_formula.startswith("=")
                    savings_is_formula = isinstance(savings_formula, str) and savings_formula.startswith("=")

                    # SITE
                    if not is_blank(new_site):
                        if str(current_site).strip() != str(new_site).strip():
                            reasons.append(f"Site: {repr(current_site)} -> {repr(new_site)}")
                            ws[f'I{master_row}'] = new_site
                            changed = True

                    # STAGE
                    if not is_blank(new_stage):
                        if not (stage_is_formula and current_stage is None):
                            if str(current_stage).strip() != str(new_stage).strip():
                                reasons.append(f"Stage: {repr(current_stage)} -> {repr(new_stage)}")
                                ws[f'L{master_row}'] = new_stage
                                changed = True

                    # CATEGORY
                    if not is_blank(new_category):
                        if not (category_is_formula and current_category is None):
                            if str(current_category).strip() != str(new_category).strip():
                                reasons.append(f"Category: {repr(current_category)} -> {repr(new_category)}")
                                ws[f'M{master_row}'] = new_category
                                changed = True

                    # SAVINGS
                    current_savings_num = pd.to_numeric(current_savings, errors='coerce')
                    if not pd.isna(current_savings_num):
                        current_savings_num = round(float(current_savings_num), 3)

                    if not pd.isna(new_savings_num):
                        new_savings_num = round(float(new_savings_num), 3)

                    if not is_blank(new_savings):
                        if not (savings_is_formula and current_savings is None):
                            if (
                                pd.isna(current_savings_num)
                                or pd.isna(new_savings_num)
                                or abs(current_savings_num - new_savings_num) > 0.01
                            ):
                                reasons.append(
                                    f"Savings: {repr(current_savings_num)} -> {repr(new_savings_num)}"
                                )
                                ws[f'J{master_row}'] = new_savings
                                changed = True

                    if not pd.isna(new_savings_num) and new_savings_num >= 50000:
                        for cell in ws[master_row]:
                            cell.fill = yellow_fill
                        _50k_count += 1

                    if changed:
                        updated_count += 1
                        details_text = " | ".join(reasons) if reasons else "Changed but no reason captured"
                        msg = f"Updated | Row {master_row} | {unique_id} | {details_text}"
                        self.updated_logs.append(msg)
                        self.append_log(self.updated_text, msg)
                    else:
                        unchanged_count += 1

                else:
                    copy_row_format(ws, template_row, next_row, ws.max_column)

                    ws[f'A{next_row}'] = row.get('ID', '')
                    ws[f'F{next_row}'] = new_name
                    ws[f'G{next_row}'] = new_owner
                    ws[f'D{next_row}'] = datetime.now()
                    ws[f'I{next_row}'] = new_site
                    ws[f'E{next_row}'] = f"{new_id} {new_site}".strip()
                    ws[f'J{next_row}'] = new_savings
                    ws[f'L{next_row}'] = new_stage
                    ws[f'M{next_row}'] = new_category

                    if not pd.isna(new_savings_num) and new_savings_num >= 50000:
                        for cell in ws[next_row]:
                            cell.fill = yellow_fill
                        _50k_count += 1

                    master_lookup[unique_id] = next_row
                    msg = f"Added   | Row {next_row} | {unique_id}"
                    self.added_logs.append(msg)
                    self.append_log(self.added_text, msg)

                    next_row += 1
                    added_count += 1

                pct = 45 + int((idx / total_valid) * 30)
                self.set_progress(min(pct, 75), f"Processing records... {idx}/{total_valid}")

            self.set_progress(78, "Marking NOT FOUND records...")

            # =========================
            # 6B. MARK MASTER RECORDS NOT FOUND IN NEW DATA
            # =========================
            new_data_unique_ids = set(
                valid_data_df['UniqueID']
                .fillna('')
                .astype(str)
                .str.strip()
            )

            not_found_count = 0

            for r in range(2, last_row + 1):
                master_unique_id = ws[f'E{r}'].value
                master_id = ws[f'A{r}'].value

                if master_unique_id is None or not re.match(pattern, str(master_unique_id)):
                    continue

                master_unique_id = str(master_unique_id).strip()

                if master_unique_id.endswith("NOT FOUND"):
                    continue

                if master_unique_id != '' and master_unique_id not in new_data_unique_ids:
                    id_text = '' if master_id is None else str(master_id).strip().replace('.0', '')

                    if id_text != '':
                        ws[f'E{r}'] = f"{id_text} NOT FOUND"
                        not_found_count += 1

            self.set_progress(86, "Moving NOT FOUND rows...")

            # =========================
            # 6C. MOVE NOT FOUND ROWS TO List_Moved
            # =========================
            if 'List_Moved' in wb.sheetnames:
                ws_moved = wb['List_Moved']
            else:
                ws_moved = wb.create_sheet('List_Moved')

            moved_count = 0
            rows_to_delete = []

            # find next empty row in List_Moved
            def find_next_empty_row(ws):
                for row in range(ws.max_row, 0, -1):
                    for col in range(1, ws.max_column + 1):
                        if ws.cell(row=row, column=col).value not in (None, ''):
                            return row + 1
                return 1

            next_moved_row = find_next_empty_row(ws_moved)

            for r in range(2, last_row + 1):
                unique_id_value = ws[f'E{r}'].value

                if unique_id_value is None:
                    continue

                unique_id_value = str(unique_id_value).strip()

                if unique_id_value.endswith("NOT FOUND"):
                    # append whole row VALUES to List_Moved
                    for col in range(1, ws.max_column + 1):
                        source_cell = ws.cell(row=r, column=col)                 # for style
                        source_value_cell = ws_values.cell(row=r, column=col)    # for displayed value
                        target_cell = ws_moved.cell(row=next_moved_row, column=col)

                        if isinstance(source_cell.value, str) and source_cell.value.startswith("="):
                            target_cell.value = source_value_cell.value
                        else:
                            target_cell.value = source_cell.value


                        # copy formatting
                        if source_cell.has_style:
                            target_cell.font = copy(source_cell.font)
                            target_cell.fill = copy(source_cell.fill)
                            target_cell.border = copy(source_cell.border)
                            target_cell.alignment = copy(source_cell.alignment)
                            target_cell.protection = copy(source_cell.protection)
                            target_cell.number_format = source_cell.number_format

                    # copy BC value into J in List_Moved, using values not formulas
                    bc_value = ws_moved[f"BC{next_moved_row}"].value
                    if bc_value not in (None, ''):
                        ws_moved[f"J{next_moved_row}"] = bc_value

                    # copy row height
                    ws_moved.row_dimensions[next_moved_row].height = ws.row_dimensions[r].height

                    moved_count += 1
                    rows_to_delete.append(r)

                    last_not_found = ws[f'E{r}'].value
                    msg = f"Moved    | From row {r} -> List_Moved row {next_moved_row} | {last_not_found}"
                    self.not_found_logs.append(msg)
                    self.append_log(self.not_found_text, msg)

                    next_moved_row += 1

            # delete moved rows from L0_meeting, bottom to top
            for r in sorted(rows_to_delete, reverse=True):
                ws.delete_rows(r, 1)


            self.set_progress(94, "Saving updated workbook...")

            # =========================
            # 7. SAVE OUTPUT
            # =========================
            master_path = Path(master_file)
            output_file = str(master_path.with_name(f"{master_path.stem} Updated{master_path.suffix}"))
            final_last_row = find_last_used_row(
                ws,
                ['A', 'E', 'F', 'G', 'I', 'J', 'L', 'M']
            )
            apply_dropdown_validations(wb, ws, start_row=2, end_row=final_last_row)

            wb.save(output_file)

            self.set_progress(100, "Completed")

            summary = (
                f"Master file updated successfully:\n{output_file}\n\n"
                f"Added records: {added_count}\n"
                f"Records over 50k USD: {_50k_count}\n"
                f"NOT FOUND records: {not_found_count}\n"
                f"Moved NOT FOUND rows: {moved_count}\n"
                f"Updated existing records: {updated_count}\n"
                f"Unchanged existing records: {unchanged_count}\n"
                f"Invalid records skipped: {len(invalid_ids)}"
            )

            messagebox.showinfo("Process completed", summary)

        except Exception as e:
            self.set_progress(0, "Error")
            messagebox.showerror("Processing error", str(e))


if __name__ == "__main__":
    app = ttk.Window(themename="cosmo")
    L0ProcessorGUI(app)
    app.mainloop()