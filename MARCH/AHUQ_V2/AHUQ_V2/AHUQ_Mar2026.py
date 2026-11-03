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
import pyperclip
from concurrent.futures import ThreadPoolExecutor, as_completed
import math
from collections import Counter
from typing import Any, Iterable, Tuple
import os
import ezdxf
from ezdxf import recover
import matplotlib.pyplot as plt
from matplotlib.patches import Arc, Circle
import math
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg


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

    progress = ttk.Progressbar(query_win, orient="horizontal", length=600, mode="determinate")
    progress.grid(row=1, column=0, columnspan=2, pady=10, padx=10, sticky="ew")
    progress.grid_remove()

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

    feature_frame = ttk.Frame(input_frame)
    feature_frame.grid(row=2, column=0, sticky="w", padx=5, pady=(0, 5))
    ttk.Label(feature_frame, text="Penetration feature:").pack(side="left")
    penetration_feature = tk.StringVar()
    feature_entry = ttk.Entry(feature_frame, textvariable=penetration_feature, width=30)
    feature_entry.pack(side="left", padx=(5, 0))
    feature_frame.grid_remove() 

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

    actions = ["LocationID", "Qty", "Points", "Description", "Icons", "Penetrations"]
    selected_action = tk.StringVar()
    dropdown = ttk.Combobox(frame, textvariable=selected_action, values=actions, state="readonly", width=30)
    dropdown.set("Select an action")
    dropdown.grid(row=1, column=0, padx=5, pady=5)

    def hide_icons(event=None):
        action = selected_action.get()
        if action == "Icons":
            input_frame.grid_remove()
            feature_frame.grid_remove()
        elif action == "Penetrations":
            input_frame.grid()
            feature_frame.grid()
        else:
            input_frame.grid()
            feature_frame.grid_remove()
    dropdown.bind("<<ComboboxSelected>>", hide_icons)
       
    processing_animation_running = False
    animation_index = 0

    def execute_query():
        nonlocal should_stop, processing_animation_running
        should_stop = False

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

                    elif not should_stop and selected_action.get() == "Penetrations":

                        regex_input = regexes
                        feature_filter = penetration_feature.get().strip()

                        for item in root_xml.findall('.//manufacturedItem'):
                            if should_stop:
                                return local_results

                            part_node = item.find('partNumber')
                            if part_node is None or not part_node.text:
                                continue

                            part_number = part_node.text.strip()

                            if regex_input:
                                if not any(r.search(part_number) for r in regex_input):
                                    continue

                            for penetration in item.findall('.//penetration'):
                                feature = penetration.attrib.get('feature', '')

                                if feature_filter and feature_filter not in feature:
                                    continue

                                xl = penetration.attrib.get('xl', '')
                                yl = penetration.attrib.get('yl', '')
                                zl = penetration.attrib.get('zl', '')
                                xu = penetration.attrib.get('xu', '')
                                yu = penetration.attrib.get('yu', '')
                                zu = penetration.attrib.get('zu', '')

                                local_results.append(
                                    f"{os.path.basename(xml_file)}\t{part_number}\t{feature}"
                                    f"\txl={xl}, yl={yl}, zl={zl}, xu={xu}, yu={yu}, zu={zu}"
                                )


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
            result_text.config(state="normal")
            result_text.delete(1.0, tk.END)
            result_text.insert(tk.END, "\n".join(results))
            result_text.config(state="disabled")


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
    last_search_term = ""
    search_matches = []
    current_match_index = -1
    search_var = tk.StringVar()
    search_entry = ttk.Entry(search_frame, textvariable=search_var, width=40)
    search_entry.grid(row=0, column=1, pady=5, sticky="w")

    def highlight_search():
        nonlocal search_matches, current_match_index

        result_text.tag_remove('highlight', '1.0', tk.END)
        result_text.tag_remove('current_match', '1.0', tk.END)

        term = search_var.get()
        search_matches = []
        current_match_index = -1

        if not term:
            return

        idx = '1.0'
        while True:
            idx = result_text.search(term, idx, nocase=1, stopindex=tk.END)
            if not idx:
                break
            lastidx = f"{idx}+{len(term)}c"
            search_matches.append((idx, lastidx))
            result_text.tag_add('highlight', idx, lastidx)
            idx = lastidx

        result_text.tag_config('highlight', background='yellow', foreground='black')

        if search_matches:
            current_match_index = 0
            go_to_match()

    
    def go_to_match():
        nonlocal current_match_index

        result_text.tag_remove('current_match', '1.0', tk.END)

        start, end = search_matches[current_match_index]
        result_text.tag_add('current_match', start, end)
        result_text.see(start)

        result_text.tag_config(
            'current_match',
            background='orange',
            foreground='black'
        )


    def on_search_key(event):
        nonlocal current_match_index

        if not search_matches:
            return "break"

        if event.state & 0x0001:  # Shift
            current_match_index = (current_match_index - 1) % len(search_matches)
        else:
            current_match_index = (current_match_index + 1) % len(search_matches)

        go_to_match()
        return "break"

    search_entry.bind("<Return>", on_search_key)

    ttk.Button(search_frame, text="Search", command=highlight_search, style="Small.TButton").grid(row=0, column=2, padx=5)
    ttk.Button(search_frame, text="Clear Results", command=lambda: (result_text.config(state="normal"), result_text.delete(1.0, tk.END), result_text.config(state="disabled"), status_query.config(text="Ready", foreground="black")), style="Small.TButton").grid(row=0, column=3, padx=5)


    result_label = ttk.Label(query_win, text="Results:")
    result_label.grid(row=5, column=0, columnspan=2, sticky="w", padx=10, pady=(10, 0))

    result_frame = ttk.Frame(query_win)
    result_frame.grid(row=6, column=0, columnspan=2, padx=10, pady=(0, 10), sticky="nsew")
    query_win.rowconfigure(6, weight=1)
    result_text = tk.Text(result_frame, height=20, width=120, font=("Courier", 10), wrap="none", state="disabled")
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

    
    def paste_from_clipboard():
        try:
            text = pyperclip.paste()
            if text:
                entryxploder.delete("1.0", tk.END)
                entryxploder.insert(tk.END, text)
                num_rows = len([line for line in text.splitlines() if line.strip()])
                status_bar.config(text=f"Pasted {num_rows} rows from clipboard.")
            else:
                status_bar.config(text="Clipboard is empty.")
        except Exception as e:
            status_bar.config(text=f"Error pasting: {e}")


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

    folder_frame = ttk.Frame(xploder_win)
    folder_frame.grid(row=1, column=0, columnspan=2, sticky="ew", padx=10, pady=(0,5))
    folder_frame.columnconfigure(0, weight=0)
    folder_frame.columnconfigure(1, weight=1)
    folder_frame.columnconfigure(2, weight=0)

    select_button = ttk.Button(folder_frame, text="Select Folder", width=15, command=select_xploderfolder)
    select_button.grid(row=0, column=0, sticky="w", padx=(5,0))

    folder_label = ttk.Label(folder_frame, text="Please select a folder with .rule", foreground="gray")
    folder_label.grid(row=0, column=1, sticky="w", padx=5)

    paste_button = ttk.Button(folder_frame, text="📋 Paste", width=12, command=paste_from_clipboard)
    paste_button.grid(row=0, column=2, sticky="e")

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

