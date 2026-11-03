import tkinter as tk
from tkinter import filedialog, ttk, messagebox
from tkinter.messagebox import showinfo
import threading
import xml.etree.ElementTree as ET
import os
import re
from pathlib import Path
import pandas as pd
import platform
import subprocess
from PIL import Image, ImageTk
import sys
import webbrowser
import sv_ttk
from concurrent.futures import ThreadPoolExecutor, as_completed

def resource_path_logo(relative_path_logo):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path_logo)
    return os.path.join(os.path.abspath("."), relative_path_logo)

if getattr(sys, 'frozen', False): 
    base_path = sys._MEIPASS
else:
    base_path = os.path.dirname(__file__)

icon_path = os.path.join(base_path, 'AHUQ-icon.ico')

def query_window():
    should_stop = False

    query_win = tk.Toplevel()
    query_win.iconbitmap(icon_path)
    root.withdraw()
    query_win.title("AHU XML Query")
    query_win.geometry("1024x768")
    query_win.columnconfigure(0, weight=1)
    query_win.columnconfigure(1, weight=1)
    query_win.rowconfigure(4, weight=1)

    # Estilos
    style_query = ttk.Style()
    style_query.configure("TLabel", font=("Segoe UI", 10))
    style_query.configure("TButton", font=("Segoe UI", 10))
    style_query.configure("TCombobox", font=("Segoe UI", 10))
    style_query.configure("Small.TButton", font=("Segoe UI", 8), padding=2)

    topbar = ttk.Frame(query_win)
    topbar.grid(row=0, column=0, columnspan=2, sticky="ew", padx=10, pady=(10, 0))
    topbar.columnconfigure((0,1,2), weight=1)

    def back_root():
        query_win.destroy()
        root.deiconify()

    ttk.Button(topbar, text="🔙 Back", command=back_root, style="Small.TButton").grid(row=0, column=0, sticky="w")
    ttk.Label(topbar, text="AHU XML Query Tool", font=("Segoe UI", 16, "bold")).grid(row=0, column=1, sticky="n", pady=(0, 5))

    def open_feedback_form(event=None):
        webbrowser.open_new_tab("https://forms.office.com/r/hRNvBVSwnm")
    feedback_link = tk.Label(topbar, text="⚠️ Report/Feedback", cursor="hand2", font=("Segoe UI", 9, "underline"))
    feedback_link.grid(row=0, column=2, sticky="e")
    feedback_link.bind("<Button-1>", open_feedback_form)

    # ProgressBar
    progress = ttk.Progressbar(query_win, orient="horizontal", length=600, mode="determinate")
    progress.grid(row=1, column=0, columnspan=2, pady=10, padx=10, sticky="ew")
    progress.grid_remove()

    # Seleccionar Folder
    def select_folder():
        folder_path = filedialog.askdirectory()
        if folder_path:
            folder_label.config(text=f"📂 Selected Folder: {folder_path}")
            global xml_files
            xml_files = [os.path.join(folder_path, f) for f in os.listdir(folder_path) if f.lower().endswith('.xml')]
            file_count_label.config(text=f"Number of XML files: {len(xml_files)}")

    folder_frame = ttk.LabelFrame(query_win, text="📁 Folder Selection")
    folder_frame.grid(row=2, column=0, columnspan=2, padx=10, pady=8, sticky="ew")
    select_button = ttk.Button(folder_frame, text="Select Folder", command=select_folder, style="Small.TButton")
    select_button.grid(row=0, column=0, padx=10, pady=4, sticky="w")
    folder_label = ttk.Label(folder_frame, text="📂 No folder selected")
    folder_label.grid(row=0, column=1, sticky="w", padx=5)
    file_count_label = ttk.Label(folder_frame, text="Number of XML files: 0")
    file_count_label.grid(row=1, column=0, columnspan=2, sticky="w", padx=10)

    top_section_frame = ttk.Frame(query_win)
    top_section_frame.grid(row=3, column=0, columnspan=2, padx=10, sticky="nsew")
    top_section_frame.columnconfigure((0,1), weight=1, uniform="equal")

    input_frame = ttk.LabelFrame(top_section_frame, text="🔍 Query Input")
    input_frame.grid(row=3, column=0, columnspan=2, padx=(2.5,5), pady=10, sticky="nsew")

    label_button_frame = ttk.Frame(input_frame)
    label_button_frame.grid(row=0, column=0, columnspan=2, sticky="w", padx=5, pady=5)
    ttk.Label(label_button_frame, text="Enter your regex queries (one per line):").pack(side="left")

    query_entry = tk.Text(input_frame, height=4, width=90, font=("Courier", 10))
    query_entry.grid(row=1, column=0, padx=5, pady=5)

    def insert_caret():
        query_entry.insert(tk.INSERT, '^')
    def insert_bracket_pair():
        query_entry.insert(tk.INSERT, '[]')
        query_entry.mark_set(tk.INSERT, f"{query_entry.index(tk.INSERT)}-1c")

    ttk.Button(label_button_frame, text="Insert ^", command=insert_caret, style="Small.TButton").pack(side="left", padx=(10, 0))
    ttk.Button(label_button_frame, text="Insert [ ]", command=insert_bracket_pair, style="Small.TButton").pack(side="left", padx=(5,0))

    frame = ttk.LabelFrame(top_section_frame, text="⚒️Action")
    frame.grid(row=3, column=2, padx=(5,2.5), pady=10, sticky="nse")
    ttk.Label(frame, text="Please select an action:").grid(row=0, column=0, padx=5, pady=5)

    actions = ["LocationID", "Qty", "Points", "Description", "Icons"]
    selected_action = tk.StringVar()
    dropdown = ttk.Combobox(frame, textvariable=selected_action, values=actions, state="readonly", width=30)
    dropdown.set("Select an action")
    dropdown.grid(row=1, column=0, padx=5, pady=5)

    def hide_icons(event=None):
        if selected_action.get() == "Icons":
            input_frame.grid_remove()
        else:
            input_frame.grid()
    dropdown.bind("<<ComboboxSelected>>", hide_icons)

    processing_animation_running = False
    animation_index = 0
    animation_symbols = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

    def animate_status():
        nonlocal animation_index
        if processing_animation_running:
            symbol = animation_symbols[animation_index % len(animation_symbols)]
            status_query.config(text=f"{symbol} Processing... please wait")
            animation_index += 1
            query_win.after(150, animate_status)
            
    
    # Proceso
    def execute_query():
        nonlocal should_stop, processing_animation_running
        should_stop = False
        processing_animation_running = False

        if 'xml_files' not in globals() or not xml_files:
            tk.messagebox.showwarning("No XML Files", "Please select a folder containing XML files before executing the query.")
            return
        if selected_action.get() not in actions:
            tk.messagebox.showwarning("No Action Selected", "Please select a valid action before executing the query.")
            return

        disable_controls()
        status_query.config(text="Processing...", foreground="blue")
        animation_states = ["Processing.", "Processing..", "Processing..."]
        animation_index = 0
        processing_animation_running = True

        def animate_status():
            nonlocal animation_index
            if processing_animation_running:
                status_query.config(text=animation_states[animation_index])
                animation_index = (animation_index + 1) % len(animation_states)
                query_win.after(400, animate_status)
        animate_status()

        try:
            queries = query_entry.get("1.0", tk.END).strip().split('\n')
            regexes = [re.compile(q) for q in queries if q.strip()]
            results = []
            total_files = len(xml_files)
            progress.grid()
            progress["maximum"] = total_files
            progress["value"] = 0
            query_win.update_idletasks()

            def find_text(elem, tag):
                node = elem.find(tag)
                return node.text if node is not None else ""

            def execute_action(action, elem, part_number, Odometer39M):
                out = []
                if action == "LocationID":
                    out.append(f"{Odometer39M}\t{part_number}\t{find_text(elem, 'locationNumber')}")
                elif action == "Qty":
                    out.append(f"{Odometer39M}\t{part_number}\t{find_text(elem, 'quantity')}")
                elif action == "Points":
                    for child in elem.findall('points'):
                        points = ', '.join(f'{k}: {child.get(k)}' for k in ['xl','yl','zl','xu','yu','zu'] if child.get(k))
                        out.append(f"{Odometer39M}\t{part_number}\t{points}")
                elif action == "Description":
                    out.append(f"{Odometer39M}\t{part_number}\t{find_text(elem, 'description')}")
                return out

            def process_xml(xml_file):
                if should_stop:
                    return []

                local_results = []
                try:
                    tree = ET.parse(xml_file)
                    root_xml = tree.getroot()
                    Odometer39M = os.path.splitext(os.path.basename(xml_file))[0]

                    for elem in root_xml.iter():
                        if should_stop:
                            return local_results

                        for child in elem:
                            if child.tag == 'partNumber':
                                part_number = child.text
                                for regex in regexes:
                                    if regex.search(part_number):
                                        local_results.extend(execute_action(selected_action.get(), elem, part_number, Odometer39M))
                                        break

                    # ICONS
                    if not should_stop and selected_action.get() == "Icons":
                        lista_items = [
                            item for item in root_xml.findall('.//manufacturing/manufacturedItem')
                            if item.find('partNumber') is not None and item.find('partNumber').text and
                            (item.find('partNumber').text.strip().startswith("39MN") or
                            item.find('partNumber').text.strip().startswith("39MW"))
                        ]
                        for item in lista_items:
                            if should_stop:
                                return local_results

                            Split39M = item.find('partNumber').text.strip()
                            icon_elements = item.findall('.//icon')
                            icon_textos = [icon.text.strip() for icon in icon_elements if icon.text]
                            if not icon_textos:
                                vf_parts = [
                                    f"{pn.text.strip()} VFD FIELD MOUNTED AND SHIPPED AS SEPARATE SEQUENCE"
                                    for pn in item.findall('.//partNumber')
                                    if pn.text and pn.text.strip().startswith('93VF')
                                ]
                                lista_iconos = vf_parts if vf_parts else ["['']"]
                            else:
                                lista_iconos = icon_textos
                            local_results.append(f"{Split39M}\t{lista_iconos}")

                except Exception as e:
                    local_results.append(f"Error in {xml_file}: {e}")

                return local_results

            with ThreadPoolExecutor(max_workers=6) as executor:
                futures = {executor.submit(process_xml, f): f for f in xml_files}
                for i, future in enumerate(as_completed(futures)):
                    if should_stop:
                        executor.shutdown(cancel_futures=True)
                        break
                    results.extend(future.result())
                    progress["value"] = i + 1
                    query_win.update_idletasks()

            progress.grid_remove()
            result_text.delete(1.0, tk.END)
            result_text.insert(tk.END, "\n".join(results))

            with open('query_results.txt', 'w', encoding="utf-8") as f:
                f.write("\n".join(results))
            status_query.config(
                text=f"{len(results)} result(s) found. Saved to query_results.txt.",
                foreground="green"
            )

        finally:
            processing_animation_running = False
            if should_stop:
                status_query.config(text="⛔ Query stopped by user", foreground="red")
                query_win.after(2000, lambda: status_query.config(text="Ready", foreground="black"))
            else:
                status_query.config(foreground="black")
            enable_controls()

    def stop_processing():
        nonlocal should_stop
        should_stop = True
        status_query.config(text="⛔ Query stopped by user")
        query_win.after(2000, lambda: status_query.config(text="Ready"))


    button_row = ttk.Frame(frame)
    button_row.grid(row=2, column=0, pady=10, sticky="ew")
    button_row.columnconfigure((0,1,2), weight=1)

    ttk.Button(button_row, text="Execute Query", command=lambda: threading.Thread(target=execute_query).start(), style="Small.TButton").grid(row=0, column=0, sticky="e", padx=(0,5))
    ttk.Button(button_row, text="Stop Query", command=stop_processing, style="Small.TButton").grid(row=0, column=1, padx=5)

    search_frame = ttk.Frame(query_win)
    search_frame.grid(row=4, column=0, columnspan=2, sticky="ew", padx=10)
    ttk.Label(search_frame, text="Search in results:").grid(row=0, column=0, padx=(0, 5), pady=5, sticky="w")
    search_var = tk.StringVar()
    search_entry = ttk.Entry(search_frame, textvariable=search_var, width=40)
    search_entry.grid(row=0, column=1, pady=5, sticky="w")

    def highlight_search():
        result_text.tag_remove('highlight', '1.0', tk.END)
        term = search_var.get()
        if term:
            idx = '1.0'
            while True:
                idx = result_text.search(term, idx, nocase=1, stopindex=tk.END)
                if not idx:
                    break
                lastidx = f"{idx}+{len(term)}c"
                result_text.tag_add('highlight', idx, lastidx)
                idx = lastidx
            result_text.tag_config('highlight', background='yellow', foreground='black')

    ttk.Button(search_frame, text="Search", command=highlight_search, style="Small.TButton").grid(row=0, column=2, padx=5)
    ttk.Button(search_frame, text="Clear Results", command=lambda: (result_text.delete(1.0, tk.END), status_query.config(text="Ready", foreground="black")), style="Small.TButton").grid(row=0, column=3, padx=5)


    result_label = ttk.Label(query_win, text="Results:")
    result_label.grid(row=5, column=0, columnspan=2, sticky="w", padx=10, pady=(10, 0))

    result_frame = ttk.Frame(query_win)
    result_frame.grid(row=6, column=0, columnspan=2, padx=10, pady=(0, 10), sticky="nsew")
    query_win.rowconfigure(6, weight=1)
    result_text = tk.Text(result_frame, height=20, width=120, font=("Courier", 10), wrap="none")
    result_text.pack(side=tk.LEFT, fill="both", expand=True)
    scrollbar = ttk.Scrollbar(result_frame, orient="vertical", command=result_text.yview)
    scrollbar.pack(side=tk.RIGHT, fill="y")
    result_text.configure(yscrollcommand=scrollbar.set)

    status_query = ttk.Label(query_win, text="Ready", relief="sunken", anchor="w")
    status_query.grid(row=7, column=0, columnspan=2, sticky="ew")

    def disable_controls():
        for w in [query_entry, search_entry]:
            w.config(state="disabled")
        dropdown.config(state="disabled")
        for child in button_row.winfo_children():
            if child.cget("text") != "Stop Query":
                child.config(state="disabled")

        select_button.config(state="disabled")

    def enable_controls():
        for w in [query_entry, search_entry]:
            w.config(state="normal")
        dropdown.config(state="readonly")
        for child in button_row.winfo_children():
            child.config(state="normal")
        select_button.config(state="normal")

    query_win.protocol("WM_DELETE_WINDOW", lambda: root.destroy())

