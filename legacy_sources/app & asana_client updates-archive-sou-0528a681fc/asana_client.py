'''
This code uses the list of  dictionaries that was obtained from
the pdf extraction file and uses each data to create a task in
Asana through the API, it assigns each data to each corresponding 
field and also generates the description/notes with: the jobname,
email, ETO and Standard part numbers, and line numbers

'''
import os
import time
import requests
from datetime import datetime, date, timedelta
import time
from zoneinfo import ZoneInfo
from pdf_extraction import get_odometer


ASANA_BASE_URL = "https://app.asana.com/api/1.0"

AHU_SET = {"39L","39M"}

ART_SET = {"40R","48A","48K","48V","50A","50K","50P","50V","50X"}

SMRT_SET = { "38AU","38AX","48FC","48FE","48GC","48GE","48JC","48LC","50FC","50FE","50GC","50GE","50JC","50LC","50WE","547K","559K","559L","581K","581L","582K","582L"}

HOLIDAYS_DDMM = {
    (1, 1),    
    (2, 2),   
    (16, 3),   
    (1, 5),   
    (16, 9),   
    (12, 10), 
    (2, 11),   
    (16, 11),  
    (20, 11),  
    (12, 12),  
    (24, 12),  
    (25, 12),  
}
LOCAL_TZ = ZoneInfo("America/Monterrey")
SHIFT_CUTOFF = time(15, 30)  


def week_number_from_date(d):
    return d.isocalendar().week

def is_weekend(d: date) -> bool:
    return d.weekday() >= 5  # 5=Sat, 6=Sun

def is_holiday(d: date) -> bool:
    return (d.day, d.month) in HOLIDAYS_DDMM

def next_workday(d: date) -> date:
    """Move forward until it's not weekend and not holiday."""
    while is_weekend(d) or is_holiday(d):
        d += timedelta(days=1)
    return d

def compute_date_in(now: datetime) -> date:
    """
    now: timezone-aware datetime in local plant timezone.
    Rules:
      - if time > 15:30 => start from next day
      - then push forward to next workday if weekend/holiday
    """
    base = now.date()

    if now.time() > SHIFT_CUTOFF:
        base = base + timedelta(days=1)

    return next_workday(base)

def asana_date_string(d: date) -> str:
    """Asana date custom fields accept YYYY-MM-DD."""
    return d.isoformat()

def product_from_matno(mat_no: str):
    m = (mat_no or "").strip().upper()
    for code in AHU_SET:
        if code in m:
            return "AHU"
    for code in ART_SET:
        if code in m:
            return "ART"
    for code in SMRT_SET:
        if code in m:
            return "SMRT"

    return None

def base_matno(mat_no: str) -> str:

    m = (mat_no or "").strip().upper()
    if  "_" in m:
        m = m.split("_", 1)[0].strip()
    return m

def tonnage_to_int(tonnage):
    if tonnage is None:
        return None

    s = str(tonnage).strip()
    if not s:
        return None
    try:
        f = float(s)
        return int(f) 
    except:
        pass

    if s.isdigit():
        n = int(s)
        if len(s) >= 2 and s.endswith("5"):
            return int(n / 10)
        return n

    return None

def pick_smrt_plant_from_matno_and_tonnage(mat_no: str, tonnage_int: int):
    m = base_matno(mat_no)
    t = tonnage_int
    if not m or t is None:
        return None

    if m == "40RLA":
        return "CMX-B" if t in {6, 7, 10, 12, 15, 20, 25, 28} else None
    if m == "40RLS":
        return "CMX-B" if t in {7, 8, 10, 12, 15, 20, 25, 28} else None
    if m == "40RLQ":
        return "CMX-B" if t in {6, 7, 10, 15, 20, 25} else None

    if m == "38AXZ":
        if t in {6, 7, 10, 12}:
            return "CMX-C"
        if t in {15, 20}:
            return "CMX-D"
        return None

    if m == "38AXD":
        if t in {10, 12}:
            return "CMX-C"
        if t in {15, 20, 25}:
            return "CMX-D"
        return None

    if m == "38AXQ":
        if t in {6, 7, 10}:
            return "CMX-C"
        if t in {15, 20}:
            return "CMX-D"
        return None

    if m in {"48FE", "50FE"}:
        if t in {3, 4, 5, 6}:
            return "CMX-C"
        if 7<=t<=28:
            return "CMX-D"
        return None

    if m in {"48GE", "50GE"}:
        if t in {3, 4, 5}:
            return "CMX-C"
        if t in {6, 7, 8, 10, 12, 15, 17, 20, 25}:
            return "CMX-D"
        return None

    if m == "50FEQ":
        if t in {3, 4, 5, 6}:
            return "CMX-C"
        if t in {7, 8, 10, 12, 15, 20, 25}:
            return "CMX-D"
        return None

    if m == "50GEQ":
        if t in {3, 4, 5}:
            return "CMX-C"
        if t in {6, 7, 8, 10, 15, 20, 25}:
            return "CMX-D"
        return None

    if m == "48QE":
        if t in {3, 4, 5}:
            return "CMX-C"
        if t in {6, 7, 8, 10, 15, 20, 25}:
            return "CMX-D"
        return None

    if m in {"48WE", "50WE"}:
        if t in {6, 7, 10, 15}:
            return "CMX-D"
        return None

    return None

