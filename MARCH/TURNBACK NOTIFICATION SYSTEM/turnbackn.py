"""
Turnback Notification System - GUI (ttkbootstrap)

Features:
- Select Users file and Turnbacks file
- Optional first-run-of-month reset for monthly history
- Filters current-month Turnbacks only
- Matches users by name
- Skips ambiguous matches
- Sends emails through Classic Outlook
- Prevents duplicate completion emails within the same month
- Shows unmatched, ambiguous, and skipped cases
- Saves latest outbox, report, and send log files

Requirements:
pip install ttkbootstrap pandas pywin32 openpyxl
"""

import os
import re
import time
import unicodedata
import threading
from datetime import datetime
import pandas as pd
import ttkbootstrap as tb      
from ttkbootstrap.constants import *
from tkinter import filedialog, messagebox, ttk
import tkinter.font as tkfont



GOAL_TURNBACKS = 4
USERS_EMPLOYEE_COL = "Employee"          
USERS_EMAIL_COL = "Email"

TURNBACK_REPORTED_BY_COL = "Reported By"
TURNBACK_REPORTED_DATE_COL = "Reported Date"
TURNBACK_TYPE_COL = "Type" 
TURNBACK_TYPE_VALUE = "Turnback"

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")


# -----------------------------
# Core logic 
# -----------------------------
def load_data(file_path: str) -> pd.DataFrame:
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".csv":
        return pd.read_csv(file_path)
    if ext in (".xlsx", ".xls"):
        return pd.read_excel(file_path)
    raise ValueError(f"Format {ext} not supported. Use CSV or Excel.")

def filter_turnbacks_current_month_and_type(df_turnbacks: pd.DataFrame,reported_date_col: str = TURNBACK_REPORTED_DATE_COL,type_col: str = TURNBACK_TYPE_COL,required_type: str = TURNBACK_TYPE_VALUE,) -> tuple[pd.DataFrame, pd.DataFrame]:
    df = df_turnbacks.copy()
    df[reported_date_col] = pd.to_datetime(df[reported_date_col], errors="coerce")

    now = datetime.now()
    keep = (
        df[reported_date_col].notna()
        & (df[reported_date_col].dt.year == now.year)
        & (df[reported_date_col].dt.month == now.month)
        & (df[type_col].astype(str).str.strip().str.lower() == required_type.lower())
    )
    return df.loc[keep].copy(), df.loc[~keep].copy()

def normalize_text(s: object) -> str:
    if pd.isna(s):
        return ""
    s = str(s).strip()
    s = "".join(ch for ch in unicodedata.normalize("NFKD", s) if not unicodedata.combining(ch))
    s = s.lower()
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    return re.sub(r"\s+", " ", s).strip()

def tokenize_name(s: object) -> list[str]:
    t = normalize_text(s)
    return [x for x in t.split(" ") if x]

def parse_reported_by(reported_by: object) -> tuple[list[str], list[str], list[str]]:
    raw = "" if pd.isna(reported_by) else str(reported_by).strip()
    if not raw:
        return [], [], []

    # Expected: "Last, First Middle"
    if "," not in raw:
        toks = tokenize_name(raw)
        if len(toks) >= 2:
            return toks[:-1], [toks[-1]], [toks[-1]]
        return toks, [], []

    last_part, first_part = [x.strip() for x in raw.split(",", 1)]
    last_tokens = tokenize_name(last_part)
    first_tokens = tokenize_name(first_part)
    return first_tokens, last_tokens, last_tokens[:]  # mandatory = all last tokens
                      
def is_valid_email(email: object) -> bool:
    if pd.isna(email):
        return False
    return bool(EMAIL_RE.match(str(email).strip()))

