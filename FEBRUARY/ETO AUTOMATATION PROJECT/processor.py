import os
import sys
import time
import base64
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
import pdfplumber

from asana_client import (
    get_project_custom_field_settings,
    build_custom_fields_by_name,
    build_notes_with_parts,
    create_task_with_custom_fields,
    attach_file_to_task,
)
from pdf_extraction import collect_items, extract_tumbling, extract_header_info


_APP_ROOT = Path(__file__).resolve().parent
UPLOAD_DIR = _APP_ROOT / "incoming_pdfs"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_EXTENSIONS = {".pdf"}


ASANA_TOKEN = os.getenv("ASANA_TOKEN", "")
PROJECT_GID = os.getenv("ASANA_PROJECT_GID", "1211531277250279")

AHU_USER_GID = os.getenv("ASANA_AHU_USER_GID", "1211243647054567")
ROOFTOP_USER_GID = os.getenv("ASANA_ROOFTOP_USER_GID", "1211137208483755")


def _allowed_file(filename: str) -> bool:
    return Path(filename).suffix.lower() in ALLOWED_EXTENSIONS


def cleanup_old_pdfs(folder: Path, days: int = 7) -> dict:
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=days)
    deleted = 0
    kept = 0
    errors = []

    if not folder.exists():
        return {"ok": True, "deleted": 0, "kept": 0, "errors": [], "note": "folder_missing"}

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


def process_pdf(
    pdf_path: str,
    progress_callback=None,
    log_callback=None,
):
    def emit_log(msg):
        if log_callback:
            log_callback(msg)

    def emit_progress(value, msg=""):
        if progress_callback:
            progress_callback(value, msg)

    start_ts = time.time()
    pdf_path = Path(pdf_path)

    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    if not _allowed_file(pdf_path.name):
        raise ValueError("Only PDF files are allowed")

    if not ASANA_TOKEN or not PROJECT_GID:
        raise RuntimeError("Missing ASANA_TOKEN or ASANA_PROJECT_GID")

    emit_progress(5, "Cleaning old PDFs")
    cleanup_report = cleanup_old_pdfs(UPLOAD_DIR, days=7)
    emit_log(f"Cleanup report: {cleanup_report}")

    emit_progress(10, "Reading file")
    pdf_bytes = pdf_path.read_bytes()

    if pdf_bytes.startswith(b"JVBER") and not pdf_bytes.startswith(b"%PDF"):
        emit_log("Detected base64-encoded PDF, decoding")
        try:
            pdf_bytes = base64.b64decode(pdf_bytes, validate=True)
        except Exception:
            pdf_bytes = base64.b64decode(pdf_bytes)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    save_path = UPLOAD_DIR / f"{stamp}__{pdf_path.name}"
    save_path.write_bytes(pdf_bytes)
    emit_log(f"Saved PDF to: {save_path}")

    emit_progress(25, "Extracting PDF data")
    with pdfplumber.open(str(save_path)) as pdf:
        items_all, grouped = collect_items(pdf)
        header_info = extract_header_info(pdf)
        items_unique = extract_tumbling(items_all)

    emit_log(f"Items extracted: {len(items_all)}")
    emit_log(f"Unique items: {len(items_unique)}")
    emit_log(f"Header info: {header_info}")

    emit_progress(45, "Loading Asana settings")
    project_cfs = get_project_custom_field_settings(ASANA_TOKEN, PROJECT_GID)

    created = []
    total_items = max(len(items_unique), 1)

    for index, item in enumerate(items_unique, start=1):
        tumbling = item.get("tumbling")
        if not tumbling:
            emit_log(f"Skipping item {index}: missing tumbling")
            continue

        step_progress = 45 + int((index / total_items) * 50)
        emit_progress(step_progress, f"Creating task {index}/{total_items}")

        emit_log(f"Building task for tumbling: {tumbling}")
        notes = build_notes_with_parts(item, grouped)

        custom_fields, assignee_id = build_custom_fields_by_name(
            project_cfs,
            item,
            grouped,
            ahu_user_gid=AHU_USER_GID,
            rooftop_user_gid=ROOFTOP_USER_GID,
            header_info=header_info,
        )

        task = create_task_with_custom_fields(
            token=ASANA_TOKEN,
            project_gid=PROJECT_GID,
            name=str(tumbling),
            custom_fields=custom_fields,
            notes=notes,
            assignee_gid=assignee_id,
        )

        time.sleep(1.5)

        attachment_gid = None
        attachment_error = None

        try:
            attach = attach_file_to_task(
                ASANA_TOKEN,
                str(task.get("gid")),
                str(save_path),
                retries=5,
                delay=2.0,
            )
            attachment_gid = attach.get("gid")
            emit_log(f"Attached PDF to task {task.get('gid')}")
        except Exception as e:
            attachment_error = str(e)
            emit_log(f"Attachment failed for task {task.get('gid')}: {e}")

        created.append({
            "gid": task.get("gid"),
            "name": task.get("name"),
            "attachment_gid": attachment_gid,
            "attachment_error": attachment_error,
        })

    total_time = round(time.time() - start_ts, 2)
    emit_progress(100, "Done")
    emit_log(f"Finished in {total_time} seconds")

    return {
        "ok": True,
        "file_saved": str(save_path),
        "header_info": header_info,
        "items_all_count": len(items_all),
        "items_unique_count": len(items_unique),
        "tasks_created": created,
        "cleanup": cleanup_report,
        "processing_seconds": total_time,
    }