def get_group_tonnage_int(grouped, tumbling: str):
    g = grouped.get(tumbling, {})
    entries = g.get("entries", []) or []
    for e in entries:
        t = tonnage_to_int(e.get("tonnage"))
        if t is not None:
            return t
    return None

def get_project_custom_field_settings(token: str, project_gid: str):
    url = f"{ASANA_BASE_URL}/projects/{project_gid}/custom_field_settings"
    headers = {"Authorization": f"Bearer {token}"}
    params = {
        "opt_fields": "custom_field.gid,custom_field.name,custom_field.type,custom_field.enum_options.gid,custom_field.enum_options.name"
    }

    r = requests.get(url, headers=headers, params=params)
    r.raise_for_status()
    return r.json()["data"]

def build_custom_fields_by_name(project_cfs, item, grouped, ahu_user_gid, rooftop_user_gid, header_info):
    tumbling = item.get("tumbling") or ""
    g = grouped.get(tumbling, {})
    dist_texts = g.get("dist_texts", [])
    od=get_odometer(item.get("catalog"), item.get("mat_no"))
    if len(dist_texts) == 1:
        dist_text_value = dist_texts[0]
    elif len(dist_texts) > 1:
        dist_text_value = " | ".join(dist_texts)
    else:
        dist_text_value = ""

    wanted_product = product_from_matno(item.get("mat_no"))
    blanket_control = item.get("blanket_control")

    if wanted_product in ("ART", "SMRT"):
        if not dist_text_value and blanket_control:
            dist_text_value = "Blanket Quote"

    if wanted_product == "AHU":
        assignee_gid = ahu_user_gid
    else:
        assignee_gid = rooftop_user_gid
    plant_value = None

    if wanted_product in ("AHU", "ART"):
        plant_value = "CMX-B"

    elif wanted_product == "SMRT":
        t_int = get_group_tonnage_int(grouped, tumbling)
        plant_value = pick_smrt_plant_from_matno_and_tonnage(item.get("mat_no"), t_int)


    mapping = {
        "Contract": item.get("quote"),
        "Qty": item.get("quantity"),
        "Distributor Comments": dist_text_value,
        "Job Name": header_info.get("jobname"),
        "Customer Email": header_info.get("email"),
        "Odometer": od
    }

    payload = {}

    for cf_setting in project_cfs:
        cf = cf_setting["custom_field"]
        cf_gid = str(cf["gid"])
        cf_name = (cf.get("name") or "").strip()
        cf_type = cf.get("type")

        # ---- Product multi-select ----
        if cf_name == "Product" and wanted_product:
            enum_options = cf.get("enum_options") or []
            option_gid = None
            for opt in enum_options:
                if (opt.get("name") or "").strip().upper() == wanted_product:
                    option_gid = str(opt.get("gid"))
                    break

            if option_gid:
                payload[cf_gid] = option_gid
            continue

        # ---- Task Progress single-select (default = Not Started) ----
        if cf_name == "Task Progress":
            enum_options = cf.get("enum_options") or []
            option_gid = None
            for opt in enum_options:
                if (opt.get("name") or "").strip().lower() == "not started":
                    option_gid = str(opt.get("gid"))
                    break

            if option_gid:
                payload[cf_gid] = option_gid  # single-select expects single gid
            continue

        # ---- Plant multi-select ----
        if cf_name == "Plant":
            if plant_value:
                enum_options = cf.get("enum_options") or []
                option_gid = None
                for opt in enum_options:
                    if (opt.get("name") or "").strip().upper() == plant_value:
                        option_gid = str(opt.get("gid"))
                        break

                if option_gid:
                    payload[cf_gid] = [option_gid]  # multi-select expects list
            continue
        # ---- Date in ----
        if cf_name == "Date in":
            now_local = datetime.now(LOCAL_TZ)
            date_in = compute_date_in(now_local)  
            payload[cf_gid] = {"date": date_in.isoformat()}
            continue

        if cf_name == "Week Number":
            now_local = datetime.now(LOCAL_TZ)
            date_in = compute_date_in(now_local)
            wk = week_number_from_date(date_in)

            label = f"Week {wk:02d}"   

            enum_options = cf.get("enum_options") or []
            option_gid = None
            for opt in enum_options:
                if (opt.get("name") or "").strip() == label:
                    option_gid = str(opt.get("gid"))
                    break

            if option_gid:
                payload[cf_gid] = option_gid  
            else:
                pass

            continue




        # ---- Existing fields ----
        value = mapping.get(cf_name)
        if value is None:
            continue

        if cf_type == "number":
            try:
                payload[cf_gid] = float(value)
            except:
                continue
        else:
            payload[cf_gid] = str(value)

    return payload, assignee_gid