#xploder

def xploder_window():
    root.withdraw()
    xploder_win = tk.Toplevel()
    xploder_win.iconbitmap(icon_path)
    xploder_win.title("AHU Xploder Test MTH")
    xploder_win.geometry("1024x768")
    xploder_win.minsize(800, 600)

    cancel_event = threading.Event()

    xploder_win.columnconfigure(0, weight=1)
    xploder_win.rowconfigure(3, weight=1)

    style_xploder = ttk.Style()
    style_xploder.configure("TButton", font=("Segoe UI", 9), padding=2)
    style_xploder.configure("TLabel", font=("Segoe UI", 10))

    xploder_folder = ""

    def select_xploderfolder():
        nonlocal xploder_folder
        folder = filedialog.askdirectory()
        if folder:
            xploder_folder = folder
            folder_label.config(text=f"📁 {folder}")

    def process_folder(pn_entry, folder_rule):
        xploder_out = []

        for xploder_file in os.listdir(folder_rule):
            if not xploder_file.lower().endswith(".rule"):
                continue

            try:
                xploder_path = os.path.join(folder_rule, xploder_file)
                with open(xploder_path, 'r', encoding='utf-8') as f:
                    lines = [line.strip() for line in f if line.strip()]
            except Exception as e:
                messagebox.showerror("Error", f"Error reading file: {xploder_file}\n{str(e)}")
                cancel_event.set()
                break

            inside_rule = False
            text1_labels = []
            appliesto_regex = None
            error_if_not_added = None
            error_if_more_than_one = None
            matches = []

            for line in lines:
                if cancel_event.is_set():
                    return xploder_out

                if line.startswith("RuleBegin"):
                    inside_rule = True
                    parts = re.split(r'\s{2,}|\t+', line)
                    text1_labels = parts[2:]
                    appliesto_regex = None
                    error_if_not_added = None
                    error_if_more_than_one = None
                    matches = []
                    continue

                if line == "RuleEnd":
                    if not appliesto_regex or not re.search(appliesto_regex, pn_entry):
                        inside_rule = False
                        continue

                    if len(matches) == 0:
                        if error_if_not_added:
                            xploder_out.append((xploder_file, appliesto_regex, "ErrorIfPartNotAdded", error_if_not_added, "", "", ""))
                    elif len(matches) == 1:
                        code_rule, full_description, regex, qty, adicional = matches[0]
                        xploder_out.append((xploder_file, appliesto_regex, code_rule, full_description, regex, qty, adicional))
                    else:
                        if error_if_more_than_one:
                            xploder_out.append((xploder_file, appliesto_regex, "ErrorIfMoreThanOnePartAdded", error_if_more_than_one, "", "", ""))
                        else:
                            for code_rule, full_description, regex, qty, adicional in matches:
                                xploder_out.append((xploder_file, appliesto_regex, code_rule, full_description, regex, qty, adicional))
                    inside_rule = False
                    continue

                if not inside_rule:
                    continue

                if line.startswith("AppliesTo"):
                    if line.startswith("AppliesTo"):
                        parts = re.split(r'\s+', line, maxsplit=1)
                        if len(parts) > 1:
                            appliesto_regex = parts[1].split()[0] 
                        else:
                            appliesto_regex = None

                elif re.match(r"^RegularExpression\w*", line):
                    parts = re.split(r'\s+', line)
                    if len(parts) >= 4:
                        regex = parts[1]
                        code_rule = parts[2]
                        qty = parts[3]
                        descriptions = parts[4:]

                        full_description = "; ".join(
                            f"{label}: {desc}" for label, desc in zip(text1_labels, descriptions)
                        ) if text1_labels and len(descriptions) >= len(text1_labels) else " ".join(descriptions)

                        adicional = ""
                        if len(descriptions) > len(text1_labels):
                            extra = descriptions[len(text1_labels):]
                            filtered_extra =[e for e in extra if e and e not in full_description]
                            if filtered_extra:
                                adicional = " ".join(filtered_extra)


                        if re.search(regex, pn_entry):
                            if full_description.strip() == adicional.strip():
                                adicional = ""
                            matches.append((code_rule, full_description, regex, qty, adicional))


                elif line.startswith("ErrorIfPartNotAdded"):
                    parts = re.split(r'\s+', line, maxsplit=2)
                    if len(parts) >= 3:
                        error_if_not_added = parts[2]

                elif line.startswith("ErrorIfMoreThanOnePartAdded"):
                    parts = re.split(r'\s+', line, maxsplit=2)
                    if len(parts) >= 3:
                        error_if_more_than_one = parts[2]

        return xploder_out

    def run_process():
        cancel_event.clear()
        exp_button.config(state=tk.DISABLED)
        stop_button.config(state=tk.NORMAL)
        entryxploder.config(state=tk.DISABLED)
        progress.grid()
        progress["value"] = 0

        if not xploder_folder:
            messagebox.showwarning(
                "Missing Folder",
                "⚠️ Please select a folder containing .rule files before running the test."
            )
            folder_label.config(text="Please select a folder!")
            exp_button.config(state=tk.NORMAL)
            stop_button.config(state=tk.DISABLED)
            entryxploder.config(state=tk.NORMAL)
            progress.grid_remove()
            return


        pn_entries = [pn.strip() for pn in entryxploder.get("1.0", tk.END).splitlines() if pn.strip()]
        if not pn_entries:
            messagebox.showwarning("Warning", "Please enter at least one part number.")
            exp_button.config(state=tk.NORMAL)
            stop_button.config(state=tk.DISABLED)
            entryxploder.config(state=tk.NORMAL)
            progress.grid_remove()
            return

        status_bar.config(text="Running...")

        xploder_results = []
        progress["maximum"] = len(pn_entries)

        for i, pn_entry in enumerate(pn_entries):
            if cancel_event.is_set():
                break

            results = process_folder(pn_entry, xploder_folder)
            for res in results:
                if len(res) == 7:
                    xploder_file, applies_to, code_ref, description, regex_match, qty, adicional = res
                    xploder_results.append([
                        pn_entry,
                        xploder_file,
                        applies_to,
                        regex_match,
                        code_ref,
                        qty,
                        description,
                        adicional
                    ])

            progress["value"] = i + 1
            xploder_win.update_idletasks()

        if cancel_event.is_set():
            status_bar.config(text="Process was cancelled.")
        elif xploder_results:
            try:
                df = pd.DataFrame(xploder_results, columns=[
                    "Part Number",
                    "File .rule",
                    "AppliesTo",
                    "RegularExpression",
                    "39MX",
                    "Qty",
                    "Description",
                    "Aditional"
                ])
                if df["Aditional"].str.strip().replace("", pd.NA).dropna().empty:
                    df = df.drop(columns=["Aditional"])

                output_path = os.path.join(os.path.dirname(__file__), "Results_xploder.xlsx")
                df.to_excel(output_path, index=False)
                status_bar.config(text=f"📁 Results saved to: {output_path}")

                try:
                    if platform.system() == "Windows":
                        os.startfile(output_path)
                    elif platform.system() == "Darwin":
                        subprocess.call(["open", output_path])
                    else:
                        subprocess.call(["xdg-open", output_path])
                except Exception as e:
                    status_bar.config(text=f"Error opening file: {e}")

            except Exception as e:
                status_bar.config(text=f" Error saving Excel file: {e}")
        else:
            status_bar.config(text=" No results found.")

        exp_button.config(state=tk.NORMAL)
        stop_button.config(state=tk.DISABLED)
        entryxploder.config(state=tk.NORMAL)
        progress.grid_remove()

    def stop_process():
        cancel_event.set()
        status_bar.config(text="Process was cancelled.")
        exp_button.config(state=tk.NORMAL)
        stop_button.config(state=tk.DISABLED)
        entryxploder.config(state=tk.NORMAL)
        progress["value"] = 0
        progress.grid_remove()

    def back_root():
        xploder_win.destroy()
        root.deiconify()

    def open_feedback_form(event=None):
        webbrowser.open_new_tab("https://forms.office.com/r/hRNvBVSwnm")

    topbar_xploder = ttk.Frame(xploder_win)
    topbar_xploder.grid(row=0, column=0, columnspan=2, sticky="ew", padx=10, pady=(10, 0))
    topbar_xploder.columnconfigure(0, weight=1)
    topbar_xploder.columnconfigure(1, weight=1)
    topbar_xploder.columnconfigure(2, weight=1)

    back_button = ttk.Button(topbar_xploder, text="🔙 Back", command=back_root)
    back_button.grid(row=0, column=0, sticky="w")

    header_query = ttk.Label(topbar_xploder, text="XPLODER RULES TEST", font=("Segoe UI", 16, "bold"))
    header_query.grid(row=0, column=1, sticky="n", pady=(0, 5))

    feedback_link = tk.Label(topbar_xploder, text="⚠️ Report/Feedback", cursor="hand2", font=("Segoe UI", 9, "underline"))
    feedback_link.grid(row=0, column=2, sticky="e")
    feedback_link.bind("<Button-1>", open_feedback_form)

    select_button = ttk.Button(xploder_win, text="Select Folder", width=15, command=select_xploderfolder)
    select_button.grid(row=1, column=0, sticky="w", padx=10)

    folder_label = ttk.Label(xploder_win, text="Please select a folder with .rule", foreground="gray")
    folder_label.grid(row=1, column=1, sticky="w", padx=10)

    rule_label = ttk.Label(xploder_win, text="Enter your part numbers (one per line):")
    rule_label.grid(row=2, column=0, sticky="sw", padx=10, pady=(0, 5))

    button_frame = ttk.Frame(xploder_win)
    button_frame.grid(row=2, column=1, sticky="e", pady=(0, 5), padx=(0, 10))

    button_width = 12

    exp_button = ttk.Button(button_frame, text="Run Test", width=button_width, command=lambda: threading.Thread(target=run_process, daemon=True).start())
    exp_button.pack(side="left")

    stop_button = ttk.Button(button_frame, text="Stop", width=button_width, command=stop_process, state=tk.DISABLED)
    stop_button.pack(side="left", padx=(5, 0))


    entryxploder = tk.Text(xploder_win, font=("Courier", 11), wrap="none")
    entryxploder.grid(row=3, column=0, columnspan=2, sticky="nsew", padx=10, pady=5)

    progress = ttk.Progressbar(xploder_win, orient="horizontal", length=300, mode="determinate")
    progress.grid(row=4, column=0, columnspan=2, pady=10)
    progress.grid_remove()

    status_bar = ttk.Label(xploder_win, text="Ready", relief="sunken", anchor="w")
    status_bar.grid(row=5, column=0, columnspan=2, sticky="ew")

    xploder_win.rowconfigure(3, weight=1)
    xploder_win.columnconfigure(1, weight=1)

    def exit_app():
        root.destroy()

    xploder_win.protocol("WM_DELETE_WINDOW", exit_app)



