import secrets
from flask import Flask, render_template, request, session, jsonify
from estimator import DesignHourEstimatorData
from estimation_rules import (
    PRIMARY_L1_WEIGHT,
    SECONDARY_L1_WEIGHT,
    TERTIARY_L1_WEIGHT,
    weighted_hours,
)
import webbrowser
from threading import Timer 
import pandas as pd
import os
import sys
import shutil
import socket
import re

def is_port_available(port, host="127.0.0.1"):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return s.connect_ex((host, port)) 
    

def find_available_port(start_port=5000, host="127.0.0.1", max_tries=50):
    for port in range(start_port, start_port + max_tries):
        if is_port_available(port, host):
            return port
    raise RuntimeError("No available port found.")

def open_browser(port):   
    webbrowser.open_new(f"http://127.0.0.1:{port}/")

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY") or secrets.token_hex(32)

def app_base_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.abspath(".")

def bundled_resource_path(relative_path):
    base_path = getattr(sys, "_MEIPASS", os.path.abspath("."))
    return os.path.join(base_path, relative_path)

BASE_DIR = app_base_dir()



EXTERNAL_PRODUCT_DATA_DIR = os.path.join(BASE_DIR, "Product Data")
EXCEL_FILE = os.path.join(EXTERNAL_PRODUCT_DATA_DIR, "estimator_data_updated.xlsx")
SAVE_FOLDER = os.path.join(BASE_DIR, "Project Files", "Qboms")
SUMMARY_FOLDER = os.path.join(BASE_DIR, "Project Files", "Projects")

os.makedirs(EXTERNAL_PRODUCT_DATA_DIR, exist_ok=True)
os.makedirs(SAVE_FOLDER, exist_ok=True)
os.makedirs(SUMMARY_FOLDER, exist_ok=True)

def ensure_external_excel():
    bundled_excel = bundled_resource_path(os.path.join("Product Data", "estimator_data_updated.xlsx"))

    if not os.path.exists(EXCEL_FILE):
        if os.path.exists(bundled_excel):
            shutil.copyfile(bundled_excel, EXCEL_FILE)
            print("Copied Excel to external Product Data folder:", EXCEL_FILE)
        else:
            print("Bundled Excel not found:", bundled_excel)


ensure_external_excel()


def create_backup_if_exists(folder, filename):
    file_path = os.path.join(folder, filename) 

    if not os.path.exists(file_path):
        return

    backup_folder = os.path.join(folder, "Backups")
    os.makedirs(backup_folder, exist_ok=True)

    name, ext = os.path.splitext(filename)

    backup_filename = f"{name}_BACKUP{ext}"
    backup_path = os.path.join(backup_folder, backup_filename)

    shutil.copy(file_path, backup_path)

def calculate_summary(parts_table):
    summary = {
        "Modeling Hrs": 0,
        "Detailing Hrs": 0,
        "BOM Hrs": 0,
        "QC Hrs": 0,
        "TotalDesignHrs": 0,
        "Total Hrs": 0
    }

    for row in parts_table:
        summary["Modeling Hrs"] += float(row.get("Modeling Hrs", 0) or 0)
        summary["Detailing Hrs"] += float(row.get("Detailing Hrs", 0) or 0)
        summary["BOM Hrs"] += float(row.get("BOM Hrs", 0) or 0)
        summary["QC Hrs"] += float(row.get("QC Hrs", 0) or 0)
        summary["TotalDesignHrs"] += float(row.get("TotalDesignHrs", 0) or 0)
        summary["Total Hrs"] += float(row.get("Total Hrs", 0) or 0)

    for key in summary:
        summary[key] = round(summary[key], 2)

    return summary

def normalize_comment(value):
    if value is None:
        return ""

    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass

    return str(value).strip()

def normalize_loaded_rows(df):
    required_columns = [
    "UniqueID",
    "Team",
    "qBOM",
    "Product Family",
    "Part Name",
    "SET",
    "Low Qty",
    "Medium Qty",
    "Complex Qty",
    "Modeling Hrs",
    "Detailing Hrs",
    "BOM Hrs",
    "QC Hrs",
    "TotalDesignHrs",
    "Total Hrs",
    "Comments"
]

    for col in required_columns:
        if col not in df.columns:
            df[col] = "" if col in ["UniqueID", "Team", "qBOM", "Product Family", "Part Name", "SET"] else 0

    for col in ["UniqueID", "Team", "qBOM", "Product Family", "Part Name", "SET"]:
        df[col] = df[col].fillna("").astype(str).str.strip()

    for col in ["Low Qty", "Medium Qty", "Complex Qty"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).clip(lower=0, upper=99).astype(int)

    for col in ["Modeling Hrs", "Detailing Hrs", "BOM Hrs", "QC Hrs", "TotalDesignHrs", "Total Hrs"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).round(2)

    df["Comments"] = df["Comments"].apply(normalize_comment)

    return df[required_columns]

def get_saved_project_summary(save_folder, filename):
    path = os.path.join(save_folder, filename)

    if not os.path.exists(path):
        return None

    df = pd.read_csv(path)

    if "UniqueID" in df.columns:
        df = df[
            df["UniqueID"].fillna("").astype(str).str.strip().str.upper() != "TOTALS"
        ].copy()

    result = {
        "QBomSaved": filename,
        "Product Family": "",
        "Modeling Hrs": 0,
        "Detailing Hrs": 0,
        "BOM Hrs": 0,
        "QC Hrs": 0,
        "Design Hrs": 0,
        "Total Hrs": 0
    }

    if df.empty:
        return result

    result["Product Family"] = str(df.iloc[0].get("Product Family", "")).strip()

    result["Modeling Hrs"] = round(pd.to_numeric(df["Modeling Hrs"], errors="coerce").fillna(0).sum(), 2)
    result["Detailing Hrs"] = round(pd.to_numeric(df["Detailing Hrs"], errors="coerce").fillna(0).sum(), 2)
    result["BOM Hrs"] = round(pd.to_numeric(df["BOM Hrs"], errors="coerce").fillna(0).sum(), 2)
    result["QC Hrs"] = round(pd.to_numeric(df["QC Hrs"], errors="coerce").fillna(0).sum(), 2)
    result["Design Hrs"] = round(pd.to_numeric(df["TotalDesignHrs"], errors="coerce").fillna(0).sum(), 2)
    result["Total Hrs"] = round(pd.to_numeric(df["Total Hrs"], errors="coerce").fillna(0).sum(), 2)

    return result