def match_turnback_to_users(
    turnback_name: object,
    users_employee_tokens_list: list[list[str]],
    users_employee_raw_list: list[str],
) -> tuple[str, list[int], dict]:
    first_tokens, last_tokens, last_mandatory = parse_reported_by(turnback_name)

    debug = {
        "_parsed_first_tokens": " ".join(first_tokens),
        "_parsed_last_tokens": " ".join(last_tokens),
        "_parsed_last_mandatory": " ".join(last_mandatory),
        "_match_reason": "",
    }

    if (not first_tokens) and (not last_mandatory):
        debug["_match_reason"] = "Missing or unparseable Reported By"
        return "INVALID", [], debug

    # 1) candidates by last name (ALL tokens)
    last_candidates = []
    for i, emp_tokens in enumerate(users_employee_tokens_list):
        if all(t in set(emp_tokens) for t in last_mandatory):
            last_candidates.append(i)

    if not last_candidates:
        debug["_match_reason"] = "No Employee contains ALL last-name tokens"
        return "UNMATCHED", [], debug

    # 2) require at least one first token
    one_first = []
    if first_tokens:
        for i in last_candidates:
            emp_set = set(users_employee_tokens_list[i])
            if any(t in emp_set for t in first_tokens):
                one_first.append(i)
    else:
        one_first = last_candidates

    if not one_first:
        debug["_match_reason"] = f"Last name matched ({len(last_candidates)}), but none contain any first-name token"
        return "UNMATCHED", [], debug

    if len(one_first) == 1:
        debug["_match_reason"] = "Unique match"
        return "MATCHED", one_first, debug

    # 3) tie-breaker: require ALL first tokens
    all_first = []
    for i in one_first:
        emp_set = set(users_employee_tokens_list[i])
        if all(t in emp_set for t in first_tokens):
            all_first.append(i)

    if len(all_first) == 1:
        debug["_match_reason"] = "Resolved ambiguity by requiring ALL first-name tokens"
        return "MATCHED", all_first, debug

    if not all_first:
        debug["_match_reason"] = (
            f"Ambiguous on last name ({len(one_first)} candidates), "
            "but none contain ALL first-name tokens"
        )
        return "UNMATCHED", [], debug

    debug["_match_reason"] = f"Multiple possible matches ({len(all_first)}) even after ALL first-name tokens"
    return "AMBIGUOUS", all_first, debug

def compute_turnbacks_per_user(df_users: pd.DataFrame, df_turnbacks: pd.DataFrame) -> pd.DataFrame:
    users_raw = df_users[USERS_EMPLOYEE_COL].fillna("").astype(str).tolist()
    users_tokens = [tokenize_name(x) for x in users_raw]

    assigned = []
    for _, row in df_turnbacks.iterrows():
        st, matches, _ = match_turnback_to_users(row.get(TURNBACK_REPORTED_BY_COL, ""), users_tokens, users_raw)
        if st == "MATCHED" and len(matches) == 1:
            assigned.append(df_users.iloc[matches[0]][USERS_EMPLOYEE_COL])
        else:
            assigned.append(None)

    matched_only = pd.Series(assigned).dropna()
    counts = matched_only.value_counts().rename_axis(USERS_EMPLOYEE_COL).reset_index(name="turnbacks_completed")

    per_user = df_users[[USERS_EMPLOYEE_COL, USERS_EMAIL_COL]].copy()
    per_user[USERS_EMPLOYEE_COL] = per_user[USERS_EMPLOYEE_COL].astype(str).str.strip()
    per_user = per_user[
        per_user[USERS_EMPLOYEE_COL].notna()
        & (per_user[USERS_EMPLOYEE_COL] != "")
        & (per_user[USERS_EMPLOYEE_COL].str.lower() != "nan")
    ].drop_duplicates()

    per_user = per_user.merge(counts, on=USERS_EMPLOYEE_COL, how="left")
    per_user["turnbacks_completed"] = per_user["turnbacks_completed"].fillna(0).astype(int)

    per_user["goal"] = GOAL_TURNBACKS
    per_user["remaining"] = (per_user["goal"] - per_user["turnbacks_completed"]).clip(lower=0).astype(int)
    per_user["met_goal"] = per_user["turnbacks_completed"] >= per_user["goal"]
    per_user["status"] = per_user["met_goal"].map(lambda x: "MET_GOAL" if x else "BEHIND_GOAL")
    return per_user

def first_name(employee_full_name: object) -> str:
    s = str(employee_full_name).strip() if not pd.isna(employee_full_name) else ""
    return s.split()[0] if s else "there"

