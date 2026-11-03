'''
This code receives a ETON ALERT REPORT pdf file as an input and extract the relevant 
information like: jobname, email, quote#, line#, quantity, status, material no., material entered, 
catalog#, and distributor text. Groups the line# material entered (part number ETO) and 
the catalog# (part number standard) according to the tumbling. Outputs an object that contains all 
the extracted info, an object including only the jobname and email (since they appear only once),
and another object with the grouped part and line numbers.
'''
import re
from collections import defaultdict

JOBNAME_X = (25, 205)
EMAIL_X = (319, 500)
QUOTE_X = (20, 70)
LINE_X  = (70, 120)
QTY_X   = (115, 170)
STATUS_X = (140, 300)
MATNO_X = (25, 40)
MAT_X = (110, 210)
CATALOG_X = (213, 291)
DIST_X = (477, 580)
BLANKET_X=(350,450)
LINE_Y_TOL = 3.0

RE_QUOTE = re.compile(r"^\d{8}$")
RE_LINE  = re.compile(r"^\d{6}$")
RE_QTY   = re.compile(r"^\d+\.\d+$")
RE_MAT   = re.compile(r"^[A-Z0-9\-]{10,}$")
RE_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
RE_TUMBLING_5 = re.compile(r"^\d{5}$")
RE_LAST_5_DIGITS = re.compile(r"(\d{5})(?!.*\d)")

def _tonnage_from_catalog(catalog: str):
    c = (catalog or "").strip().upper()
    if len(c) < 8:
        return None
    t = c[6:8]  
    t = t.strip()
    return t if len(t) == 2 else None

def _tumbling_from_material(material: str, mat_no: str = ""):
    material = (material or "").strip().upper()
    if len(material) < 9:
        return None

    m = (mat_no or "").strip().upper()

    # ================= AHU =================
    if m in ("39L", "39M"):

        tail = material[8:]

        match = re.search(r"\d{5}", tail)
        if not match:
            return None

        tumbling = match.group(0)

        if not RE_TUMBLING_5.match(tumbling):
            return None

        return tumbling

    # ================= ART / SMRT =================
    match = RE_LAST_5_DIGITS.search(material)
    if not match:
        return None

    tumbling = match.group(1)

    if not RE_TUMBLING_5.match(tumbling):
        return None

    return tumbling

def _add_item_to_grouped(grouped, seen_entries, item):
    """
    Stores material+catalog+line per tumbling.
    Also stores dist_text per tumbling with truncation-aware dedupe:
      - If new text is substring of an existing -> ignore
      - If new text is a superstring of an existing -> replace existing
      - Otherwise keep as new unique comment
    """
    material = item.get("material_entered") or ""
    catalog = item.get("catalog") or ""
    line_no = item.get("line") or ""
    dist_text = _clean(item.get("dist_text") or "")

    mat_no = item.get("mat_no") or ""
    tumbling = _tumbling_from_material(material, mat_no)

    if not tumbling:
        return

    # ---- entries ----
    key = (material, catalog, line_no)
    if key not in seen_entries[tumbling]:
        seen_entries[tumbling].add(key)
        grouped[tumbling]["entries"].append({
            "material": material,
            "catalog": catalog,
            "line": line_no,
            "tonnage": _tonnage_from_catalog(catalog)
        })

    # ---- dist_texts (truncation-aware) ----
    if dist_text:
        existing = grouped[tumbling].get("dist_texts", [])
        if "dist_texts" not in grouped[tumbling]:
            grouped[tumbling]["dist_texts"] = existing

        # 1) If new is already covered by an existing longer text -> ignore
        for e in existing:
            if dist_text in e:
                return

        # 2) If new is longer and contains any existing shorter ones -> remove those
        kept = []
        replaced_any = False
        for e in existing:
            if e in dist_text:
                replaced_any = True
                continue
            kept.append(e)

        if replaced_any:
            kept.append(dist_text)
            grouped[tumbling]["dist_texts"] = kept
            return

        # 3) Otherwise it's genuinely different -> add
        grouped[tumbling]["dist_texts"].append(dist_text)

def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").replace("\n", " ")).strip()

def _in_range(x: float, rng):
    return rng[0] <= x <= rng[1]

def _group_words_into_lines(words):
    lines = defaultdict(list)
    for w in words:
        y_key = round(float(w["top"]) / LINE_Y_TOL) * LINE_Y_TOL
        lines[y_key].append(w)

    out = []
    for y in sorted(lines.keys()):
        lw = lines[y]
        lw.sort(key=lambda ww: float(ww["x0"]))
        out.append(lw)
    return out

def extract_header_info(pdf):
    jobname = None
    email = None

    for page in pdf.pages:
        words = page.extract_words()
        if not words:
            continue

        words = [w for w in words if float(w["top"]) > 400]
        for lw in _group_words_into_lines(words):
            job_words = [w["text"] for w in lw if _in_range(float(w["x0"]), JOBNAME_X)]
            email_words = [w["text"] for w in lw if _in_range(float(w["x0"]), EMAIL_X)]

            if job_words and not jobname:
                jobname = _clean(" ".join(job_words))

            if email_words and not email:
                email = next((t for t in email_words if RE_EMAIL.match(t)), None)

            if jobname and email:
                return {"jobname": jobname, "email": email}

    return {"jobname": jobname, "email": email}