def build_blank_summary_rows(n=10):
    rows = []
    for _ in range(n):
        rows.append({
            "QBomSaved": "",
            "Phase": 0,
            "Primary L1s Qty": 0,
            "Secondary L1s Qty": 0,
            "Tertiary L1s Qty": 0,
            "Product Family": "",
            "Modelling hours * Quantity": 0,
            "Detailling Hours * Quantity": 0,
            "BOM Hours * Quantity": 0,
            "QC Hours * Quantity": 0,
            "Design Hours * Quantity": 0,
            "Total Hours (Primary L1s) * Quantity": 0,
            "Secondary L1s": 0,
            "Tertiary L1s": 0
        })
    return rows

def calculate_summary_row(project_data, phase, primaryquantity, secondaryquantity, tertiaryquantity):
    primaryquantity = max(0, int(primaryquantity or 0))
    secondaryquantity = max(0, int(secondaryquantity or 0))
    tertiaryquantity = max(0, int(tertiaryquantity or 0))
    phase = max(0, int(phase or 0))

    modeling = round(weighted_hours(project_data["Modeling Hrs"], primaryquantity, secondaryquantity, tertiaryquantity), 2)
    detailing = round(weighted_hours(project_data["Detailing Hrs"], primaryquantity, secondaryquantity, tertiaryquantity), 2)
    bom = round(weighted_hours(project_data["BOM Hrs"], primaryquantity, secondaryquantity, tertiaryquantity), 2)
    qc = round(weighted_hours(project_data["QC Hrs"], primaryquantity, secondaryquantity, tertiaryquantity), 2)
    design = round(modeling+detailing+bom, 2)
    base_total = (
        project_data["Modeling Hrs"]
        + project_data["Detailing Hrs"]
        + project_data["BOM Hrs"]
        + project_data["QC Hrs"]
    )
    primary = round(base_total * primaryquantity * PRIMARY_L1_WEIGHT, 2)
    secondary = round(base_total * secondaryquantity * SECONDARY_L1_WEIGHT, 2)
    tertiary = round(base_total * tertiaryquantity * TERTIARY_L1_WEIGHT, 2)

    return { 
        "QBomSaved": project_data["QBomSaved"],
        "Phase": phase,
        "Primary L1s Qty": primaryquantity,
        "Secondary L1s Qty": secondaryquantity,
        "Tertiary L1s Qty": tertiaryquantity,
        "Product Family": project_data["Product Family"],
        "Modelling hours * Quantity": modeling,
        "Detailling Hours * Quantity": detailing,
        "BOM Hours * Quantity": bom,
        "QC Hours * Quantity": qc,
        "Design Hours * Quantity": design,
        "Total Hours (Primary L1s) * Quantity": primary,
        "Secondary L1s": secondary,
        "Tertiary L1s": tertiary
    }

def calculate_summary_tab_totals(rows):
    totals = {
        "Modelling hours * Quantity": 0,
        "Detailling Hours * Quantity": 0,
        "BOM Hours * Quantity": 0,
        "QC Hours * Quantity": 0,
        "Design Hours * Quantity": 0,
        "Total Hours (Primary L1s) * Quantity": 0,
        "Secondary L1s": 0,
        "Tertiary L1s": 0
    }

    for row in rows:
        for key in totals:
            totals[key] += float(row.get(key, 0) or 0)

    for key in totals:
        totals[key] = round(totals[key], 2)

    return totals