DEFAULT_PRECISION = 6
DEFAULT_COMPARE_TYPES = {
        "LINE",
        "CIRCLE",
        "ARC",
        "LWPOLYLINE",
        "POLYLINE",
        "POINT",
        "ELLIPSE",
        "SPLINE",
        "TEXT",
        "MTEXT",
        "INSERT",
    }


def _r(value, precision=DEFAULT_PRECISION):
    if value is None:
        return None
    if isinstance(value, (int, float)):
        if math.isfinite(float(value)):
            return round(float(value), precision)
        return value
    return value


def _pt(point, precision=DEFAULT_PRECISION):
    if point is None:
        return (None, None, None)
    return (
        _r(point[0], precision),
        _r(point[1], precision),
        _r(point[2], precision),
    )


def _normalize_text(text):
    if text is None:
        return ""
    return " ".join(str(text).split()).strip()


def _safe_layer(entity):
    try:
        return entity.dxf.layer
    except:
        return ""


def _safe_color(entity):
    try:
        return entity.dxf.color
    except:
        return None


def _safe_linetype(entity):
    try:
        return entity.dxf.linetype
    except:
        return ""


def _base_signature(entity):
    return (
        entity.dxftype(),
        _safe_layer(entity),
        _safe_color(entity),
        _safe_linetype(entity),
    )


