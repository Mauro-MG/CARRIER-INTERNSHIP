'''
This code generates a flask API service that automates the 
creation of Asana tasks from PDF documents. It exposes a secure /ingest 
endpoint that accepts raw PDF bytes, saves the file, immediately returns 
a job_id, and processes the PDF/Asana task creation in the background.
'''

import os
import sys
import base64
import time
import json
import uuid
import hashlib
import threading
from datetime import datetime, timezone, timedelta
from pathlib import Path
import logging

from flask import Flask, jsonify, request
from werkzeug.utils import secure_filename
import pdfplumber

from asana_client import (
    get_project_custom_field_settings,
    build_custom_fields_by_name,
    build_notes_with_parts,
    create_task_with_custom_fields,
    attach_file_to_task,
)
from pdf_extraction import collect_items, extract_tumbling, extract_header_info


app = Flask(__name__)

# ============================================================
# Paths / Directories
# ============================================================
_APP_ROOT = Path(__file__).resolve().parent

_upload_env = os.getenv("UPLOAD_DIR")
if _upload_env:
    _p = Path(_upload_env)
    UPLOAD_DIR = _p if _p.is_absolute() else (_APP_ROOT / _p).resolve()
else:
    UPLOAD_DIR = _APP_ROOT / "incoming_pdfs"

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

JOB_DIR = _APP_ROOT / "job_status"
JOB_DIR.mkdir(parents=True, exist_ok=True)
# ============================================================
# CLEAN OLD JOB STATUS FILES (>1 day)
# ============================================================

try:

    now_utc = datetime.now(timezone.utc)

    for job_file in JOB_DIR.glob("*.json"):

        modified_time = datetime.fromtimestamp(
            job_file.stat().st_mtime,
            tz=timezone.utc
        )

        age = now_utc - modified_time

        if age > timedelta(days=1):
            try:
                job_file.unlink()
            except Exception:
                pass

except Exception:
    pass

ALLOWED_EXTENSIONS = {".pdf"}

# ============================================================
# Logging
# ============================================================
LOG_PATH = UPLOAD_DIR / "debug_log.txt"
# ============================================================
# DELETE LOG IF OLDER THAN 1 DAY
# ============================================================

if LOG_PATH.exists():

    modified_time = datetime.fromtimestamp(
        LOG_PATH.stat().st_mtime,
        tz=timezone.utc
    )

    age = datetime.now(timezone.utc) - modified_time

    if age > timedelta(days=1):
        try:
            LOG_PATH.unlink()
        except Exception:
            pass

# ============================================================
# LOGGER SETUP
# ============================================================

logger = logging.getLogger("app_logger")
logger.setLevel(logging.DEBUG)
logger.handlers.clear()

formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")

try:
    file_handler = logging.FileHandler(LOG_PATH, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
except Exception:
    pass

stream_handler = logging.StreamHandler(sys.stderr)
stream_handler.setLevel(logging.DEBUG)
stream_handler.setFormatter(formatter)
logger.addHandler(stream_handler)

logger.propagate = False


def log_debug(msg, *args):
    logger.debug(msg, *args)
    for handler in logger.handlers:
        try:
            handler.flush()
        except Exception:
            pass


def log_exception(msg, *args):
    logger.exception(msg, *args)
    for handler in logger.handlers:
        try:
            handler.flush()
        except Exception:
            pass


# ============================================================
# Config / Env Vars
# ============================================================
API_KEY = os.getenv("API_KEY", "")

ASANA_TOKEN = os.getenv("ASANA_TOKEN", "")
PROJECT_GID = os.getenv("ASANA_PROJECT_GID", "1211531277250279")

AHU_USER_GID = os.getenv("ASANA_AHU_USER_GID", "1211243647054567")
ROOFTOP_USER_GID = os.getenv("ASANA_ROOFTOP_USER_GID", "1211137208483755")


# ============================================================
# Helpers
# ============================================================
def _auth_ok(req) -> bool:
    if not API_KEY:
        return True
    return req.headers.get("X-API-KEY", "") == API_KEY


def _allowed_file(filename: str) -> bool:
    return Path(filename).suffix.lower() in ALLOWED_EXTENSIONS


def cleanup_old_pdfs(folder: Path, days: int = 7) -> dict:
    """
    Deletes .pdf files older than `days` in `folder`.
    Ignores per-file errors and returns a report.
    """
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=days)

    deleted = 0
    kept = 0
    errors = []

    folder = Path(folder)
    if not folder.exists():
        return {
            "ok": True,
            "deleted": 0,
            "kept": 0,
            "errors": [],
            "note": "folder_missing",
        }

    for p in folder.glob("*.pdf"):
        try:
            mtime = datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc)
            if mtime < cutoff:
                p.unlink()
                deleted += 1
            else:
                kept += 1
        except Exception as e:
            errors.append({"file": str(p), "error": str(e)})

    return {
        "ok": len(errors) == 0,
        "deleted": deleted,
        "kept": kept,
        "errors": errors,
    }