def save_summary_project(summary_folder, summary_name, form, row_count=10):
    summary_name = str(summary_name).strip()
    if not summary_name:
        return False, "Please enter a summary file name."

    if not summary_name.lower().endswith(".csv"):
        summary_name += ".csv"

    path = os.path.join(summary_folder, summary_name)

    if os.path.exists(path):
        create_backup_if_exists(summary_folder, summary_name)

    rows_to_save = []
    summary_id = os.path.splitext(summary_name)[0]

    for i in range(row_count):
        qbom_saved = str(form.get(f"qbom_saved_{i}", "")).strip()
        phase = int(form.get(f"phase_{i}", 0) or 0)
        primaryquantity = int(form.get(f"primaryquantity_{i}", 0) or 0)
        secondaryquantity = int(form.get(f"secondaryquantity_{i}", 0) or 0)
        tertiaryquantity = int(form.get(f"tertiaryquantity_{i}", 0) or 0)
        comments = str(form.get(f"comments_{i}", "")).strip()

        if qbom_saved or phase != 0 or primaryquantity != 0 or secondaryquantity != 0 or tertiaryquantity != 0:
            if qbom_saved:
                project_data = get_saved_project_summary(SAVE_FOLDER, qbom_saved)

                if project_data:
                    calculated_row = calculate_summary_row(
                        project_data,
                        phase,
                        primaryquantity,
                        secondaryquantity,
                        tertiaryquantity
                    )
                else:
                    calculated_row = build_blank_summary_rows(1)[0]
                    calculated_row["QBomSaved"] = qbom_saved
                    calculated_row["Phase"] = phase
                    calculated_row["Primary L1s Qty"] = primaryquantity
                    calculated_row["Secondary L1s Qty"] = secondaryquantity
                    calculated_row["Tertiary L1s Qty"] = tertiaryquantity
            else:
                calculated_row = build_blank_summary_rows(1)[0]
                calculated_row["Phase"] = phase
                calculated_row["Primary L1s Qty"] = primaryquantity
                calculated_row["Secondary L1s Qty"] = secondaryquantity
                calculated_row["Tertiary L1s Qty"] = tertiaryquantity

            rows_to_save.append({
                "SummaryID": summary_id,
                "QBomSaved": calculated_row["QBomSaved"],
                "Phase": calculated_row["Phase"],
                "Primary L1s Qty": calculated_row["Primary L1s Qty"],
                "Secondary L1s Qty": calculated_row["Secondary L1s Qty"],
                "Tertiary L1s Qty": calculated_row["Tertiary L1s Qty"],
                "Product Family": calculated_row["Product Family"],
                "Modelling hours * Quantity": calculated_row["Modelling hours * Quantity"],
                "Detailling Hours * Quantity": calculated_row["Detailling Hours * Quantity"],
                "BOM Hours * Quantity": calculated_row["BOM Hours * Quantity"],
                "QC Hours * Quantity": calculated_row["QC Hours * Quantity"],
                "Design Hours * Quantity": calculated_row["Design Hours * Quantity"],
                "Total Hours (Primary L1s) * Quantity": calculated_row["Total Hours (Primary L1s) * Quantity"],
                "Secondary L1s": calculated_row["Secondary L1s"],
                "Tertiary L1s": calculated_row["Tertiary L1s"],
                "Grand Total Hours": round(
                    float(calculated_row.get("Total Hours (Primary L1s) * Quantity", 0) or 0)
                    + float(calculated_row.get("Secondary L1s", 0) or 0)
                    + float(calculated_row.get("Tertiary L1s", 0) or 0),
                    2
                ),
                "Comments": comments
            })

    ordered_columns = [
        "SummaryID",
        "QBomSaved",
        "Phase",
        "Primary L1s Qty",
        "Secondary L1s Qty",
        "Tertiary L1s Qty",
        "Product Family",
        "Modelling hours * Quantity",
        "Detailling Hours * Quantity",
        "BOM Hours * Quantity",
        "QC Hours * Quantity",
        "Design Hours * Quantity",
        "Total Hours (Primary L1s) * Quantity",
        "Secondary L1s",
        "Tertiary L1s",
        "Grand Total Hours",
        "Comments"
    ]
    summary_totals = calculate_summary_tab_totals(rows_to_save)

    totals_row = {
        "SummaryID": "TOTALS",
        "QBomSaved": "",
        "Phase": "",
        "Primary L1s Qty": "",
        "Secondary L1s Qty": "",
        "Tertiary L1s Qty": "",
        "Product Family": "",
        "Modelling hours * Quantity": round(summary_totals.get("Modelling hours * Quantity", 0), 2),
        "Detailling Hours * Quantity": round(summary_totals.get("Detailling Hours * Quantity", 0), 2),
        "BOM Hours * Quantity": round(summary_totals.get("BOM Hours * Quantity", 0), 2),
        "QC Hours * Quantity": round(summary_totals.get("QC Hours * Quantity", 0), 2),
        "Design Hours * Quantity": round(summary_totals.get("Design Hours * Quantity", 0), 2),
        "Total Hours (Primary L1s) * Quantity": round(summary_totals.get("Total Hours (Primary L1s) * Quantity", 0), 2),
        "Secondary L1s": round(summary_totals.get("Secondary L1s", 0), 2),
        "Tertiary L1s": round(summary_totals.get("Tertiary L1s", 0), 2),
        "Grand Total Hours": round(
                float(summary_totals.get("Total Hours (Primary L1s) * Quantity", 0) or 0)
                + float(summary_totals.get("Secondary L1s", 0) or 0)
                + float(summary_totals.get("Tertiary L1s", 0) or 0),
                2
            ),
        "Comments": ""
    }


    rows_to_save.append(totals_row)

    df = pd.DataFrame(rows_to_save, columns=ordered_columns)
    text_columns = [
        "SummaryID",
        "QBomSaved",
        "Phase",
        "Primary L1s Qty",
        "Secondary L1s Qty",
        "Tertiary L1s Qty",
        "Product Family",
        "Comments"
    ]

    for col in text_columns:
        if col in df.columns:
            df[col] = df[col].fillna("").astype(str).str.strip()
    df.to_csv(path, index=False)

    return True, f"Summary saved as '{summary_name}' successfully."

def load_summary_project(summary_folder, save_folder, filename):
    filename = str(filename).strip()

    if not filename:
        return build_blank_summary_rows(10), "Please select a summary file to load."

    path = os.path.join(summary_folder, filename)

    if not os.path.exists(path):
        return build_blank_summary_rows(10), f"Summary file '{filename}' was not found."

    df = pd.read_csv(path)

    if df.empty:
        return build_blank_summary_rows(10), ""

    rows = []

    for _, saved_row in df.iterrows():
        qbom_saved = str(saved_row.get("QBomSaved", "")).strip()
        phase = int(saved_row.get("Phase", 0) or 0)
        primaryquantity = int(saved_row.get("Primary L1s Qty", 0) or 0)
        secondaryquantity = int(saved_row.get("Secondary L1s Qty", 0) or 0)
        tertiaryquantity = int(saved_row.get("Tertiary L1s Qty", 0) or 0)

        if qbom_saved:
            project_data = get_saved_project_summary(save_folder, qbom_saved)

            if project_data is not None:
                row = calculate_summary_row(project_data, phase, primaryquantity, secondaryquantity, tertiaryquantity)
            else:
                row = build_blank_summary_rows(1)[0]
                row["QBomSaved"] = qbom_saved
                row["Phase"] = phase
                row["Primary L1s Qty"] = primaryquantity
                row["Secondary L1s Qty"] = secondaryquantity
                row["Tertiary L1s Qty"] = tertiaryquantity
        else:
            row = build_blank_summary_rows(1)[0]
            row["Phase"] = phase
            row["Primary L1s Qty"] = primaryquantity
            row["Secondary L1s Qty"] = secondaryquantity
            row["Tertiary L1s Qty"] = tertiaryquantity
        rows.append(row)

    while len(rows) < 10:
        rows.append(build_blank_summary_rows(1)[0])

    return rows[:10], ""

def extract_set_number(set_value):
    text = str(set_value).strip()
    match = re.search(r"\d+", text)
    return int(match.group()) if match else 9999