def _normalize_line(entity, precision):
    start = _pt(entity.dxf.start, precision)
    end = _pt(entity.dxf.end, precision)

    if start <= end:
        p1, p2 = start, end
    else:
        p1, p2 = end, start

    return _base_signature(entity) + (p1, p2)


def _normalize_circle(entity, precision):
    return _base_signature(entity) + (
        _pt(entity.dxf.center, precision),
        _r(entity.dxf.radius, precision),
    )


def _normalize_arc(entity, precision):
    return _base_signature(entity) + (
        _pt(entity.dxf.center, precision),
        _r(entity.dxf.radius, precision),
        _r(entity.dxf.start_angle % 360.0, precision),
        _r(entity.dxf.end_angle % 360.0, precision),
    )


def _normalize_lwpolyline(entity, precision):
    points = []
    for v in entity.get_points("xyb"):
        x, y, bulge = v
        points.append((_r(x, precision), _r(y, precision), _r(bulge, precision)))

    return _base_signature(entity) + (
        int(entity.closed),
        tuple(points),
    )


def _normalize_polyline(entity, precision):
    points = []
    try:
        for v in entity.vertices:
            points.append(_pt(v.dxf.location, precision))
    except:
        try:
            for v in entity.points():
                points.append(_pt(v, precision))
        except:
            pass

    closed = 0
    try:
        closed = int(entity.is_closed)
    except:
        pass

    return _base_signature(entity) + (
        closed,
        tuple(points),
    )


def _normalize_point(entity, precision):
    return _base_signature(entity) + (
        _pt(entity.dxf.location, precision),
    )


def _normalize_ellipse(entity, precision):
    return _base_signature(entity) + (
        _pt(entity.dxf.center, precision),
        _pt(entity.dxf.major_axis, precision),
        _r(entity.dxf.ratio, precision),
        _r(entity.dxf.start_param, precision),
        _r(entity.dxf.end_param, precision),
    )


def _normalize_spline(entity, precision):
    control_points = []
    fit_points = []

    try:
        for p in entity.control_points:
            control_points.append(_pt(p, precision))
    except:
        pass

    try:
        for p in entity.fit_points:
            fit_points.append(_pt(p, precision))
    except:
        pass

    degree = None
    try:
        degree = entity.dxf.degree
    except:
        pass

    closed = 0
    try:
        closed = int(entity.closed)
    except:
        pass

    return _base_signature(entity) + (
        _r(degree, precision),
        closed,
        tuple(control_points),
        tuple(fit_points),
    )


def _normalize_text_entity(entity, precision):
    insert = None
    rotation = None
    height = None
    text = ""

    try:
        insert = _pt(entity.dxf.insert, precision)
    except:
        pass

    try:
        rotation = _r(entity.dxf.rotation, precision)
    except:
        pass

    try:
        height = _r(entity.dxf.height, precision)
    except:
        pass

    try:
        text = _normalize_text(entity.dxf.text)
    except:
        try:
            text = _normalize_text(entity.text)
        except:
            pass

    return _base_signature(entity) + (
        text,
        insert,
        rotation,
        height,
    )


def _normalize_mtext(entity, precision):
    insert = None
    char_height = None
    rotation = None
    text = ""

    try:
        insert = _pt(entity.dxf.insert, precision)
    except:
        pass

    try:
        char_height = _r(entity.dxf.char_height, precision)
    except:
        pass

    try:
        rotation = _r(entity.get_rotation(), precision)
    except:
        try:
            rotation = _r(entity.dxf.rotation, precision)
        except:
            pass

    try:
        text = _normalize_text(entity.text)
    except:
        pass

    return _base_signature(entity) + (
        text,
        insert,
        rotation,
        char_height,
    )


def _normalize_insert(entity, precision):
    name = ""
    insert = None
    rotation = None
    xscale = 1.0
    yscale = 1.0
    zscale = 1.0

    try:
        name = entity.dxf.name
    except:
        pass

    try:
        insert = _pt(entity.dxf.insert, precision)
    except:
        pass

    try:
        rotation = _r(entity.dxf.rotation, precision)
    except:
        pass

    try:
        xscale = _r(entity.dxf.xscale, precision)
    except:
        pass

    try:
        yscale = _r(entity.dxf.yscale, precision)
    except:
        pass

    try:
        zscale = _r(entity.dxf.zscale, precision)
    except:
        pass

    attribs = []
    try:
        for a in entity.attribs:
            attribs.append(
                (
                    getattr(a.dxf, "tag", ""),
                    _normalize_text(getattr(a.dxf, "text", "")),
                    _pt(getattr(a.dxf, "insert", None), precision),
                )
            )
    except:
        pass

    attribs.sort()

    return _base_signature(entity) + (
        name,
        insert,
        rotation,
        xscale,
        yscale,
        zscale,
        tuple(attribs),
    )