def cleanup_old_jobs(folder: Path, days: int = 14) -> dict:
    """
    Deletes old job status .json files.
    """
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=days)

    deleted = 0
    kept = 0
    errors = []

    folder = Path(folder)
    if not folder.exists():
        return {
            "ok": True,
            "deleted": 0,
            "kept": 0,
            "errors": [],
            "note": "folder_missing",
        }

    for p in folder.glob("*.json"):
        try:
            mtime = datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc)
            if mtime < cutoff:
                p.unlink()
                deleted += 1
            else:
                kept += 1
        except Exception as e:
            errors.append({"file": str(p), "error": str(e)})

    return {
        "ok": len(errors) == 0,
        "deleted": deleted,
        "kept": kept,
        "errors": errors,
    }


def _job_file(job_id: str) -> Path:
    return JOB_DIR / f"{job_id}.json"


def _idempotency_file(idempotency_key: str) -> Path:
    safe_hash = hashlib.sha256(idempotency_key.encode("utf-8")).hexdigest()
    return JOB_DIR / f"idempotency_{safe_hash}.json"


def save_job_status(job_id: str, data: dict) -> None:
    data["updated_at"] = datetime.now(timezone.utc).isoformat()
    path = _job_file(job_id)
    path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")


def load_job_status(job_id: str):
    path = _job_file(job_id)
    if not path.exists():
        return None

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def save_idempotency_mapping(idempotency_key: str, job_id: str) -> None:
    path = _idempotency_file(idempotency_key)
    path.write_text(
        json.dumps(
            {
                "idempotency_key": idempotency_key,
                "job_id": job_id,
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def load_idempotency_mapping(idempotency_key: str):
    path = _idempotency_file(idempotency_key)
    if not path.exists():
        return None

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def build_idempotency_key(req, pdf_bytes: bytes, safe_name: str) -> str:
    """
    Best option:
      Power Automate should send X-Idempotency-Key using:
      Message Id + Attachment Id or Internet Message Id + Attachment Name.

    Fallback:
      Use filename + sha256 hash of PDF body.
    """
    header_key = req.headers.get("X-Idempotency-Key")

    if header_key:
        return header_key.strip()

    pdf_hash = hashlib.sha256(pdf_bytes).hexdigest()
    return f"{safe_name}:{pdf_hash}"


# ============================================================
# Background processing
# ============================================================
def process_job(job_id: str, save_path: str, cleanup_report: dict) -> None:
    """
    Runs outside the HTTP request, so API Gateway / Power Automate
    do not wait for PDF extraction or Asana task creation.
    """
    start_ts = time.time()

    log_debug("====================================================")
    log_debug("BACKGROUND JOB STARTED | job_id=%s", job_id)
    log_debug("BACKGROUND STEP 1 - save_path=%s", save_path)

    save_job_status(
        job_id,
        {
            "ok": True,
            "job_id": job_id,
            "status": "processing",
            "step": "pdf_extraction",
            "file_saved": save_path,
            "started_at": datetime.now(timezone.utc).isoformat(),
        },
    )

    # ---------------- PDF Extraction ----------------
    try:
        log_debug("BACKGROUND STEP 2 - opening PDF with pdfplumber | job_id=%s", job_id)

        with pdfplumber.open(str(save_path)) as pdf:
            items_all, grouped = collect_items(pdf)
            header_info = extract_header_info(pdf)

        items_unique = extract_tumbling(items_all)

        log_debug("BACKGROUND STEP 3 - PDF parsed successfully | job_id=%s", job_id)
        log_debug("BACKGROUND Items extracted: %s | job_id=%s", len(items_all), job_id)
        log_debug("BACKGROUND Unique items: %s | job_id=%s", len(items_unique), job_id)
        log_debug("BACKGROUND Header info: %s | job_id=%s", header_info, job_id)

        save_job_status(
            job_id,
            {
                "ok": True,
                "job_id": job_id,
                "status": "processing",
                "step": "asana",
                "file_saved": save_path,
                "header_info": header_info,
                "items_all_count": len(items_all),
                "items_unique_count": len(items_unique),
            },
        )

    except Exception as e:
        log_exception("BACKGROUND ERROR in PDF extraction | job_id=%s", job_id)

        save_job_status(
            job_id,
            {
                "ok": False,
                "job_id": job_id,
                "status": "failed",
                "step": "pdf_extraction",
                "error": f"PDF extraction failed: {e}",
                "file_saved": save_path,
                "finished_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        return

    # ---------------- Asana ----------------
    try:
        log_debug("BACKGROUND STEP 4 - fetching Asana custom field settings | job_id=%s", job_id)

        project_cfs = get_project_custom_field_settings(ASANA_TOKEN, PROJECT_GID)

        log_debug("BACKGROUND STEP 5 - Asana custom field settings fetched | job_id=%s", job_id)

        created = []

        for index, item in enumerate(items_unique, start=1):
            tumbling = item.get("tumbling")

            if not tumbling:
                log_debug(
                    "BACKGROUND STEP 6 - skipping item %s because tumbling is missing | job_id=%s",
                    index,
                    job_id,
                )
                continue

            log_debug(
                "BACKGROUND STEP 6 - building task %s for tumbling %s | job_id=%s",
                index,
                tumbling,
                job_id,
            )

            notes = build_notes_with_parts(item, grouped)
            custom_fields, assignee_ID = build_custom_fields_by_name(
                project_cfs,
                item,
                grouped,
                ahu_user_gid=AHU_USER_GID,
                rooftop_user_gid=ROOFTOP_USER_GID,
                header_info=header_info,
            )

            if not custom_fields:
                log_debug(
                    "BACKGROUND WARNING - custom_fields empty for tumbling %s | job_id=%s",
                    tumbling,
                    job_id,
                )

            log_debug(
                "BACKGROUND STEP 7 - creating Asana task for tumbling %s | job_id=%s",
                tumbling,
                job_id,
            )

            task = create_task_with_custom_fields(
                token=ASANA_TOKEN,
                project_gid=PROJECT_GID,
                name=str(tumbling),
                custom_fields=custom_fields,
                notes=notes,
                assignee_gid=assignee_ID,
            )

            task_gid = str(task.get("gid"))

            log_debug(
                "BACKGROUND STEP 8 - task created for tumbling %s | gid=%s | job_id=%s",
                tumbling,
                task_gid,
                job_id,
            )

            # Small delay helps Asana recognize the newly created task before attachment.
            time.sleep(1.5)

            attachment_gid = None
            attachment_error = None

            try:
                log_debug(
                    "BACKGROUND STEP 9 - attaching PDF to task gid=%s | job_id=%s",
                    task_gid,
                    job_id,
                )

                attach = attach_file_to_task(
                    ASANA_TOKEN,
                    task_gid,
                    str(save_path),
                    retries=5,
                    delay=2.0,
                )

                attachment_gid = attach.get("gid")

                log_debug(
                    "BACKGROUND STEP 10 - attachment uploaded | task_gid=%s | attachment_gid=%s | job_id=%s",
                    task_gid,
                    attachment_gid,
                    job_id,
                )

            except Exception as e:
                attachment_error = str(e)

                log_exception(
                    "BACKGROUND WARNING - attachment failed | task_gid=%s | name=%s | job_id=%s",
                    task_gid,
                    task.get("name"),
                    job_id,
                )

            created.append(
                {
                    "gid": task_gid,
                    "name": task.get("name"),
                    "attachment_gid": attachment_gid,
                    "attachment_error": attachment_error,
                }
            )

            # Save progress after each task.
            save_job_status(
                job_id,
                {
                    "ok": True,
                    "job_id": job_id,
                    "status": "processing",
                    "step": "asana",
                    "file_saved": save_path,
                    "header_info": header_info,
                    "items_all_count": len(items_all),
                    "items_unique_count": len(items_unique),
                    "tasks_created_so_far": created,
                    "current_index": index,
                    "total_unique_items": len(items_unique),
                },
            )

        total_time = round(time.time() - start_ts, 2)

        log_debug("BACKGROUND SUCCESS - tasks created | job_id=%s", job_id)
        log_debug("BACKGROUND Created tasks: %s | job_id=%s", created, job_id)
        log_debug("BACKGROUND TOTAL TIME: %s seconds | job_id=%s", total_time, job_id)

        save_job_status(
            job_id,
            {
                "ok": True,
                "job_id": job_id,
                "status": "completed",
                "step": "done",
                "file_saved": save_path,
                "header_info": header_info,
                "items_all_count": len(items_all),
                "items_unique_count": len(items_unique),
                "tasks_created": created,
                "cleanup": cleanup_report,
                "processing_seconds": total_time,
                "finished_at": datetime.now(timezone.utc).isoformat(),
            },
        )

    except Exception as e:
        log_exception("BACKGROUND ERROR in Asana section | job_id=%s", job_id)

        save_job_status(
            job_id,
            {
                "ok": False,
                "job_id": job_id,
                "status": "failed",
                "step": "asana",
                "error": f"Asana failed: {e}",
                "file_saved": save_path,
                "header_info": header_info,
                "items_all_count": len(items_all),
                "items_unique_count": len(items_unique),
                "finished_at": datetime.now(timezone.utc).isoformat(),
            },
        )


# ============================================================
# Routes
# ============================================================
@app.get("/")
def home():
    base = request.host_url.rstrip("/")
    return jsonify(
        {
            "ok": True,
            "service": "ETO -> Asana automation",
            "base_url": base,
            "next": {
                "endpoint": f"{base}/ingest",
                "method": "POST",
                "content_type": "application/pdf",
                "body": "Raw PDF bytes in request body. Optional headers: X-Filename, X-API-KEY, X-Idempotency-Key",
                "example_curl_windows": (
                    f'curl.exe -X POST "{base}/ingest" '
                    f'-H "Content-Type: application/pdf" '
                    f'-H "X-Filename: test.pdf" '
                    f'-H "X-Idempotency-Key: unique-email-attachment-id" '
                    f'--data-binary "@C:\\\\path\\\\to\\\\file.pdf"'
                ),
                "status_endpoint": f"{base}/ingest/status/<job_id>",
            },
        }
    )


@app.get("/health")
def health():
    return jsonify({"ok": True}), 200


@app.get("/ingest/status/<job_id>")
def ingest_status(job_id: str):
    data = load_job_status(job_id)

    if not data:
        return jsonify(
            {
                "ok": False,
                "error": "Job not found",
                "job_id": job_id,
            }
        ), 404

    return jsonify(data), 200


def _ingest_core():
    start_ts = time.time()

    log_debug("====================================================")
    log_debug("---- NEW INGEST REQUEST ----")
    log_debug("Headers: %s", dict(request.headers))
    log_debug("STEP 1 - request entered")

    if not _auth_ok(request):
        log_debug("STEP 1A - unauthorized")
        return jsonify({"ok": False, "error": "Unauthorized"}), 401

    if not ASANA_TOKEN or not PROJECT_GID:
        log_debug(
            "STEP 1B - missing env vars | ASANA_TOKEN exists: %s | PROJECT_GID exists: %s",
            bool(ASANA_TOKEN),
            bool(PROJECT_GID),
        )

        return jsonify(
            {
                "ok": False,
                "error": "Missing ASANA_TOKEN or ASANA_PROJECT_GID env vars",
            }
        ), 500

    cleanup_report = cleanup_old_pdfs(UPLOAD_DIR, days=7)
    cleanup_jobs_report = cleanup_old_jobs(JOB_DIR, days=14)

    log_debug("STEP 2 - PDF cleanup completed: %s", cleanup_report)
    log_debug("STEP 2A - Job cleanup completed: %s", cleanup_jobs_report)

    content_type = (request.headers.get("Content-Type") or "").lower()
    log_debug("STEP 3 - content type detected: %s", content_type)

    if "application/pdf" not in content_type:
        log_debug("STEP 3A - invalid content type")
        return jsonify(
            {
                "ok": False,
                "error": "Expected Content-Type: application/pdf with raw PDF bytes in request body",
            }
        ), 400

    pdf_bytes = request.get_data()

    log_debug("STEP 4 - request body read")
    log_debug("Body length: %s", len(pdf_bytes))
    log_debug("First 20 bytes: %s", pdf_bytes[:20])

    # Power Automate sometimes sends base64 text instead of raw bytes.
    if pdf_bytes.startswith(b"JVBER") and not pdf_bytes.startswith(b"%PDF"):
        log_debug("STEP 5 - detected base64 PDF, attempting decode")

        try:
            pdf_bytes = base64.b64decode(pdf_bytes, validate=True)
            log_debug("STEP 5A - base64 decoded successfully")

        except Exception as e:
            log_debug("STEP 5B - strict base64 decode failed: %s", e)
            pdf_bytes = base64.b64decode(pdf_bytes)
            log_debug("STEP 5C - fallback base64 decode succeeded")

    if not pdf_bytes:
        log_debug("STEP 6 - empty request body after processing")
        return jsonify({"ok": False, "error": "Empty request body"}), 400

    log_debug("STEP 6 - body validated")
    log_debug("First 10 bytes after decode: %s", pdf_bytes[:10])

    original_name = request.headers.get("X-Filename", "incoming.pdf")
    safe_name = secure_filename(original_name)

    if not _allowed_file(safe_name):
        safe_name = "incoming.pdf"

    # ---------------- Idempotency ----------------
    idempotency_key = build_idempotency_key(request, pdf_bytes, safe_name)
    existing = load_idempotency_mapping(idempotency_key)

    if existing:
        existing_job_id = existing.get("job_id")
        existing_status = load_job_status(existing_job_id) or {}

        log_debug(
            "STEP 7 - duplicate request detected | idempotency_key=%s | existing_job_id=%s",
            idempotency_key,
            existing_job_id,
        )

        return jsonify(
            {
                "ok": True,
                "duplicate": True,
                "message": "Duplicate request detected. Returning existing job instead of creating tasks again.",
                "job_id": existing_job_id,
                "status_endpoint": f"/ingest/status/{existing_job_id}",
                "current_status": existing_status.get("status"),
                "step": existing_status.get("step"),
            }
        ), 202

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    job_id = str(uuid.uuid4())
    save_path = UPLOAD_DIR / f"{stamp}__{job_id}__{safe_name}"

    save_path.write_bytes(pdf_bytes)

    log_debug("STEP 8 - file saved: %s", save_path)
    log_debug("STEP 9 - job_id created: %s", job_id)
    log_debug("STEP 10 - idempotency_key: %s", idempotency_key)

    save_idempotency_mapping(idempotency_key, job_id)

    save_job_status(
        job_id,
        {
            "ok": True,
            "job_id": job_id,
            "status": "queued",
            "step": "accepted",
            "file_saved": str(save_path),
            "idempotency_key": idempotency_key,
            "cleanup": cleanup_report,
            "created_at": datetime.now(timezone.utc).isoformat(),
        },
    )

    worker = threading.Thread(
        target=process_job,
        args=(job_id, str(save_path), cleanup_report),
        daemon=True,
    )
    worker.start()

    total_time = round(time.time() - start_ts, 2)

    log_debug(
        "STEP 11 - background worker started | job_id=%s | response_time=%s seconds",
        job_id,
        total_time,
    )

    return jsonify(
        {
            "ok": True,
            "message": "Request accepted for background processing",
            "job_id": job_id,
            "status": "queued",
            "status_endpoint": f"/ingest/status/{job_id}",
            "file_saved": str(save_path),
            "response_seconds": total_time,
        }
    ), 202


@app.post("/ingest")
def ingest():
    try:
        return _ingest_core()

    except Exception as e:
        log_exception("ingest: unhandled error")

        return jsonify(
            {
                "ok": False,
                "error": str(e),
                "error_type": type(e).__name__,
            }
        ), 500


if __name__ == "__main__":
    log_debug("Starting Flask development server")
    app.run(host="0.0.0.0", port=5000)