def rebuild_summary_from_cache(cache_data):
    rows = []

    for i in range(10):
        qbom_saved = str(cache_data.get(f"qbom_saved_{i}", "")).strip()
        phase = cache_data.get(f"phase_{i}", 0)
        primaryquantity = cache_data.get(f"primaryquantity_{i}", 0)
        secondaryquantity = cache_data.get(f"secondaryquantity_{i}", 0)
        tertiaryquantity = cache_data.get(f"tertiaryquantity_{i}", 0)
        comments = normalize_comment(cache_data.get(f"comments_{i}", ""))

        if qbom_saved:
            project_data = get_saved_project_summary(SAVE_FOLDER, qbom_saved)
            if project_data:
                row = calculate_summary_row(
                    project_data,
                    phase,
                    primaryquantity,
                    secondaryquantity,
                    tertiaryquantity
                )
            else:
                row = build_blank_summary_rows(1)[0]
        else:
            row = build_blank_summary_rows(1)[0]
            row["Phase"] = int(phase or 0)
            row["Primary L1s Qty"] = int(primaryquantity or 0)
            row["Secondary L1s Qty"] = int(secondaryquantity or 0)
            row["Tertiary L1s Qty"] = int(tertiaryquantity or 0)

        row["Comments"] = comments
        rows.append(row)

    return rows

def sort_estimator_rows(rows):
    priority = {7: 0, 8: 1, 9: 2}

    return sorted(
        rows,
        key=lambda row: (
            priority.get(extract_set_number(row.get("SET", "")), 3),
            extract_set_number(row.get("SET", "")),
            str(row.get("Part Name", "")).lower()
        )
    )

def build_qbom_filename(project_name, selected_qbom, team):
    project_name = os.path.splitext(str(project_name).strip())[0]
    project_name = clean_file_part(project_name)

    team = str(team).strip().upper()
    qbom_suffix = get_qbom_suffix(selected_qbom, team)

    if not project_name:
        return ""

    # Prevent Project1_Blower_Blower.csv
    if qbom_suffix and project_name.upper().endswith("_" + qbom_suffix.upper()):
        file_name = project_name
    elif qbom_suffix:
        file_name = f"{project_name}_{qbom_suffix}"
    else:
        file_name = project_name

    if not file_name.lower().endswith(".csv"):
        file_name += ".csv"

    return file_name

def clean_file_part(value):
    value = str(value).strip()

    invalid_chars = '<>:"/\\|?*'
    for ch in invalid_chars:
        value = value.replace(ch, "_")

    # Replace spaces with underscores
    value = "_".join(value.split())

    return value

def get_qbom_suffix(selected_qbom, team):
    selected_qbom = str(selected_qbom).strip()
    team = str(team).strip().upper()

    if not selected_qbom:
        return ""

    if team == "ETO":
        return clean_file_part(selected_qbom)

    qbom_parts = selected_qbom.split()

    if len(qbom_parts) > 1:
        return clean_file_part(" ".join(qbom_parts[1:]))

    return ""


def get_project_name_from_loaded_filename(file_name, selected_qbom, team):
    base_name = os.path.splitext(str(file_name).strip())[0]
    suffix = get_qbom_suffix(selected_qbom, team)

    if suffix and base_name.upper().endswith("_" + suffix.upper()):
        base_name = base_name[:-(len(suffix) + 1)]

    return base_name