def build_email_subject(month_name: str, met_goal: bool) -> str:
    return f"Turnback Goal Achieved - {month_name}" if met_goal else f"Turnback Progress Update - {month_name}"

def build_email_body(employee_name: object, completed: int, goal: int, now: datetime) -> str:
    month_name = now.strftime("%B")
    current_date = now.strftime("%B %d, %Y")
    name = first_name(employee_name)

    remaining = max(goal - completed, 0)
    met_goal = completed >= goal

    if not met_goal:
        return (
            f"Hello {name},\n\n"
            f"As of {current_date}, you have completed {completed} turnbacks during the month of {month_name}.\n"
            f"You are currently {remaining} turnbacks behind the goal required to be completed by the end of the month.\n\n"
            f"Thank you,\n"
            f"Turnback Notification System\n"
        )

    return (
        f"Hello {name},\n\n"
        f"Congratulations! You have completed your turnback goal for the month of {month_name}.\n"
        f"As of {current_date}, your current turnback total for {month_name} is {completed}.\n\n"
        f"Thank you for your work and commitment.\n\n"
        f"Thank you,\n"
        f"Turnback Notification System\n"
    )

def build_email_outbox(per_user: pd.DataFrame) -> pd.DataFrame:
    now = datetime.now()
    month_name = now.strftime("%B")

    outbox = per_user.copy()
    outbox = outbox[outbox[USERS_EMAIL_COL].notna()]
    outbox = outbox[outbox[USERS_EMAIL_COL].astype(str).str.strip() != ""]
    outbox = outbox[outbox[USERS_EMAIL_COL].astype(str).str.lower() != "nan"]

    outbox["subject"] = outbox["met_goal"].apply(lambda m: build_email_subject(month_name, bool(m)))
    outbox["body"] = outbox.apply(
        lambda r: build_email_body(r[USERS_EMPLOYEE_COL], int(r["turnbacks_completed"]), GOAL_TURNBACKS, now),
        axis=1,
    )
    outbox["current_date"] = now.strftime("%Y-%m-%d")
    outbox["current_month"] = month_name

    cols = [
        USERS_EMPLOYEE_COL, USERS_EMAIL_COL,
        "turnbacks_completed", "goal", "remaining", "met_goal", "status",
        "current_date", "current_month", "subject", "body",
    ]
    return outbox[cols]