def asana_request(method, url, token, json_body=None, retries=5):
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    for attempt in range(retries):
        r = requests.request(method, url, headers=headers, json=json_body)

        if r.status_code == 429:
            wait = int(r.headers.get("Retry-After", "2"))
            time.sleep(wait)
            continue

        if r.status_code in (500, 502, 503, 504):
            time.sleep(2 ** attempt)

            continue

        return r

    return r

def create_task_with_custom_fields(token: str, project_gid: str, name: str, custom_fields: dict, notes: str = "", assignee_gid: str = None):
    url = f"{ASANA_BASE_URL}/tasks"

    data = {
        "name": name,
        "notes": notes,
        "projects": [project_gid],
        "custom_fields": custom_fields,
    }

    if assignee_gid:
        data["assignee"] = assignee_gid  

    body = {"data": data}

    r = asana_request("POST", url, token, json_body=body)
    if not r.ok:
        raise RuntimeError(f"Failed to create task: {r.status_code} {r.text}")

    return r.json()["data"]

def build_notes_with_parts(item, grouped):
    tumbling = item.get("tumbling") or ""
    g = grouped.get(tumbling, {})
    entries = g.get("entries", [])
    lines = []

    if not entries:
        lines.append("- (no parts found)")
        return "\n".join(lines)

    for e in entries:
        m = (e.get("material") or "").strip()
        c = (e.get("catalog") or "").strip()
        l = (e.get("line") or "").strip()
        lines.append(f"{l[3:]}  | {m}  | {c} " )

    return "\n".join(lines)

def attach_file_to_task(token: str, task_gid: str, file_path: str, retries: int = 5, delay: float = 2.0):
    """
    Attach a file to an Asana task, retrying in case the task was just created
    and is not yet fully recognized by the attachments endpoint.
    """
    url = f"{ASANA_BASE_URL}/attachments"
    headers = {
        "Authorization": f"Bearer {token}"
    }

    last_error = None

    for attempt in range(1, retries + 1):
        try:
            with open(file_path, "rb") as f:
                files = {
                    "file": (file_path.split("\\")[-1], f, "application/pdf")
                }
                data = {
                    "parent": str(task_gid)
                }

                r = requests.post(url, headers=headers, data=data, files=files)

            if r.ok:
                return r.json()["data"]

            last_error = f"{r.status_code} {r.text}"

            # Retry specifically for "not recognized" / just-created timing issues
            if r.status_code in (400, 404):
                time.sleep(delay * attempt)
                continue

            # Retry transient server issues too
            if r.status_code in (429, 500, 502, 503, 504):
                time.sleep(delay * attempt)
                continue

            raise RuntimeError(f"Failed to attach file: {r.status_code} {r.text}")

        except Exception as e:
            last_error = str(e)
            if attempt < retries:
                time.sleep(delay * attempt)
            else:
                raise RuntimeError(f"Failed to attach file after {retries} attempts: {last_error}")

    raise RuntimeError(f"Failed to attach file after {retries} attempts: {last_error}")