@app.route("/", methods=["GET", "POST"])
def index():  
    estimator = DesignHourEstimatorData(EXCEL_FILE)
    estimator.load_data()

    parts_df = estimator.parts_df.copy()
    hours_df = estimator.hours_df.copy()

    selected_qbom = ""
    selected_product_family = ""
    selected_team = ""
    error_message = ""
    success_message = ""
    warning_message = ""
    save_file_name = ""
    overwrite_pending = False
    confirm_overwrite = "0"

    if request.method == "POST":
        selected_team = request.form.get("team", "").strip()
        selected_product_family = request.form.get("product_family", "").strip()
        selected_qbom = request.form.get("qbom", "").strip()
        save_file_name = request.form.get("save_file_name", save_file_name).strip()


    # -----------------------------
    # 1. Team options
    # -----------------------------
    team_options = sorted(
        hours_df["Team"]
        .dropna()
        .astype(str)
        .str.strip()
        .replace("", None)
        .dropna()
        .unique()
        .tolist()
    )


    # -----------------------------
    # 2. Product Families filtered by Team
    # From hours sheet:
    # Team -> ProductFamily
    # -----------------------------
    if selected_team:
        pf_source_df = hours_df[
            hours_df["Team"].astype(str).str.strip().str.upper()
            == selected_team.strip().upper()
        ].copy()
    else:
        pf_source_df = hours_df.iloc[0:0].copy()

    product_family_options = sorted(
        pf_source_df["ProductFamily"]
        .dropna()
        .astype(str)
        .str.strip()
        .replace("", None)
        .dropna()
        .unique()
        .tolist()
    )


    # Reset Product Family if it does not belong to selected Team
    if selected_product_family and selected_product_family not in product_family_options:
        selected_product_family = ""
        selected_qbom = ""


    # -----------------------------
    # 3. Subsystems/qBOMs filtered by Product Family
    # From parts sheet:
    # Product Family -> Sheet
    # -----------------------------
    if selected_product_family:
        qbom_source_df = parts_df[
            parts_df["Product Family"].astype(str).str.strip().str.upper()
            == selected_product_family.strip().upper()
        ].copy()
    else:
        qbom_source_df = parts_df.iloc[0:0].copy()

    qbom_options = sorted(
        qbom_source_df["Sheet"]
        .dropna()
        .astype(str)
        .str.strip()
        .replace("", None)
        .dropna()
        .unique()
        .tolist()
    )


    # Reset Subsystem/qBOM if it does not belong to selected Product Family
    if selected_qbom and selected_qbom not in qbom_options:
        selected_qbom = ""
    # -----------------------------
    # 4. Final parts filter
    # Only show rows when Product Family + Subsystem are selected
    # -----------------------------
    if selected_product_family and selected_qbom:
        filtered_parts_df = parts_df.copy()

        filtered_parts_df = filtered_parts_df[
            filtered_parts_df["Product Family"].astype(str).str.strip().str.upper()
            == selected_product_family.strip().upper()
        ]

        filtered_parts_df = filtered_parts_df[
            filtered_parts_df["Sheet"].astype(str).str.strip().str.upper()
            == selected_qbom.strip().upper()
        ]
    else:
        filtered_parts_df = parts_df.iloc[0:0].copy()

    rows = []
    summary = {
        "Modeling Hrs": 0,
        "Detailing Hrs": 0,
        "BOM Hrs": 0,
        "QC Hrs": 0,
        "TotalDesignHrs": 0,
        "Total Hrs": 0
    }
    action = request.form.get("action", "") if request.method == "POST" else ""

    if request.method == "POST" and action == "load_csv":
        uploaded_file = request.files.get("csv_file")
        if uploaded_file and uploaded_file.filename.lower().endswith(".csv"):
            save_file_name = uploaded_file.filename
            df = pd.read_csv(uploaded_file)
            # Ignore TOTALS row if the saved qBOM CSV has it
            if "UniqueID" in df.columns:
                df = df[df["UniqueID"].astype(str).str.strip().str.upper() != "TOTALS"].copy()

            # Support old CSVs that do not have Comments yet
            if "Comments" not in df.columns:
                df["Comments"] = ""

            df["Comments"] = df["Comments"].fillna("").astype(str).str.strip()
            df = normalize_loaded_rows(df)

            rows = df.to_dict(orient="records")
            rows = sort_estimator_rows(rows)
            summary = calculate_summary(rows)
            selected_team = ""
            selected_qbom = ""
            selected_product_family = ""
            if "UniqueID" in df.columns:
                df = df[df["UniqueID"].astype(str).str.strip().str.upper() != "TOTALS"].copy()
            if not df.empty:
                selected_qbom = str(df.iloc[0].get("qBOM", "")).strip()
                selected_product_family = str(df.iloc[0].get("Product Family", "")).strip()
                selected_team = str(df.iloc[0].get("Team", "")).strip()
                save_file_name = get_project_name_from_loaded_filename(
                    uploaded_file.filename,
                    selected_qbom,
                    selected_team
                )

                # Rebuild Product Family dropdown based on loaded Team
                if selected_team:
                    pf_source_df = hours_df[
                        hours_df["Team"].astype(str).str.strip().str.upper()
                        == selected_team.strip().upper()
                    ].copy()
                else:
                    pf_source_df = hours_df.iloc[0:0].copy()

                product_family_options = sorted(
                    pf_source_df["ProductFamily"]
                    .dropna()
                    .astype(str)
                    .str.strip()
                    .replace("", None)
                    .dropna()
                    .unique()
                    .tolist()
                )

                # Rebuild Subsystem dropdown based on loaded Product Family
                if selected_product_family:
                    qbom_source_df = parts_df[
                        parts_df["Product Family"].astype(str).str.strip().str.upper()
                        == selected_product_family.strip().upper()
                    ].copy()
                else:
                    qbom_source_df = parts_df.iloc[0:0].copy()

                qbom_options = sorted(
                    qbom_source_df["Sheet"]
                    .dropna()
                    .astype(str)
                    .str.strip()
                    .replace("", None)
                    .dropna()
                    .unique()
                    .tolist()
                )
            confirm_overwrite = "1"
            return render_template(
                "index.html",
                team_options=team_options,
                qbom_options=qbom_options,
                product_family_options=product_family_options,
                selected_team=selected_team,
                selected_qbom=selected_qbom,
                selected_product_family=selected_product_family,
                rows=rows,
                summary=summary,
                save_file_name=save_file_name,
                error_message="",
                success_message=f"Loaded '{uploaded_file.filename}' successfully.",
                warning_message="",
                overwrite_pending=False,
                confirm_overwrite="1"
            )

    if selected_qbom and selected_product_family and selected_team:
        base_rows = estimator.get_parts_with_sets(
            qbom=selected_qbom,
            product_family=selected_product_family
        )
        row_count = int(request.form.get("row_count", 0) or 0)

        if base_rows.empty:
            error_message = (
                "Invalid selection: no Part Name records were found for the selected "
                "QBOM and Product Family"
            )

            selected_qbom = ""
            selected_product_family = ""

            qbom_options = sorted(
                parts_df["Sheet"].dropna().astype(str).str.strip().replace("", None).dropna().unique().tolist()
            )
            product_family_options = sorted(
                parts_df["Product Family"].dropna().astype(str).str.strip().replace("", None).dropna().unique().tolist()
            )

            rows = []

        elif action == "reset_complexity" and row_count > 0:
            rows = []
            for i in range(row_count):
                part_name = request.form.get(f"part_name_{i}", "").strip()
                set_value = request.form.get(f"set_{i}", "").strip()
                

                totals = estimator.calculate_part_hours(
                    set_value=set_value,
                    product_family=selected_product_family,
                    team=selected_team,
                    low_qty=0,
                    med_qty=0,
                    complex_qty=0
                ) if set_value else {
                    "Modeling Hrs": 0,
                    "Detailing Hrs": 0,
                    "BOM Hrs": 0,
                    "QC Hrs": 0,
                    "TotalDesignHrs": 0,
                    "Total Hrs": 0
                }

                rows.append({
                    "Part Name": part_name,
                    "SET": set_value,
                    "Low Qty": 0,
                    "Medium Qty": 0,
                    "Complex Qty": 0,
                    "Modeling Hrs": round(float(totals["Modeling Hrs"]), 2),
                    "Detailing Hrs": round(float(totals["Detailing Hrs"]), 2),
                    "BOM Hrs": round(float(totals["BOM Hrs"]), 2),
                    "QC Hrs": round(float(totals["QC Hrs"]), 2),
                    "TotalDesignHrs": round(float(totals["TotalDesignHrs"]), 2),
                    "Total Hrs": round(float(totals["Total Hrs"]), 2),
                    "Comments": ""
                })

        elif row_count > 0:
            rows = []
            for i in range(row_count):
                part_name = request.form.get(f"part_name_{i}", "").strip()
                set_value = request.form.get(f"set_{i}", "").strip()

                low_qty = int(request.form.get(f"low_qty_{i}", 0) or 0)
                med_qty = int(request.form.get(f"med_qty_{i}", 0) or 0)
                complex_qty = int(request.form.get(f"complex_qty_{i}", 0) or 0)

                low_qty = max(0, min(99, low_qty))
                med_qty = max(0, min(99, med_qty))
                complex_qty = max(0, min(99, complex_qty))

                totals = estimator.calculate_part_hours(
                    set_value=set_value,
                    product_family=selected_product_family,
                    team=selected_team,
                    low_qty=low_qty,
                    med_qty=med_qty,
                    complex_qty=complex_qty
                ) if set_value else {
                    "Modeling Hrs": 0,
                    "Detailing Hrs": 0,
                    "BOM Hrs": 0,
                    "QC Hrs": 0,
                    "TotalDesignHrs": 0,
                    "Total Hrs": 0
                }

                rows.append({
                    "Part Name": part_name,
                    "SET": set_value,
                    "Low Qty": low_qty,
                    "Medium Qty": med_qty,
                    "Complex Qty": complex_qty,
                    "Modeling Hrs": round(float(totals["Modeling Hrs"]), 2),
                    "Detailing Hrs": round(float(totals["Detailing Hrs"]), 2),
                    "BOM Hrs": round(float(totals["BOM Hrs"]), 2),
                    "QC Hrs": round(float(totals["QC Hrs"]), 2),
                    "TotalDesignHrs": round(float(totals["TotalDesignHrs"]), 2),
                    "Total Hrs": round(float(totals["Total Hrs"]), 2),
                    "Comments": request.form.get(f"comments_{i}", "").strip()
                })

        else:
            rows = []
            for _, row in base_rows.iterrows():
                part_name = row["Part Name"]
                set_value = row["SET"]

                low_qty = int(row.get("Low", 0) or 0)
                med_qty = int(row.get("Medium", 0) or 0)
                complex_qty = int(row.get("Complex", 0) or 0)

                low_qty = max(0, min(99, low_qty))
                med_qty = max(0, min(99, med_qty))
                complex_qty = max(0, min(99, complex_qty))

                totals = estimator.calculate_part_hours(
                    set_value=set_value,
                    product_family=selected_product_family,
                    team=selected_team,
                    low_qty=low_qty,
                    med_qty=med_qty,
                    complex_qty=complex_qty
                ) if set_value else {
                    "Modeling Hrs": 0,
                    "Detailing Hrs": 0,
                    "BOM Hrs": 0,
                    "QC Hrs": 0,
                    "TotalDesignHrs": 0,
                    "Total Hrs": 0
                }

                rows.append({
                    "Part Name": part_name,
                    "SET": set_value,
                    "Low Qty": low_qty,
                    "Medium Qty": med_qty,
                    "Complex Qty": complex_qty,
                    "Modeling Hrs": round(float(totals["Modeling Hrs"]), 2),
                    "Detailing Hrs": round(float(totals["Detailing Hrs"]), 2),
                    "BOM Hrs": round(float(totals["BOM Hrs"]), 2),
                    "QC Hrs": round(float(totals["QC Hrs"]), 2),
                    "TotalDesignHrs": round(float(totals["TotalDesignHrs"]), 2),
                    "Total Hrs": round(float(totals["Total Hrs"]), 2)
                })
    rows = sort_estimator_rows(rows)
    summary = calculate_summary(rows)
    if request.method == "POST" and action == "save_csv":
        project_name = request.form.get("save_file_name", "").strip()
        selected_qbom_for_name = request.form.get("qbom", "").strip()
        confirm_overwrite = request.form.get("confirm_overwrite", "0") == "1"
        saved_team = (
            request.form.get("team")
            or request.form.get("selected_team")
            or selected_team
            or ""
        ).strip()
        save_file_name = build_qbom_filename(project_name, selected_qbom_for_name, saved_team)

        if not save_file_name:
            error_message = "Please enter a project name before saving the CSV."
        else:
            if not save_file_name.lower().endswith(".csv"):
                save_file_name += ".csv"

            save_path = os.path.join(SAVE_FOLDER, save_file_name)

            if os.path.exists(save_path) and not confirm_overwrite:
                warning_message = f"The file '{save_file_name}' already exists. Click overwrite to replace it."
                overwrite_pending = True
                confirm_overwrite = "1"
            else:
                row_count = int(request.form.get("row_count", 0) or 0)
                rows_to_save = []

                saved_qbom = request.form.get("qbom", "").strip()
                saved_product_family = request.form.get("product_family", "").strip()
                unique_id = os.path.splitext(save_file_name)[0]

                for i in range(row_count):
                    rows_to_save.append({
                        "UniqueID": unique_id,
                        "Team": saved_team,
                        "qBOM": saved_qbom,
                        "Product Family": saved_product_family,
                        "Part Name": request.form.get(f"part_name_{i}", "").strip(),
                        "SET": request.form.get(f"set_{i}", "").strip(),
                        "Low Qty": int(request.form.get(f"low_qty_{i}", 0) or 0),
                        "Medium Qty": int(request.form.get(f"med_qty_{i}", 0) or 0),
                        "Complex Qty": int(request.form.get(f"complex_qty_{i}", 0) or 0),
                        "Modeling Hrs": float(request.form.get(f"modeling_hrs_{i}", 0) or 0),
                        "Detailing Hrs": float(request.form.get(f"detailing_hrs_{i}", 0) or 0),
                        "BOM Hrs": float(request.form.get(f"bom_hrs_{i}", 0) or 0),
                        "QC Hrs": float(request.form.get(f"qc_hrs_{i}", 0) or 0),
                        "TotalDesignHrs": float(request.form.get(f"total_design_hrs_{i}", 0) or 0),
                        "Total Hrs": float(request.form.get(f"total_hrs_{i}", 0) or 0),
                        "Comments": request.form.get(f"comments_{i}", "").strip()
                    })

                # ADD TOTALS ROW HERE
                totals_row = {
                    "UniqueID": "TOTALS",
                    "Team": "",
                    "qBOM": "",
                    "Product Family": "",
                    "Part Name": "",
                    "SET": "",
                    "Low Qty": "",
                    "Medium Qty": "",
                    "Complex Qty": "",
                    "Modeling Hrs": round(sum(float(r.get("Modeling Hrs", 0) or 0) for r in rows_to_save), 2),
                    "Detailing Hrs": round(sum(float(r.get("Detailing Hrs", 0) or 0) for r in rows_to_save), 2),
                    "BOM Hrs": round(sum(float(r.get("BOM Hrs", 0) or 0) for r in rows_to_save), 2),
                    "QC Hrs": round(sum(float(r.get("QC Hrs", 0) or 0) for r in rows_to_save), 2),
                    "TotalDesignHrs": round(sum(float(r.get("TotalDesignHrs", 0) or 0) for r in rows_to_save), 2),
                    "Total Hrs": round(sum(float(r.get("Total Hrs", 0) or 0) for r in rows_to_save), 2)
                }

                rows_to_save.append(totals_row)

                df = pd.DataFrame(rows_to_save)
                ordered_columns = [
                    "UniqueID", "Team", "qBOM", "Product Family", "Part Name", "SET",
                    "Low Qty", "Medium Qty", "Complex Qty",
                    "Modeling Hrs", "Detailing Hrs", "BOM Hrs", "QC Hrs",
                    "TotalDesignHrs", "Total Hrs", "Comments"
                ]
                df = df[ordered_columns]

                if os.path.exists(save_path):
                    create_backup_if_exists(SAVE_FOLDER, save_file_name)

                df.to_csv(save_path, index=False)
                success_message = f"Project saved as '{save_file_name}' successfully."
                overwrite_pending = False
                confirm_overwrite = "1"
                return render_template(
                "index.html",
                team_options=team_options,
                qbom_options=qbom_options,
                product_family_options=product_family_options,
                selected_team=selected_team,
                selected_qbom=selected_qbom,
                selected_product_family=selected_product_family,
                rows=rows,
                summary=summary,
                error_message="",
                success_message=success_message,
                save_file_name=save_file_name,
                overwrite_pending=False,
                confirm_overwrite="0"
            )


    return render_template(
        "index.html",
        team_options=team_options,
        qbom_options=qbom_options,
        product_family_options=product_family_options,  
        selected_team=selected_team,
        selected_qbom=selected_qbom,
        selected_product_family=selected_product_family,
        rows=rows,
        summary=summary,
        error_message=error_message,
        success_message=success_message,
        save_file_name=save_file_name,
        overwrite_pending=overwrite_pending,
        confirm_overwrite=confirm_overwrite,
        warning_message=warning_message
    )