def _normalize_entity(entity, precision=DEFAULT_PRECISION):
    entity_type = entity.dxftype()

    if entity_type == "LINE":
        return _normalize_line(entity, precision)
    if entity_type == "CIRCLE":
        return _normalize_circle(entity, precision)
    if entity_type == "ARC":
        return _normalize_arc(entity, precision)
    if entity_type == "LWPOLYLINE":
        return _normalize_lwpolyline(entity, precision)
    if entity_type == "POLYLINE":
        return _normalize_polyline(entity, precision)
    if entity_type == "POINT":
        return _normalize_point(entity, precision)
    if entity_type == "ELLIPSE":
        return _normalize_ellipse(entity, precision)
    if entity_type == "SPLINE":
        return _normalize_spline(entity, precision)
    if entity_type == "TEXT":
        return _normalize_text_entity(entity, precision)
    if entity_type == "MTEXT":
        return _normalize_mtext(entity, precision)
    if entity_type == "INSERT":
        return _normalize_insert(entity, precision)

    return None


def _read_dxf_safely(dxf_path):
    try:
        return ezdxf.readfile(dxf_path)
    except:
        doc, auditor = recover.readfile(dxf_path)
        return doc


def extract_normalized_entities(dxf_path, precision=DEFAULT_PRECISION, include_types=None):
    if include_types is None:
        include_types = DEFAULT_COMPARE_TYPES

    include_types = set(include_types)

    if os.path.isdir(dxf_path):
        raise ValueError("Expected DXF file path, got folder: " + dxf_path)

    if not os.path.isfile(dxf_path):
        raise FileNotFoundError("DXF file not found: " + dxf_path)

    doc = _read_dxf_safely(dxf_path)
    msp = doc.modelspace()
    normalized = []

    for entity in msp:
        try:
            if entity.dxftype() not in include_types:
                continue

            item = _normalize_entity(entity, precision)
            if item is not None:
                normalized.append(item)
        except:
            pass

    normalized.sort()
    return normalized


def compare_dxf_geometry(file_a, file_b, precision=DEFAULT_PRECISION, include_types=None):
    entities_a = extract_normalized_entities(file_a, precision, include_types)
    entities_b = extract_normalized_entities(file_b, precision, include_types)

    counter_a = Counter(entities_a)
    counter_b = Counter(entities_b)

    only_in_a = list((counter_a - counter_b).elements())
    only_in_b = list((counter_b - counter_a).elements())

    return {
        "match": len(only_in_a) == 0 and len(only_in_b) == 0,
        "count_a": len(entities_a),
        "count_b": len(entities_b),
        "only_in_a": only_in_a,
        "only_in_b": only_in_b,
    }


def get_dxf_files(folder):
    return {
        f.lower(): os.path.join(folder, f)
        for f in os.listdir(folder)
        if f.lower().endswith(".dxf")
    }

def compare_dxf_folders(folder_a, folder_b, precision=DEFAULT_PRECISION):
    files_a = get_dxf_files(folder_a)
    files_b = get_dxf_files(folder_b)

    all_names = sorted(set(files_a.keys()) | set(files_b.keys()))
    results = []

    for name in all_names:
        path_a = files_a.get(name)
        path_b = files_b.get(name)

        if path_a and path_b:
            try:
                result = compare_dxf_geometry(path_a, path_b, precision=precision)

                results.append({
                    "file": name,
                    "status": "MATCH" if result["match"] else "DIFFERENT",
                    "count_a": result["count_a"],
                    "count_b": result["count_b"],
                    "diff_a": len(result["only_in_a"]),
                    "diff_b": len(result["only_in_b"]),
                    "only_in_a": result["only_in_a"],
                    "only_in_b": result["only_in_b"],
                })
            except Exception as e:
                results.append({
                    "file": name,
                    "status": "ERROR",
                    "error": str(e),
                })
        elif path_a:
            results.append({
                "file": name,
                "status": "ONLY_IN_A",
            })
        else:
            results.append({
                "file": name,
                "status": "ONLY_IN_B",
            })

    return results