#main tkt
root = tk.Tk()
root.iconbitmap(icon_path)
root.title("AHUQ MTH")
root.geometry("850x600")
root.configure(bg="#f4f7fa")

container = tk.Frame(root, bg="#f4f7fa")
container.pack(expand=True)

try:
    path_logo = resource_path_logo("Carrier_logo.png")
    image = Image.open(path_logo)
    image = image.resize((300, 120), Image.LANCZOS)
    photo = ImageTk.PhotoImage(image)
    label_img = tk.Label(container, image=photo, bg="#f4f7fa")
    label_img.image = photo
    label_img.pack(pady=(30, 10))
except:
    pass

header_ahuq = tk.Label(container, text="Welcome to AHUQ",
                       font=("Segoe UI", 26, "bold"),
                       fg="#2c3e50",
                       bg="#f4f7fa")
header_ahuq.pack(pady=(10, 5))

sub_ahuq = tk.Label(container, text="What would you like to do today?",
                    font=("Segoe UI", 14),
                    fg="#7f8c8d",
                    bg="#f4f7fa")
sub_ahuq.pack(pady=(0, 30))

button_frame = tk.Frame(container, bg="#f4f7fa")
button_frame.pack(fill="x", padx=40)
button_frame.grid_columnconfigure(0, weight=1, uniform="a")
button_frame.grid_columnconfigure(1, weight=1, uniform="a")

button_style = {
    "font": ("Segoe UI", 12, "bold"),
    "bg": "#152c73",
    "fg": "white",
    "activebackground": "#44548c",
    "activeforeground": "white",
    "relief": "flat",
    "bd": 0,
    "padx": 25,
    "pady": 12,
    "cursor": "hand2"
}

open_query_button = tk.Button(button_frame, text="XML Query", command=query_window, **button_style)
open_query_button.grid(row=0, column=0, padx=15, sticky="ew")

open_xploder_button = tk.Button(button_frame, text="xPloder Rule Test", command=xploder_window, **button_style)
open_xploder_button.grid(row=0, column=1, padx=15, sticky="ew")

tk.Label(container, bg="#f4f7fa").pack(pady=40)


root.mainloop()

#ALONSO TOVAR
#LUIS SANCHEZ
#pyinstaller --onefile --noconsole --icon=AHUQ-icon.ico --add-data "AHUQ-icon.ico;." --add-data "Carrier_logo.PNG;." AHUQ_Beta0.1.py