@app.route("/summary", methods=["GET", "POST"])
def summary_tab():
    saved_files = sorted([f for f in os.listdir(SAVE_FOLDER) if f.lower().endswith(".csv")])
    saved_summary_files = sorted([f for f in os.listdir(SUMMARY_FOLDER) if f.lower().endswith(".csv")])

    overwrite_pending = False
    confirm_overwrite = "0"
    error_message = ""
    success_message = ""
    warning_message = ""
    save_file_name = ""

    rows = build_blank_summary_rows(10)
    totals = calculate_summary_tab_totals(rows)

    if request.method == "GET" and "summary_cache" in session:
        rows = rebuild_summary_from_cache(session["summary_cache"])
        totals = calculate_summary_tab_totals(rows)
        save_file_name = session["summary_cache"].get("save_file_name", "")

    action = request.form.get("action", "") if request.method == "POST" else ""

    if request.method == "POST":
        save_file_name = request.form.get("save_file_name", save_file_name).strip()

        if action == "save_csv":
            confirm_overwrite = request.form.get("confirm_overwrite", "0") == "1"

            if not save_file_name:
                error_message = "Please enter a summary file name."
            else:
                if not save_file_name.lower().endswith(".csv"):
                    save_file_name += ".csv"

                save_path = os.path.join(SUMMARY_FOLDER, save_file_name)

                if os.path.exists(save_path) and not confirm_overwrite:
                    warning_message = f"The file '{save_file_name}' already exists. Click overwrite to replace it."
                    overwrite_pending = True
                    confirm_overwrite = "1"
                else:
                    ok, msg = save_summary_project(SUMMARY_FOLDER, save_file_name, request.form, row_count=10)
                    if ok:
                        success_message = msg
                        overwrite_pending = False
                        confirm_overwrite = "0"
                        saved_summary_files = sorted(
                            [f for f in os.listdir(SUMMARY_FOLDER) if f.lower().endswith(".csv")]
                        )
                    else:
                        error_message = msg
    
            # Rebuild current screen from current form
            rows = []
            for i in range(10):
                qbom_saved = request.form.get(f"qbom_saved_{i}", "").strip()
                phase = request.form.get(f"phase_{i}", 0)
                primaryquantity = request.form.get(f"primaryquantity_{i}", 0)
                secondaryquantity = request.form.get(f"secondaryquantity_{i}", 0)
                tertiaryquantity = request.form.get(f"tertiaryquantity_{i}", 0)

                if qbom_saved:
                    project_data = get_saved_project_summary(SAVE_FOLDER, qbom_saved)
                    if project_data:
                        row = calculate_summary_row(project_data, phase, primaryquantity, secondaryquantity, tertiaryquantity)
                    else:
                        row = build_blank_summary_rows(1)[0]
                        row["QBomSaved"] = qbom_saved
                        row["Phase"] = int(phase or 0)
                        row["Primary L1s Qty"] = int(primaryquantity or 0)
                        row["Secondary L1s Qty"] = int(secondaryquantity or 0)
                        row["Tertiary L1s Qty"] = int(tertiaryquantity or 0)
                else:
                    row = build_blank_summary_rows(1)[0]
                    row["Phase"] = int(phase or 0)
                    row["Primary L1s Qty"] = int(primaryquantity or 0)
                    row["Secondary L1s Qty"] = int(secondaryquantity or 0)
                    row["Tertiary L1s Qty"] = int(tertiaryquantity or 0)
                row["Comments"] = request.form.get(f"comments_{i}", "").strip()
                rows.append(row)

            totals = calculate_summary_tab_totals(rows)
            

        elif action == "load_csv":
            uploaded_file = request.files.get("csv_file")

            if uploaded_file is None or uploaded_file.filename == "":
                error_message = "Please select a summary CSV file to load."
                rows = build_blank_summary_rows(10)
                totals = calculate_summary_tab_totals(rows)
            else:
                try:
                    df = pd.read_csv(uploaded_file)
                    save_file_name = os.path.splitext(uploaded_file.filename)[0]
                    if "SummaryID" in df.columns:
                        df = df[df["SummaryID"].astype(str).str.strip().str.upper() != "TOTALS"].copy()
                    rows = []

                    for _, saved_row in df.iterrows():
                        qbom_saved = str(saved_row.get("QBomSaved", "")).strip()
                        phase = int(saved_row.get("Phase", 0) or 0)
                        primaryquantity = int(saved_row.get("Primary L1s Qty", 0) or 0)
                        secondaryquantity = int(saved_row.get("Secondary L1s Qty", 0) or 0)
                        tertiaryquantity = int(saved_row.get("Tertiary L1s Qty", 0) or 0)

                        if qbom_saved:
                            project_data = get_saved_project_summary(SAVE_FOLDER, qbom_saved)

                            if project_data is not None:
                                row = calculate_summary_row(project_data, phase, primaryquantity,secondaryquantity,tertiaryquantity)
                            else:
                                row = build_blank_summary_rows(1)[0]
                                row["QBomSaved"] = qbom_saved
                                row["Phase"] = phase
                                row['Primary L1s Qty'] = primaryquantity 
                                row['Secondary L1s Qty'] = secondaryquantity 
                                row['Tertiary L1s Qty'] = tertiaryquantity 
                        else:
                            row = build_blank_summary_rows(1)[0]
                            row["Phase"] = phase
                            row['Primary L1s Qty'] = primaryquantity 
                            row['Secondary L1s Qty'] = secondaryquantity 
                            row['Tertiary L1s Qty'] = tertiaryquantity 
                        row["Comments"] = normalize_comment(saved_row.get("Comments", ""))
                        rows.append(row)

                    while len(rows) < 10:
                        rows.append(build_blank_summary_rows(1)[0])

                    rows = rows[:10]
                    totals = calculate_summary_tab_totals(rows)

                except Exception as e:
                    error_message = f"Could not load summary CSV: {e}"
                    rows = build_blank_summary_rows(10)
                    totals = calculate_summary_tab_totals(rows)

        else:
            # Update summary
            rows = []
            for i in range(10):
                qbom_saved = request.form.get(f"qbom_saved_{i}", "").strip()
                phase = request.form.get(f"phase_{i}", 0)
                primaryquantity = request.form.get(f"primaryquantity_{i}", 0)
                secondaryquantity = request.form.get(f"secondaryquantity_{i}", 0)
                tertiaryquantity = request.form.get(f"tertiaryquantity_{i}", 0)

                if qbom_saved:
                    project_data = get_saved_project_summary(SAVE_FOLDER, qbom_saved)
                    if project_data:
                        row = calculate_summary_row(project_data, phase, primaryquantity,secondaryquantity,tertiaryquantity)
                    else:
                        row = build_blank_summary_rows(1)[0]
                        row["QBomSaved"] = qbom_saved
                        row["Phase"] = int(phase or 0)
                        row['Primary L1s Qty'] = int(primaryquantity or 0)
                        row['Secondary L1s Qty'] = int(secondaryquantity or 0)
                        row['Tertiary L1s Qty'] = int(tertiaryquantity or 0)
                else:
                    row = build_blank_summary_rows(1)[0]
                    row["Phase"] = int(phase or 0)
                    row['Primary L1s Qty'] = int(primaryquantity or 0)
                    row['Secondary L1s Qty'] = int(secondaryquantity or 0)
                    row['Tertiary L1s Qty'] = int(tertiaryquantity or 0)
                row["Comments"] = request.form.get(f"comments_{i}", "").strip()
                rows.append(row)

            totals = calculate_summary_tab_totals(rows)

    return render_template(
        "summary.html",
        saved_files=saved_files,
        saved_summary_files=saved_summary_files,
        rows=rows,
        totals=totals,
        error_message=error_message,
        success_message=success_message,
        save_file_name=save_file_name,
        overwrite_pending=overwrite_pending,
        confirm_overwrite=confirm_overwrite,
        warning_message=warning_message
    )