def _draw_doc(ax, dxf_path, color, alpha):
    try:
        doc = _read_dxf_safely(dxf_path)
        msp = doc.modelspace()
    except Exception as e:
        print("Could not load for overlay:", dxf_path, e)
        return

    for entity in msp:
        try:
            dxftype = entity.dxftype()

            if dxftype == "LINE":
                x1, y1, _ = entity.dxf.start
                x2, y2, _ = entity.dxf.end
                ax.plot([x1, x2], [y1, y2], color=color, alpha=alpha)

            elif dxftype == "CIRCLE":
                center = entity.dxf.center
                radius = entity.dxf.radius
                patch = Circle((center[0], center[1]), radius, fill=False, color=color, alpha=alpha)
                ax.add_patch(patch)

            elif dxftype == "ARC":
                center = entity.dxf.center
                radius = entity.dxf.radius
                start_angle = entity.dxf.start_angle
                end_angle = entity.dxf.end_angle
                patch = Arc(
                    (center[0], center[1]),
                    width=2 * radius,
                    height=2 * radius,
                    angle=0,
                    theta1=start_angle,
                    theta2=end_angle,
                    color=color,
                    alpha=alpha
                )
                ax.add_patch(patch)

            elif dxftype == "LWPOLYLINE":
                pts = []
                for p in entity.get_points("xy"):
                    pts.append((p[0], p[1]))
                if pts:
                    xs = [p[0] for p in pts]
                    ys = [p[1] for p in pts]
                    if entity.closed and len(pts) > 1:
                        xs.append(pts[0][0])
                        ys.append(pts[0][1])
                    ax.plot(xs, ys, color=color, alpha=alpha)

            elif dxftype == "POLYLINE":
                pts = []
                try:
                    for v in entity.vertices:
                        pts.append((v.dxf.location[0], v.dxf.location[1]))
                except:
                    pass

                if pts:
                    xs = [p[0] for p in pts]
                    ys = [p[1] for p in pts]
                    try:
                        if entity.is_closed and len(pts) > 1:
                            xs.append(pts[0][0])
                            ys.append(pts[0][1])
                    except:
                        pass
                    ax.plot(xs, ys, color=color, alpha=alpha)

            elif dxftype == "POINT":
                x, y, _ = entity.dxf.location
                ax.plot(x, y, marker="o", color=color, alpha=alpha, markersize=2)

        except:
            pass



def plot_dxf_differences_grid(results, folder_a, folder_b):
    diff_items = [r for r in results if r.get("status") == "DIFFERENT"]

    if not diff_items:
        messagebox.showinfo("No differences", "There are no different DXF files to plot.")
        return

    plot_win = tk.Toplevel(root)
    plot_win.title("DXF Differences Grid")
    plot_win.state("zoomed")
    plot_win.configure(bg="#f4f7fa")

    def close_window():
        plot_win.destroy()

    topbar = ttk.Frame(plot_win)
    topbar.pack(fill="x", padx=10, pady=10)

    ttk.Button(topbar, text="Close", command=close_window).pack(side="left")
    ttk.Label(topbar, text="DXF DIFFERENCES GRID", font=("Segoe UI", 16, "bold")).pack(side="left", padx=15)

    main_frame = ttk.Frame(plot_win)
    main_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))

    canvas = tk.Canvas(main_frame, bg="#f4f7fa", highlightthickness=0)
    v_scroll = ttk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
    h_scroll = ttk.Scrollbar(main_frame, orient="horizontal", command=canvas.xview)

    canvas.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)

    canvas.grid(row=0, column=0, sticky="nsew")
    v_scroll.grid(row=0, column=1, sticky="ns")
    h_scroll.grid(row=1, column=0, sticky="ew")

    main_frame.rowconfigure(0, weight=1)
    main_frame.columnconfigure(0, weight=1)

    scrollable_frame = ttk.Frame(canvas)
    canvas_window = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")

    def update_scroll_region(event=None):
        canvas.configure(scrollregion=canvas.bbox("all"))

    def resize_inner_frame(event):
        canvas.itemconfig(canvas_window, width=event.width)

    scrollable_frame.bind("<Configure>", update_scroll_region)
    canvas.bind("<Configure>", resize_inner_frame)

    cards_per_row = 2
    chart_refs = []

    for i, item in enumerate(diff_items):
        row = i // cards_per_row
        col = i % cards_per_row

        file_name = item["file"]
        path_a = os.path.join(folder_a, file_name)
        path_b = os.path.join(folder_b, file_name)

        card = ttk.Frame(scrollable_frame, padding=10, relief="solid", borderwidth=1)
        card.grid(row=row, column=col, padx=10, pady=10, sticky="nsew")

        title_label = ttk.Label(card, text=file_name, font=("Segoe UI", 10, "bold"))
        title_label.pack(anchor="w", pady=(0, 4))

        info_label = ttk.Label(
            card,
            text=f"A:{item.get('count_a', 0)}   B:{item.get('count_b', 0)}   ΔA:{item.get('diff_a', 0)}   ΔB:{item.get('diff_b', 0)}"
        )
        info_label.pack(anchor="w", pady=(0, 6))

        fig = plt.Figure(figsize=(6.2, 4.6), dpi=100)
        ax = fig.add_subplot(111)
        ax.set_title(file_name, fontsize=9)
        ax.set_aspect("equal", adjustable="datalim")
        ax.grid(True)

        try:
            _draw_doc(ax, path_a, color="cyan", alpha=0.9)
            _draw_doc(ax, path_b, color="magenta", alpha=0.9)
        except Exception as e:
            ax.clear()
            ax.text(0.5, 0.5, str(e), ha="center", va="center", wrap=True)
            ax.set_axis_off()

        fig.tight_layout()

        chart = FigureCanvasTkAgg(fig, master=card)
        chart.draw()
        chart.get_tk_widget().pack(fill="both", expand=True)

        chart_refs.append(chart)

    for c in range(cards_per_row):
        scrollable_frame.columnconfigure(c, weight=1)

    def _on_mousewheel(event):
        canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    plot_win.bind_all("<MouseWheel>", _on_mousewheel)
    plot_win.focus_force()