def collect_items(pdf):
    items = []
    current_item = None
    current_status = None

    grouped = defaultdict(lambda: {"entries": [], "dist_texts":[]})
    seen_entries = defaultdict(set)

    def finalize_current_item():
        nonlocal current_item
        if current_item is None:
            return

        current_item["dist_text"] = _clean(" ".join(current_item["dist_text_lines"]))
        del current_item["dist_text_lines"]
        items.append(current_item)

        _add_item_to_grouped(grouped, seen_entries, current_item)

        current_item = None

    for page_num, page in enumerate(pdf.pages, start=1):
        words = page.extract_words()
        if not words:
            continue
        words = [w for w in words if float(w.get("top", 0)) > 60]
        for lw in _group_words_into_lines(words):
            status_words = [w["text"] for w in lw if _in_range(float(w["x0"]), STATUS_X)]
            tokens = [w["text"] for w in lw]
            line_text = _clean(" ".join(tokens))

            if _is_header_line(line_text):
                continue

            if status_words and "QC" in status_words:
                current_status = _clean(" ".join(status_words))

            quote_candidates = [w["text"] for w in lw if _in_range(float(w["x0"]), QUOTE_X)]
            line_candidates  = [w["text"] for w in lw if _in_range(float(w["x0"]), LINE_X)]
            qty_candidates   = [w["text"] for w in lw if _in_range(float(w["x0"]), QTY_X)]

            quote = next((t for t in quote_candidates if RE_QUOTE.match(t)), None)
            line_no = next((t for t in line_candidates if RE_LINE.match(t)), None)
            qty = next((t for t in qty_candidates if RE_QTY.match(t)), None)

            # New line item begins
            if quote is not None and line_no is not None:
                finalize_current_item()

                current_item = {
                    "page_start": page_num,
                    "status": current_status,
                    "quote": quote,
                    "line": line_no,
                    "quantity": qty,
                    "material_entered": None,
                    "catalog": None,
                    "mat_no": None,
                    "blanket_control": None,      
                    "dist_text_lines": [],
                }

                continue

            if current_item is None:
                continue

            if current_item["mat_no"] is None:
                matno_candidates = [w["text"] for w in lw if _in_range(float(w["x0"]), MATNO_X)]
                matno = next((t for t in matno_candidates if t), None)
                if matno:
                    current_item["mat_no"] = matno

            if current_item["material_entered"] is None:
                mat_candidates = [w["text"] for w in lw if _in_range(float(w["x0"]), MAT_X)]
                mat = next((t for t in mat_candidates if RE_MAT.match(t)), None)
                if mat:
                    current_item["material_entered"] = mat

            if current_item["catalog"] is None:
                cat_candidates = [w["text"] for w in lw if _in_range(float(w["x0"]), CATALOG_X)]
                cat = next((t for t in cat_candidates if RE_MAT.match(t)), None)
                if cat:
                    current_item["catalog"] = cat

            if current_item["blanket_control"] is None:
                blanket_words = [w["text"] for w in lw if _in_range(float(w["x0"]), BLANKET_X)]
                blanket_text = _clean(" ".join(blanket_words))
                if blanket_text:
                    current_item["blanket_control"] = blanket_text


            dist_words = [w for w in lw if _in_range(float(w["x0"]), DIST_X)]
            if dist_words:
                dist_words.sort(key=lambda ww: float(ww["x0"]))
                dist_line = _clean(" ".join(w["text"] for w in dist_words))
                if dist_line:
                    current_item["dist_text_lines"].append(dist_line)

    finalize_current_item()

    return items, dict(grouped)

def extract_tumbling(items):
    unique_items = []
    seen = set()
    for it in items:
        material = it.get("material_entered") or ""
        tumbling = _tumbling_from_material(material, it.get("mat_no") or "")
        if not tumbling:
            continue

        if tumbling in seen:
            continue
        seen.add(tumbling)

        new_it = dict(it)
        new_it["tumbling"] = tumbling
        unique_items.append(new_it)

    return unique_items

def _is_header_line(line_text: str) -> bool:
    t = (line_text or "").strip()
    if not t:
        return True
    header_prefixes = (
        "Company:",
        "Program:",
        "User ID:",
        "System:",
        "Date/Time:",
        "Page:",
    )

    if any(p in t for p in header_prefixes):
        return True

    if t == "ETO Alert Report":
        return True

    return False

def get_odometer(model, matNo):
    if matNo=="39M":
        if isinstance(model, str) and len(model) == 18:
            if model[-3:] == 'XXE':
                result = model[3] + model[-1] + model[7] + model[8:13] + '.XML'
            else:
                result = model[3] + model[-1] + model[7:13] + '.XML'
            return result
    return None