@app.route("/cache_summary", methods=["POST"])
def cache_summary():
    data = request.get_json(silent=True) or {}
    session["summary_cache"] = data
    session.modified = True
    return jsonify({"status": "ok"})

@app.route("/data-management", methods=["GET", "POST"])
def data_management():
    estimator = DesignHourEstimatorData(EXCEL_FILE)
    estimator.load_data()

    selected_team = ""
    selected_sheet = ""
    rows = []
    columns = []

    team_options = sorted(
        estimator.hours_df["Team"]
        .dropna()
        .astype(str)
        .str.strip()
        .replace("", None)
        .dropna()
        .unique()
        .tolist()
    )

    if request.method == "POST":
        selected_team = request.form.get("team", "").strip()
        selected_sheet = request.form.get("sheet_view", "").strip()

        if selected_team and selected_sheet:
            if selected_sheet == "hours":
                df = estimator.hours_df[
                    estimator.hours_df["Team"].astype(str).str.strip() == selected_team
                ].copy()

            elif selected_sheet == "parts":
                team_product_families = (
                    estimator.hours_df[
                        estimator.hours_df["Team"].astype(str).str.strip() == selected_team
                    ]["ProductFamily"]
                    .dropna()
                    .astype(str)
                    .str.strip()
                    .unique()
                    .tolist()
                )

                df = estimator.parts_df[
                    estimator.parts_df["Product Family"]
                    .astype(str)
                    .str.strip()
                    .isin(team_product_families)
                ].copy()
            else:
                df = pd.DataFrame()

            columns = df.columns.tolist()
            rows = df.fillna("").to_dict(orient="records")

    return render_template(
        "data_management.html",
        team_options=team_options,
        selected_team=selected_team,
        selected_sheet=selected_sheet,
        columns=columns,
        rows=rows
    )

if __name__ == "__main__":
    port = find_available_port(start_port=5000)
    Timer(1.5, open_browser, args=(port,)).start()

    print(f"Running on http://127.0.0.1:{port}/", flush=True)
    app.run(port=port, debug=False, use_reloader=False)