def dxf_compare_window():
    root.withdraw()

    dxf_win = tk.Toplevel(root)
    dxf_win.iconbitmap(icon_path)
    dxf_win.title("AHUQ MTH - DXF Compare")
    dxf_win.geometry("1000x700")
    dxf_win.configure(bg="#f4f7fa")

    selected_folder_a = tk.StringVar()
    selected_folder_b = tk.StringVar()
    filter_var = tk.StringVar()

    latest_results = []
    latest_folder_a = ""
    latest_folder_b = ""

    def back_root():
        dxf_win.destroy()
        root.deiconify()

    def exit_app():
        root.destroy()

    def open_feedback_form(event=None):
        pass

    def select_folder_a():
        folder = filedialog.askdirectory(title="Select first DXF folder")
        if folder:
            selected_folder_a.set(folder)
            folder_a_label.config(text=folder, foreground="#2c3e50")

    def select_folder_b():
        folder = filedialog.askdirectory(title="Select second DXF folder")
        if folder:
            selected_folder_b.set(folder)
            folder_b_label.config(text=folder, foreground="#2c3e50")

    def write_output_line(text_line=""):
        output_text.insert(tk.END, text_line + "\n")
        output_text.see(tk.END)

    def clear_output():
        output_text.delete("1.0", tk.END)
        status_bar.config(text="Ready")

    def format_results_for_display(results, filter_text=""):
        output_text.delete("1.0", tk.END)

        filter_text = filter_text.strip().lower()
        shown = 0

        write_output_line("DXF folder comparison results:")
        write_output_line("")

        for r in results:
            file_name = r.get("file", "")

            if filter_text and filter_text not in file_name.lower():
                continue

            shown += 1

            if r["status"] == "MATCH":
                write_output_line(f"✅ {file_name}")
            elif r["status"] == "DIFFERENT":
                write_output_line(
                    f"❌ {file_name} | A:{r.get('count_a', 0)} B:{r.get('count_b', 0)} | ΔA:{r.get('diff_a', 0)} ΔB:{r.get('diff_b', 0)}"
                )
            elif r["status"] == "ERROR":
                write_output_line(f"⚠️ {file_name} | ERROR: {r.get('error', '')}")
            else:
                write_output_line(f"⚠️ {file_name} - {r['status']}")
            
        if shown == 0:
            write_output_line("No files matched the current filter.")

        diff_count = len([r for r in results if r.get("status") == "DIFFERENT"])
        shown_diff_count = len(
            [r for r in results if r.get("status") == "DIFFERENT" and (not filter_text or filter_text in r.get("file", "").lower())]
        )

        status_bar.config(
            text=f"Done | Total files: {len(results)} | Different: {diff_count} | Displayed: {shown} | Displayed diffs: {shown_diff_count}"
        )

    def apply_filter(*args):
        if latest_results:
            format_results_for_display(latest_results, filter_var.get())

    def run_dxf_compare():
        nonlocal latest_results, latest_folder_a, latest_folder_b

        folder_a = selected_folder_a.get().strip()
        folder_b = selected_folder_b.get().strip()

        if not folder_a or not folder_b:
            messagebox.showwarning("Missing folders", "Please select both DXF folders.")
            return

        if not os.path.isdir(folder_a):
            messagebox.showerror("Invalid folder", "Folder A is not valid.")
            return

        if not os.path.isdir(folder_b):
            messagebox.showerror("Invalid folder", "Folder B is not valid.")
            return

        run_button.config(state=tk.DISABLED)
        clear_button.config(state=tk.DISABLED)
        plot_button.config(state=tk.DISABLED)

        progress.grid()
        progress.start(10)
        status_bar.config(text="Running DXF compare...")
        output_text.delete("1.0", tk.END)

        try:
            results = compare_dxf_folders(folder_a, folder_b, precision=6)
            #print(results[0])
            latest_results = results
            latest_folder_a = folder_a
            latest_folder_b = folder_b
            #print(latest_results[0])
            format_results_for_display(latest_results, "")

            if any(r.get("status") == "DIFFERENT" for r in latest_results):
                plot_button.config(state=tk.NORMAL)

        except Exception as e:
            output_text.delete("1.0", tk.END)
            write_output_line("⚠️ ERROR")
            write_output_line(str(e))
            status_bar.config(text="Comparison failed")

        finally:
            progress.stop()
            progress.grid_remove()
            run_button.config(state=tk.NORMAL)
            clear_button.config(state=tk.NORMAL)

    def open_plot_grid():
        if not latest_results:
            messagebox.showwarning("No results", "Run the DXF comparison first.")
            return

        filtered_results = []
        filter_text = filter_var.get().strip().lower()

        for r in latest_results:
            if r.get("status") != "DIFFERENT":
                continue
            if filter_text and filter_text not in r.get("file", "").lower():
                continue
            filtered_results.append(r)

        if not filtered_results:
            messagebox.showinfo("No plotted differences", "There are no different files matching the current filter.")
            return

        plot_dxf_differences_grid(filtered_results, latest_folder_a, latest_folder_b)

    topbar_dxf = ttk.Frame(dxf_win)
    topbar_dxf.grid(row=0, column=0, columnspan=2, sticky="ew", padx=10, pady=(10, 0))
    topbar_dxf.columnconfigure(0, weight=1)
    topbar_dxf.columnconfigure(1, weight=1)
    topbar_dxf.columnconfigure(2, weight=1)

    back_button = ttk.Button(topbar_dxf, text="🔙 Back", command=back_root)
    back_button.grid(row=0, column=0, sticky="w")

    header_dxf = ttk.Label(topbar_dxf, text="DXF COMPARE", font=("Segoe UI", 16, "bold"))
    header_dxf.grid(row=0, column=1, sticky="n", pady=(0, 5))

    feedback_link = tk.Label(
        topbar_dxf,
        text="⚠️ Report/Feedback",
        cursor="hand2",
        font=("Segoe UI", 9, "underline"),
        fg="#2c3e50",
        bg="#f4f7fa"
    )
    feedback_link.grid(row=0, column=2, sticky="e")
    feedback_link.bind("<Button-1>", open_feedback_form)

    folder_frame_a = ttk.Frame(dxf_win)
    folder_frame_a.grid(row=1, column=0, columnspan=2, sticky="ew", padx=10, pady=(5, 5))
    folder_frame_a.columnconfigure(0, weight=0)
    folder_frame_a.columnconfigure(1, weight=1)

    select_button_a = ttk.Button(folder_frame_a, text="Pick PRD Folder", width=15, command=select_folder_a)
    select_button_a.grid(row=0, column=0, sticky="w", padx=(5, 0))

    folder_a_label = ttk.Label(folder_frame_a, text="Please select the first folder with .dxf files", foreground="gray")
    folder_a_label.grid(row=0, column=1, sticky="w", padx=5)

    folder_frame_b = ttk.Frame(dxf_win)
    folder_frame_b.grid(row=2, column=0, columnspan=2, sticky="ew", padx=10, pady=(0, 5))
    folder_frame_b.columnconfigure(0, weight=0)
    folder_frame_b.columnconfigure(1, weight=1)

    select_button_b = ttk.Button(folder_frame_b, text="Pick QA Folder ", width=15, command=select_folder_b)
    select_button_b.grid(row=0, column=0, sticky="w", padx=(5, 0))

    folder_b_label = ttk.Label(folder_frame_b, text="Please select the second folder with .dxf files", foreground="gray")
    folder_b_label.grid(row=0, column=1, sticky="w", padx=5)

    filter_frame = ttk.Frame(dxf_win)
    filter_frame.grid(row=3, column=0, columnspan=2, sticky="ew", padx=10, pady=(5, 5))
    filter_frame.columnconfigure(1, weight=1)

    ttk.Label(filter_frame, text="Filter by filename:").grid(row=0, column=0, sticky="w", padx=(5, 5))
    filter_entry = ttk.Entry(filter_frame, textvariable=filter_var)
    filter_entry.grid(row=0, column=1, sticky="ew", padx=(0, 5))

    button_frame_dxf = ttk.Frame(dxf_win)
    button_frame_dxf.grid(row=4, column=0, columnspan=2, sticky="e", pady=(0, 5), padx=(0, 10))

    button_width = 14

    run_button = ttk.Button(
        button_frame_dxf,
        text="Run Compare",
        width=button_width,
        command=lambda: threading.Thread(target=run_dxf_compare, daemon=True).start()
    )
    run_button.pack(side="left")

    plot_button = ttk.Button(
        button_frame_dxf,
        text="Plot Differences",
        width=button_width,
        command=open_plot_grid,
        state=tk.DISABLED
    )
    plot_button.pack(side="left", padx=(5, 0))

    clear_button = ttk.Button(
        button_frame_dxf,
        text="Clear",
        width=button_width,
        command=clear_output
    )
    clear_button.pack(side="left", padx=(5, 0))

    results_label = ttk.Label(dxf_win, text="Comparison Results:")
    results_label.grid(row=5, column=0, sticky="sw", padx=10, pady=(0, 5))

    output_frame = ttk.Frame(dxf_win)
    output_frame.grid(row=6, column=0, columnspan=2, sticky="nsew", padx=10, pady=5)

    output_scroll_y = ttk.Scrollbar(output_frame, orient="vertical")
    output_scroll_x = ttk.Scrollbar(output_frame, orient="horizontal")

    output_text = tk.Text(
        output_frame,
        font=("Courier", 11),
        wrap="none",
        yscrollcommand=output_scroll_y.set,
        xscrollcommand=output_scroll_x.set
    )
    output_text.grid(row=0, column=0, sticky="nsew")

    output_scroll_y.config(command=output_text.yview)
    output_scroll_y.grid(row=0, column=1, sticky="ns")

    output_scroll_x.config(command=output_text.xview)
    output_scroll_x.grid(row=1, column=0, sticky="ew")

    output_frame.rowconfigure(0, weight=1)
    output_frame.columnconfigure(0, weight=1)

    progress = ttk.Progressbar(dxf_win, orient="horizontal", length=300, mode="indeterminate")
    progress.grid(row=7, column=0, columnspan=2, pady=10)
    progress.grid_remove()

    status_bar = ttk.Label(dxf_win, text="Ready", relief="sunken", anchor="w")
    status_bar.grid(row=8, column=0, columnspan=2, sticky="ew")

    dxf_win.rowconfigure(6, weight=1)
    dxf_win.columnconfigure(0, weight=1)
    dxf_win.columnconfigure(1, weight=1)

    filter_var.trace_add("write", apply_filter)

    dxf_win.protocol("WM_DELETE_WINDOW", exit_app)

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

open_xploder_button = tk.Button(button_frame, text="xPloder Rule Test", command=dxf_compare_window, **button_style)
open_xploder_button.grid(row=0, column=1, padx=15, sticky="ew")

open_dxf_compare_button = tk.Button(button_frame, text="DXF Compare", command=dxf_compare_window, **button_style)
open_dxf_compare_button.grid(row=0, column=2, padx=15, sticky="ew")

tk.Label(container, bg="#f4f7fa").pack(pady=40)


root.mainloop()

#ALONSO TOVAR
#LUIS SANCHEZ
#pyinstaller --onefile --noconsole --icon=AHUQ-icon.ico --add-data "AHUQ-icon.ico;." --add-data "Carrier_logo.PNG;." AHUQ_Dec2025.py