def build_mismatch_tables(df_users: pd.DataFrame, df_turnbacks_valid: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Returns (unmatched_df, ambiguous_df) for UI display.
    """
    users_raw = df_users[USERS_EMPLOYEE_COL].fillna("").astype(str).tolist()
    users_tokens = [tokenize_name(x) for x in users_raw]

    rows = []
    for _, row in df_turnbacks_valid.iterrows():
        rb = row.get(TURNBACK_REPORTED_BY_COL, "")
        st, matches, debug = match_turnback_to_users(rb, users_tokens, users_raw)
        rows.append({
            TURNBACK_REPORTED_BY_COL: rb,
            "status": st,
            "matched_employee_count": len(matches),
            "matched_employees_preview": "; ".join(users_raw[i] for i in matches[:5]),
            "_parsed_first_tokens": debug.get("_parsed_first_tokens", ""),
            "_parsed_last_tokens": debug.get("_parsed_last_tokens", ""),
            "_match_reason": debug.get("_match_reason", ""),
        })

    df_results = pd.DataFrame(rows)
    unmatched = df_results[df_results["status"] == "UNMATCHED"].copy()
    ambiguous = df_results[df_results["status"] == "AMBIGUOUS"].copy()
    return unmatched, ambiguous

def get_ambiguous_employee_names(ambiguous_df: pd.DataFrame) -> set[str]:
    skipped = set()

    if ambiguous_df is None or ambiguous_df.empty:
        return skipped

    for _, row in ambiguous_df.iterrows():
        preview = str(row.get("matched_employees_preview", "")).strip()
        if not preview:
            continue

        names = [x.strip() for x in preview.split(";") if x.strip()]
        for name in names:
            skipped.add(name)

    return skipped

def filter_outbox_by_send_rules(outbox_df: pd.DataFrame, history_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    if history_df is None or history_df.empty:
        send_df = outbox_df.copy()
        skip_df = pd.DataFrame(columns=list(outbox_df.columns) + ["skip_reason"])
        return send_df, skip_df

    send_rows = []
    skip_rows = []

    for _, row in outbox_df.iterrows():
        employee = str(row.get(USERS_EMPLOYEE_COL, "")).strip()
        status = str(row.get("status", "")).strip()

        if status == "BEHIND_GOAL":
            send_rows.append(row.to_dict())
            continue

        if status == "MET_GOAL":
            already_sent = history_df[
                (history_df[USERS_EMPLOYEE_COL].astype(str).str.strip() == employee) &
                (history_df["status"].astype(str).str.strip() == "MET_GOAL")
            ]

            if len(already_sent) > 0:
                skipped = row.to_dict()
                skipped["skip_reason"] = "Completion email already sent this month"
                skip_rows.append(skipped)
            else:
                send_rows.append(row.to_dict())
            continue

        send_rows.append(row.to_dict())

    send_df = pd.DataFrame(send_rows) if send_rows else pd.DataFrame(columns=outbox_df.columns)
    skip_df = pd.DataFrame(skip_rows) if skip_rows else pd.DataFrame(columns=list(outbox_df.columns) + ["skip_reason"])
    return send_df, skip_df

def load_monthly_history() -> pd.DataFrame:
    history_file = "monthly_history.csv"
    if os.path.exists(history_file):
        return pd.read_csv(history_file)
    return pd.DataFrame()

def reset_monthly_history():
    history_file = "monthly_history.csv"
    empty_df = pd.DataFrame(columns=[USERS_EMPLOYEE_COL, USERS_EMAIL_COL, "status", "current_month", "current_date"])
    empty_df.to_csv(history_file, index=False, encoding="utf-8-sig")

def update_monthly_history(sent_df: pd.DataFrame):
    history_file = "monthly_history.csv"

    if os.path.exists(history_file):
        history_df = pd.read_csv(history_file)
    else:
        history_df = pd.DataFrame(columns=[USERS_EMPLOYEE_COL, USERS_EMAIL_COL, "status", "current_month", "current_date"])

    if sent_df is None or sent_df.empty:
        history_df.to_csv(history_file, index=False, encoding="utf-8-sig")
        return

    met_goal_sent = sent_df[sent_df["status"] == "MET_GOAL"].copy()
    if met_goal_sent.empty:
        history_df.to_csv(history_file, index=False, encoding="utf-8-sig")
        return

    cols = [c for c in [USERS_EMPLOYEE_COL, USERS_EMAIL_COL, "status", "current_month", "current_date"] if c in met_goal_sent.columns]
    met_goal_sent = met_goal_sent[cols].copy()

    updated = pd.concat([history_df, met_goal_sent], ignore_index=True)
    updated = updated.drop_duplicates(subset=[USERS_EMPLOYEE_COL, "status", "current_month"], keep="first")
    updated.to_csv(history_file, index=False, encoding="utf-8-sig")

def get_successfully_sent_outbox(send_outbox: pd.DataFrame, log_df: pd.DataFrame) -> pd.DataFrame:
    if send_outbox is None or send_outbox.empty:
        return pd.DataFrame(columns=send_outbox.columns if send_outbox is not None else [])

    if log_df is None or log_df.empty:
        return pd.DataFrame(columns=send_outbox.columns)

    sent_log = log_df[log_df["status"] == "SENT"].copy()
    if sent_log.empty:
        return pd.DataFrame(columns=send_outbox.columns)

    sent_log["employee"] = sent_log["employee"].astype(str).str.strip()
    sent_log["to"] = sent_log["to"].astype(str).str.strip()

    sent_rows = send_outbox.copy()
    sent_rows["_employee_key"] = sent_rows[USERS_EMPLOYEE_COL].astype(str).str.strip()
    sent_rows["_email_key"] = sent_rows[USERS_EMAIL_COL].astype(str).str.strip()

    sent_keys = set(zip(sent_log["employee"], sent_log["to"]))

    sent_rows = sent_rows[
        sent_rows.apply(lambda r: (r["_employee_key"], r["_email_key"]) in sent_keys, axis=1)
    ].copy()

    sent_rows = sent_rows.drop(columns=["_employee_key", "_email_key"])
    return sent_rows

#-----------------------------
# Outlook sender 
# -----------------------------
def send_outlook_emails(
    outbox_df: pd.DataFrame,
    send: bool = False,          # False=Drafts, True=Send
    attachment_path: str | None = None,
    delay_seconds: float = 0.2,
    max_retries: int = 8,
    retry_delay: float = 0.6,
    progress_cb=None,            # progress_cb(current, total, message)
) -> pd.DataFrame:
    try:
        import pythoncom
        import win32com.client
        import pywintypes
    except ImportError as e:
        raise ImportError("Missing pywin32. Run: pip install pywin32") from e

    if outbox_df.empty:
        return pd.DataFrame(columns=["employee", "to", "status", "details"])

    if attachment_path:
        attachment_path = os.path.abspath(attachment_path)
        if not os.path.isfile(attachment_path):
            raise FileNotFoundError(f"Attachment not found: {attachment_path}")

    pythoncom.CoInitialize()
    outlook = win32com.client.Dispatch("Outlook.Application")

    total = len(outbox_df)
    logs = []

    for idx, (_, row) in enumerate(outbox_df.iterrows(), start=1):
        employee = str(row.get("Employee", "")).strip()
        to_addr = str(row.get("Email", "")).strip()
        subject = str(row.get("subject", "")).strip()
        body = str(row.get("body", "")).strip()

        if progress_cb:
            progress_cb(idx - 1, total, f"Preparing: {employee}")

        if not employee or employee.lower() == "nan":
            logs.append({"employee": employee, "to": to_addr, "status": "SKIPPED", "details": "Missing Employee"})
            continue
        if not to_addr or to_addr.lower() == "nan":
            logs.append({"employee": employee, "to": to_addr, "status": "SKIPPED", "details": "Missing Email"})
            continue

        attempt = 0
        while True:
            try:
                mail = outlook.CreateItem(0)
                mail.To = to_addr
                mail.Subject = subject
                mail.Body = body

                if attachment_path:
                    mail.Attachments.Add(attachment_path)

                if send:
                    mail.Send()
                    logs.append({"employee": employee, "to": to_addr, "status": "SENT", "details": ""})
                else:
                    mail.Save()
                    logs.append({"employee": employee, "to": to_addr, "status": "DRAFTED", "details": ""})

                if delay_seconds:
                    time.sleep(delay_seconds)
                break

            except pywintypes.com_error as ex:
                attempt += 1
                if attempt > max_retries:
                    logs.append({"employee": employee, "to": to_addr, "status": "ERROR", "details": repr(ex)})
                    break
                time.sleep(retry_delay)

            except Exception as ex:
                logs.append({"employee": employee, "to": to_addr, "status": "ERROR", "details": repr(ex)})
                break

        if progress_cb:
            progress_cb(idx, total, f"Processed: {employee}")

    return pd.DataFrame(logs)
 
# -----------------------------
# GUI
# -----------------------------
class App(tb.Window):
    def __init__(self):
        super().__init__(themename="cosmo")
        self.title("Turnback Notification System")
        self.geometry("1100x700")   

        self.users_path = tb.StringVar(value="")
        self.turnbacks_path = tb.StringVar(value="")
        self.first_run_var = tb.BooleanVar(value=False)

        self._build_ui()
        self._set_send_enabled(False)

    def _build_ui(self):
        top = tb.Frame(self, padding=12)
        top.pack(fill=X)
        label_font = tkfont.Font(size=12, weight="bold")
        entry_font = tkfont.Font(size=12)
        # Make 3 columns: left spacer | center | right spacer

        top.grid_columnconfigure(1, weight=0)
        top.grid_columnconfigure(2, weight=1)

        # Files frame placed in the CENTER column
        files_frame = tb.Labelframe(top, text="Files", padding=20)
        files_frame.grid(row=0, column=1, pady=20)
        # -----------------------------
        # USERS FILE
        # -----------------------------
        tb.Label(
            files_frame,
            text="Users file",
            font=label_font
        ).grid(row=0, column=0, sticky="e", padx=(0, 15), pady=10)

        tb.Entry(
            files_frame,
            textvariable=self.users_path,
            width=45,
            font=entry_font
        ).grid(row=0, column=1, pady=10)

        tb.Button(
            files_frame,
            text="SELECT",
            bootstyle="primary",
            command=self.pick_users,
            width=12
        ).grid(row=0, column=2, padx=(15, 0), pady=10)


        # -----------------------------
        # TURNBACKS FILE
        # -----------------------------
        tb.Label(
            files_frame,
            text="Turnbacks file",
            font=label_font
        ).grid(row=1, column=0, sticky="e", padx=(0, 15), pady=10)

        tb.Entry(
            files_frame,
            textvariable=self.turnbacks_path,
            width=45,
            font=entry_font
        ).grid(row=1, column=1, pady=10)

        tb.Button(
            files_frame,
            text="SELECT",
            bootstyle="primary",
            command=self.pick_turnbacks,
            width=12
        ).grid(row=1, column=2, padx=(15, 0), pady=10)
        tb.Checkbutton(
            files_frame,
            text="First run of the month (reset monthly history)",
            variable=self.first_run_var,
            bootstyle="warning-round-toggle"
        ).grid(row=2, column=1, sticky="w", pady=(10, 0))
        

        send_frame = tb.Frame(top)
        send_frame.grid(row=1, column=1, pady=10)
        self.send_btn = tb.Button(
            send_frame,
            text="SEND EMAILS",
            bootstyle="success",
            width=25,
            command=self.on_send_clicked
        )
        self.send_btn.pack(pady=10)
    

        top.columnconfigure(1, weight=1)

        # Progress
        prog = tb.Frame(self, padding=(12, 0, 12, 12))
        prog.pack(fill=X)

        self.status_lbl = tb.Label(prog, text="Select both files to enable sending.")
        self.status_lbl.pack(anchor=W)

        self.pbar = tb.Progressbar(prog, bootstyle=INFO, mode="determinate")
        self.pbar.pack(fill=X, pady=(6, 0))

        # Results tabs
        body = tb.Frame(self, padding=12)
        body.pack(fill=BOTH, expand=True)

        self.notebook = ttk.Notebook(body)
        self.notebook.pack(fill=BOTH, expand=True)

        self.tab_summary = tb.Frame(self.notebook, padding=10)
        self.tab_unmatched = tb.Frame(self.notebook, padding=10)
        self.tab_ambiguous = tb.Frame(self.notebook, padding=10)
        self.tab_skipped = tb.Frame(self.notebook, padding=10)


        self.notebook.add(self.tab_summary, text="Summary")
        self.notebook.add(self.tab_unmatched, text="Unmatched")
        self.notebook.add(self.tab_ambiguous, text="Ambiguous")
        self.notebook.add(self.tab_skipped, text="Skipped")
        # Summary box
        self.summary_text = tb.Text(self.tab_summary, height=14)
        self.summary_text.pack(fill=X)
        self.summary_text.insert("1.0", "Run will show summary here.\n")
        self.summary_text.configure(state="disabled")

        # Tables
        self.unmatched_table = self._make_table(
            parent=self.tab_unmatched,
            columns=[TURNBACK_REPORTED_BY_COL, "_parsed_first_tokens", "_parsed_last_tokens", "_match_reason"],
            headings=["Reported By", "First tokens", "Last tokens", "Reason"],
        )
        self.ambiguous_table = self._make_table(
            parent=self.tab_ambiguous,
            columns=[TURNBACK_REPORTED_BY_COL, "matched_employee_count", "matched_employees_preview", "_match_reason"],
            headings=["Reported By", "Count", "Candidates preview", "Reason"],  
        )
        self.skipped_table = self._make_table(
            parent=self.tab_skipped,
            columns=[USERS_EMPLOYEE_COL, "status", "skip_reason"],
            headings=["Employee", "Status", "Skip reason"],
        )

    def _make_table(self, parent, columns, headings):
        frame = tb.Frame(parent)
        frame.pack(fill=BOTH, expand=True)

        tree = ttk.Treeview(frame, columns=columns, show="headings")
        for col, head in zip(columns, headings):
            tree.heading(col, text=head)
            tree.column(col, width=200, anchor=W)
        tree.pack(side=LEFT, fill=BOTH, expand=True)
   
        yscroll = ttk.Scrollbar(frame, orient=VERTICAL, command=tree.yview)
        yscroll.pack(side=RIGHT, fill=Y)
        tree.configure(yscrollcommand=yscroll.set)

        return tree

    def _set_send_enabled(self, enabled: bool):
        self.send_btn.configure(state=("normal" if enabled else "disabled"))

    def pick_users(self):
        path = filedialog.askopenfilename(
            title="Select Users file",
            filetypes=[("Excel/CSV", "*.xlsx *.xls *.csv"), ("All files", "*.*")]
        )
        if path:
            self.users_path.set(path)
        self._sync_send_enabled()

    def pick_turnbacks(self):
        path = filedialog.askopenfilename(
            title="Select Turnbacks file",
            filetypes=[("Excel/CSV", "*.xlsx *.xls *.csv"), ("All files", "*.*")]
        )
        if path:
            self.turnbacks_path.set(path)
        self._sync_send_enabled()

    def _sync_send_enabled(self):
        ok = bool(self.users_path.get().strip()) and bool(self.turnbacks_path.get().strip())
        self._set_send_enabled(ok)
        if ok:
            self._set_status("Ready. Click “Send Emails”.", 0, 1)
        else:
            self._set_status("Select both files to enable sending.", 0, 1)

    def _set_status(self, text: str, current: int, total: int):
        self.status_lbl.configure(text=text)
        if total <= 0:
            total = 1
        self.pbar.configure(maximum=total, value=current)
        self.update_idletasks()

    def _clear_table(self, tree: ttk.Treeview):
        for item in tree.get_children():
            tree.delete(item)

    def _fill_table(self, tree: ttk.Treeview, df: pd.DataFrame, cols: list[str], limit: int = 2000):
        self._clear_table(tree)
        if df is None or df.empty:
            return
        df2 = df[cols].copy()
        if len(df2) > limit:
            df2 = df2.head(limit)
        for _, r in df2.iterrows():
            tree.insert("", "end", values=[str(r.get(c, "")) for c in cols])

    def _set_summary(self, text: str):
        self.summary_text.configure(state="normal")
        self.summary_text.delete("1.0", "end")
        self.summary_text.insert("1.0", text)
        self.summary_text.configure(state="disabled")

    def on_send_clicked(self):
        users = self.users_path.get().strip()
        turnbacks = self.turnbacks_path.get().strip()
        if not users or not turnbacks:
            messagebox.showwarning("Missing files", "Please select both Users and Turnbacks files.")
            return


        if messagebox.askyesno("Confirm SEND", "This will SEND emails. Continue?") is False:
            return
        
        self._set_send_enabled(False)
        self._set_status("Starting...", 0, 1)
        self._clear_table(self.unmatched_table)
        self._clear_table(self.ambiguous_table)
        self._clear_table(self.skipped_table)
        self._set_summary("Running...\n")

        t = threading.Thread(target=self._run_pipeline_thread, daemon=True)
        t.start()
    
    def _run_pipeline_thread(self):
        try:

            # Step 1: load
            self.after(0, lambda: self._set_status("Loading files...", 0, 100))
            df_users = load_data(self.users_path.get().strip())
            df_turnbacks = load_data(self.turnbacks_path.get().strip())

            # Basic column checks
            for col in (TURNBACK_REPORTED_DATE_COL, TURNBACK_TYPE_COL, TURNBACK_REPORTED_BY_COL):
                if col not in df_turnbacks.columns:
                    raise ValueError(f"Turnbacks file missing required column: '{col}'")
            for col in (USERS_EMPLOYEE_COL, USERS_EMAIL_COL):
                if col not in df_users.columns:
                    raise ValueError(f"Users file missing required column: '{col}'")

            # Step 2: filter
            self.after(0, lambda: self._set_status("Filtering turnbacks (current month + Type=Turnback)...", 10, 100))
            df_turnbacks_valid, _ = filter_turnbacks_current_month_and_type(df_turnbacks)

            # Step 3: compute per-user
            self.after(0, lambda: self._set_status("Computing turnbacks per user...", 20, 100))
            per_user = compute_turnbacks_per_user(df_users, df_turnbacks_valid)

            # Step 4: mismatches tables
            self.after(0, lambda: self._set_status("Building mismatch tables...", 30, 100))
            unmatched_df, ambiguous_df = build_mismatch_tables(df_users, df_turnbacks_valid)

            unmatched_count = 0 if unmatched_df is None else len(unmatched_df)
            ambiguous_count = 0 if ambiguous_df is None else len(ambiguous_df)

            self.after(0, lambda: self._fill_table(
                self.unmatched_table,
                unmatched_df,
                [TURNBACK_REPORTED_BY_COL, "_parsed_first_tokens", "_parsed_last_tokens", "_match_reason"],
            ))
            self.after(0, lambda: self._fill_table(
                self.ambiguous_table,
                ambiguous_df,
                [TURNBACK_REPORTED_BY_COL, "matched_employee_count", "matched_employees_preview", "_match_reason"],
            ))

            # Step 5: build outbox
            self.after(0, lambda: self._set_status("Building email outbox...", 40, 100))
            outbox = build_email_outbox(per_user)

            # Skip ambiguous users
            ambiguous_employees = get_ambiguous_employee_names(ambiguous_df)
            if ambiguous_employees:
                outbox = outbox[~outbox[USERS_EMPLOYEE_COL].isin(ambiguous_employees)].copy()

            # First run of month: reset history
            if self.first_run_var.get():
                reset_monthly_history()

            history_df = load_monthly_history()

            # Apply anti-spam rules
            send_outbox, skipped_history_df = filter_outbox_by_send_rules(outbox, history_df)

            self.after(0, lambda: self._fill_table(
                self.skipped_table,
                skipped_history_df,
                [USERS_EMPLOYEE_COL, "status", "skip_reason"],
            ))

            # Step 7: send via Outlook
            def progress_cb(cur, total, msg):
                base = 50
                span = 50
                value = base + int(span * (cur / max(total, 1)))
                self.after(0, lambda: self._set_status(msg, value, 100))

            self.after(0, lambda: self._set_status("Sending via Classic Outlook...", 50, 100))
            log_df=send_outlook_emails(
                outbox_df=send_outbox,
                send=True,
                attachment_path=None,
                delay_seconds=0.2,
                progress_cb=progress_cb,
            )
            successful_sent_outbox = get_successfully_sent_outbox(send_outbox, log_df)
            update_monthly_history(successful_sent_outbox)
            sent_count = 0 if log_df is None or log_df.empty else int((log_df["status"] == "SENT").sum())
            error_count = 0 if log_df is None or log_df.empty else int((log_df["status"] == "ERROR").sum())
            skipped_send_count = 0 if log_df is None or log_df.empty else int((log_df["status"] == "SKIPPED").sum())
            summary_text = (
            f"Valid turnbacks: {len(df_turnbacks_valid)}\n"
            f"Unmatched entries: {unmatched_count}\n"
            f"Ambiguous entries: {ambiguous_count}\n"
            f"Employees skipped due to ambiguity: {len(ambiguous_employees)}\n"
            f"Users skipped by monthly history: {len(skipped_history_df)}\n"
            f"Emails attempted: {len(send_outbox)}\n"
            f"Emails actually sent: {sent_count}\n"
            f"Send errors: {error_count}\n"
            f"Skipped during send: {skipped_send_count}\n"  
        )

            self.after(0, lambda: self._set_summary(summary_text))
            self.after(0, lambda: self._set_status("Done.", 100, 100))
            self.after(0, lambda: self._set_send_enabled(True))
            self.after(0, lambda: self.notebook.select(self.tab_summary))

        except Exception as e:
            self.after(0, lambda: self._set_status("Error.", 0, 1))
            self.after(0, lambda: self._set_send_enabled(True))
            self.after(0, lambda: messagebox.showerror("Run failed", str(e)))
     

if __name__ == "__main__":
    app = App()
    app.mainloop()

