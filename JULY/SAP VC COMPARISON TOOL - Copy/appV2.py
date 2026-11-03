from __future__ import annotations

import os
import secrets

import json
import shutil
import sys
import tempfile
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from flask import Flask, Response, flash, jsonify, redirect, render_template, request, url_for
from werkzeug.exceptions import RequestEntityTooLarge
from werkzeug.utils import secure_filename

from services.configuration_service import DEFAULT_STRUCTURE_ROWS, build_phase1_configuration
from services.configuration_storage import (
    configuration_filename,
    delete_configuration,
    duplicate_configuration,
    list_configurations,
    load_configuration_by_name,
    next_available_version,
    save_configuration,
)
from services.configuration_validator import validate_configuration
from services.option_code_generator import OPTION_CODE_LETTERS
from services.docx_price_extractor import extract_catalog_prices
from services.sap_input_parser import parse_ordered_sap_prices
from services.sap_price_comparator import build_document_comparison_records, compare_sap_prices
from services.search_token_resolver import VALID_SEARCH_MODES, get_search_mode, search_mode_label
import webbrowser
from threading import Timer

POSITIONS = list(range(10, 20))
OPTION_GROUPS = list(range(1, 21))
RANGE_SUFFIXES = ["", *OPTION_CODE_LETTERS]

def open_browser():
    webbrowser.open_new_tab("http://127.0.0.1:5001/")

def _resource_path(relative_path: str) -> Path:
    base_path = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base_path / relative_path


def _runtime_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def _seed_configuration_dir(configuration_dir: str) -> None:
    target_dir = Path(configuration_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    if any(target_dir.glob("*.json")):
        return
    source_dir = _resource_path("product_configurations")
    if not source_dir.exists() or source_dir.resolve() == target_dir.resolve():
        return
    for source_file in source_dir.glob("*.json"):
        shutil.copy2(source_file, target_dir / source_file.name)


def create_app(test_config: dict[str, Any] | None = None) -> Flask:
    app = Flask(
        __name__,
        template_folder=str(_resource_path("templates")),
        static_folder=str(_resource_path("static")),
    )
    app.config.update(
        SECRET_KEY=os.environ.get("FLASK_SECRET_KEY") or secrets.token_hex(32),
        CONFIGURATION_DIR=str(_runtime_base_dir() / "product_configurations"),
        MAX_CONTENT_LENGTH=25 * 1024 * 1024,
    )
    if test_config:
        app.config.update(test_config)
    if not app.config.get("TESTING"):
        _seed_configuration_dir(app.config["CONFIGURATION_DIR"])

    @app.template_filter("money")
    def format_decimal(value: Decimal | str) -> str:
        decimal_value = Decimal(str(value))
        sign = "-" if decimal_value < 0 else ""
        return f"{sign}${abs(decimal_value):,.2f}"

    @app.template_filter("signed_money")
    def format_signed_decimal(value: Decimal | str) -> str:
        decimal_value = Decimal(str(value))
        if decimal_value > 0:
            return f"+${decimal_value:,.2f}"
        if decimal_value < 0:
            return f"-${abs(decimal_value):,.2f}"
        return "$0.00"

    @app.template_filter("sap_result_class")
    def sap_result_class(status: str) -> str:
        normalized = str(status or "").upper()
        if normalized == "MATCH":
            return "match"
        if normalized == "MISMATCH":
            return "discrepancy"
        if "NOT NUMERIC" in normalized:
            return "nonnumeric"
        if "MISSING" in normalized:
            return "review"
        return "review"

    @app.get("/")
    def index() -> Any:
        return redirect(url_for("configuration_manager"))

    @app.get("/configurations")
    def configuration_manager() -> str:
        search = request.args.get("q", "").strip().upper()
        configurations = list_configurations(configuration_dir=app.config["CONFIGURATION_DIR"])
        if search:
            configurations = [
                item for item in configurations if search in str(item.get("product_type", "")).upper()
            ]
        configurations.sort(key=lambda item: (item.get("configuration_date", ""), item.get("product_type", "")), reverse=True)
        return render_template("configuration/manage.html", configurations=configurations, search=search)

    @app.get("/analysis")
    def analysis_form() -> str:
        configurations = list_configurations(configuration_dir=app.config["CONFIGURATION_DIR"])
        selected_config = request.args.get("config", "")
        return render_template(
            "configuration/analyze.html",
            configurations=configurations,
            selected_config=selected_config,
            catalog_number="",
            sap_pricing_data="",
        )

    @app.post("/analysis")
    def analyze_docx() -> tuple[str, int] | str:
        configurations = list_configurations(configuration_dir=app.config["CONFIGURATION_DIR"])
        selected_config = request.form.get("configuration_file", "").strip()
        catalog_number = request.form.get("catalog_number", "").strip().upper()
        sap_pricing_data = request.form.get("sap_pricing_data", "")
        upload = request.files.get("docx_file")

        if not selected_config:
            flash("Select a saved product configuration.", "error")
            return render_template(
                "configuration/analyze.html",
                configurations=configurations,
                selected_config=selected_config,
                catalog_number=catalog_number,
                sap_pricing_data=sap_pricing_data,
            ), 400
        if not catalog_number:
            flash("Enter a complete catalog number.", "error")
            return render_template(
                "configuration/analyze.html",
                configurations=configurations,
                selected_config=selected_config,
                catalog_number=catalog_number,
                sap_pricing_data=sap_pricing_data,
            ), 400
        if upload is None or not upload.filename:
            flash("Select a DOCX file to analyze.", "error")
            return render_template(
                "configuration/analyze.html",
                configurations=configurations,
                selected_config=selected_config,
                catalog_number=catalog_number,
                sap_pricing_data=sap_pricing_data,
            ), 400

        filename = secure_filename(upload.filename)
        if not filename or Path(filename).suffix.lower() != ".docx":
            flash("Only DOCX uploads are supported for analysis.", "error")
            return render_template(
                "configuration/analyze.html",
                configurations=configurations,
                selected_config=selected_config,
                catalog_number=catalog_number,
                sap_pricing_data=sap_pricing_data,
            ), 400

        try:
            configuration = load_configuration_by_name(
                selected_config,
                configuration_dir=app.config["CONFIGURATION_DIR"],
            )
        except (OSError, ValueError, json.JSONDecodeError):
            flash("The selected configuration could not be loaded.", "error")
            return render_template(
                "configuration/analyze.html",
                configurations=configurations,
                selected_config=selected_config,
                catalog_number=catalog_number,
                sap_pricing_data=sap_pricing_data,
            ), 400

        temp_path: str | None = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as temp_file:
                temp_path = temp_file.name
                upload.save(temp_file)
            if Path(temp_path).stat().st_size == 0:
                flash("The uploaded DOCX is empty.", "error")
                return render_template(
                    "configuration/analyze.html",
                    configurations=configurations,
                    selected_config=selected_config,
                    catalog_number=catalog_number,
                    sap_pricing_data=sap_pricing_data,
                ), 400

            result = extract_catalog_prices(temp_path, catalog_number, configuration)
            sap_parse_result = parse_ordered_sap_prices(sap_pricing_data)
            document_records = build_document_comparison_records(result)
            sap_comparison = (
                compare_sap_prices(sap_parse_result.records, document_records)
                if sap_pricing_data.strip()
                else None
            )
        except Exception:
            app.logger.exception("V2 DOCX price extraction failed")
            flash("The DOCX could not be analyzed. Verify that it is a valid Word document with extractable tables.", "error")
            return render_template(
                "configuration/analyze.html",
                configurations=configurations,
                selected_config=selected_config,
                catalog_number=catalog_number,
                sap_pricing_data=sap_pricing_data,
            ), 500
        finally:
            if temp_path:
                try:
                    Path(temp_path).unlink(missing_ok=True)
                except OSError:
                    app.logger.warning("Could not delete temporary analysis upload: %s", temp_path)

        return render_template(
            "configuration/analysis_results.html",
            result=result,
            catalog_number=catalog_number,
            configuration=configuration,
            configuration_file=selected_config,
            filename=filename,
            sap_pricing_data=sap_pricing_data,
            sap_parse_result=sap_parse_result,
            document_records=document_records,
            sap_comparison=sap_comparison,
        )

    @app.get("/configurations/new")
    def new_configuration() -> str:
        search_mode = request.args.get("mode", "").strip().lower()
        if search_mode not in VALID_SEARCH_MODES:
            return render_template("configuration/choose_mode.html")
        return _render_builder(configuration=_new_configuration_draft(search_mode))

    @app.get("/configurations/<file_name>/edit")
    def edit_configuration(file_name: str) -> str:
        try:
            configuration = load_configuration_by_name(file_name, configuration_dir=app.config["CONFIGURATION_DIR"])
        except (OSError, ValueError, json.JSONDecodeError):
            flash("The selected configuration could not be loaded.", "error")
            return redirect(url_for("configuration_manager"))
        return _render_builder(configuration=configuration, current_file_name=file_name)

    @app.post("/configurations/preview")
    def preview_configuration() -> tuple[str, int] | str:
        form_state = _capture_form_state(request.form)
        selected_positions = [
            position for position in POSITIONS if request.form.get(f"position_{position}") == "on"
        ]
        ranges_by_position = _capture_ranges(request.form, selected_positions)
        configuration, build_errors = build_phase1_configuration(
            product_type=request.form.get("product_type", ""),
            description=request.form.get("description", ""),
            configuration_date=request.form.get("configuration_date", ""),
            version=request.form.get("version", "1"),
            selected_positions=selected_positions,
            ranges_by_position=ranges_by_position,
        )
        errors = [*build_errors, *validate_configuration(configuration, require_matrix=False)]
        if errors:
            for error in errors:
                flash(error, "error")
            return (
                render_template(
                    "configuration/new.html",
                    today=date.today().isoformat(),
                    positions=POSITIONS,
                    option_groups=OPTION_GROUPS,
                    range_suffixes=RANGE_SUFFIXES,
                    form_state=form_state,
                    errors=errors,
                ),
                400,
            )

        return render_template("configuration/preview.html", configuration=configuration)

    @app.post("/configurations/save")
    def save_configuration_api() -> tuple[Any, int] | Any:
        payload = request.get_json(silent=True) or {}
        configuration = payload.get("configuration")
        if not isinstance(configuration, dict):
            return jsonify({"ok": False, "errors": ["Configuration payload is required."]}), 400

        current_file_name = str(payload.get("current_file_name", "")).strip()
        overwrite = bool(payload.get("overwrite"))
        save_as_new_version = bool(payload.get("save_as_new_version"))

        now = datetime.now().replace(microsecond=0).isoformat()
        configuration["search_mode"] = get_search_mode(configuration)
        configuration["updated_at"] = now
        if not configuration.get("created_at"):
            configuration["created_at"] = now
        if save_as_new_version:
            configuration["version"] = next_available_version(
                configuration, configuration_dir=app.config["CONFIGURATION_DIR"]
            )
            configuration["created_at"] = now

        errors = validate_configuration(configuration, require_matrix=True)
        if errors:
            return jsonify({"ok": False, "errors": errors}), 400

        target_file_name = configuration_filename(configuration)
        allow_overwrite = overwrite or bool(current_file_name and current_file_name == target_file_name)
        try:
            path = save_configuration(
                configuration,
                overwrite=allow_overwrite,
                configuration_dir=app.config["CONFIGURATION_DIR"],
            )
        except FileExistsError:
            suggested_version = next_available_version(configuration, configuration_dir=app.config["CONFIGURATION_DIR"])
            return (
                jsonify(
                    {
                        "ok": False,
                        "conflict": True,
                        "file_name": target_file_name,
                        "suggested_version": suggested_version,
                    }
                ),
                409,
            )

        return jsonify({"ok": True, "file_name": Path(path).name, "redirect_url": url_for("configuration_manager")})

    @app.post("/configurations/<file_name>/delete")
    def delete_configuration_route(file_name: str) -> Any:
        try:
            delete_configuration(file_name, configuration_dir=app.config["CONFIGURATION_DIR"])
            flash("Configuration deleted.", "success")
        except (OSError, ValueError):
            flash("The configuration could not be deleted.", "error")
        return redirect(url_for("configuration_manager"))

    @app.post("/configurations/<file_name>/duplicate")
    def duplicate_configuration_route(file_name: str) -> Any:
        try:
            duplicate_configuration(file_name, configuration_dir=app.config["CONFIGURATION_DIR"])
            flash("Configuration duplicated as the next available version.", "success")
        except (OSError, ValueError, FileExistsError, json.JSONDecodeError):
            flash("The configuration could not be duplicated.", "error")
        return redirect(url_for("configuration_manager"))

    @app.get("/configurations/<file_name>/export")
    def export_configuration(file_name: str) -> Any:
        try:
            from services.configuration_storage import resolve_configuration_path

            path = resolve_configuration_path(file_name, configuration_dir=app.config["CONFIGURATION_DIR"])
        except ValueError:
            flash("The configuration file name is invalid.", "error")
            return redirect(url_for("configuration_manager"))
        response = Response(path.read_bytes(), mimetype="application/json")
        response.headers["Content-Disposition"] = f'attachment; filename="{path.name}"'
        return response

    @app.post("/configurations/import")
    def import_configuration() -> Any:
        upload = request.files.get("configuration_file")
        if upload is None or not upload.filename:
            flash("Select a JSON configuration file to import.", "error")
            return redirect(url_for("configuration_manager"))

        filename = secure_filename(upload.filename)
        if Path(filename).suffix.lower() != ".json":
            flash("Only JSON configuration files can be imported.", "error")
            return redirect(url_for("configuration_manager"))

        try:
            configuration = json.loads(upload.read().decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            flash("The imported file is not valid JSON.", "error")
            return redirect(url_for("configuration_manager"))

        configuration["search_mode"] = get_search_mode(configuration)
        errors = validate_configuration(configuration, require_matrix=True)
        if errors:
            for error in errors:
                flash(error, "error")
            return redirect(url_for("configuration_manager"))

        try:
            save_configuration(configuration, overwrite=False, configuration_dir=app.config["CONFIGURATION_DIR"])
            flash("Configuration imported.", "success")
        except FileExistsError:
            flash("A configuration with the same product type, date, and version already exists.", "error")
        return redirect(url_for("configuration_manager"))

    @app.errorhandler(RequestEntityTooLarge)
    def too_large(_: RequestEntityTooLarge) -> tuple[str, int]:
        flash("The uploaded file exceeds the 25 MB limit.", "error")
        return redirect(url_for("analysis_form")), 413

    return app


def _render_builder(
    *,
    configuration: dict[str, Any] | None = None,
    current_file_name: str = "",
) -> str:
    return render_template(
        "configuration/builder.html",
        today=date.today().isoformat(),
        positions=POSITIONS,
        option_groups=OPTION_GROUPS,
        range_suffixes=RANGE_SUFFIXES,
        initial_configuration=configuration,
        current_file_name=current_file_name,
        matrix_rows=list("-0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"),
        default_structure=DEFAULT_STRUCTURE_ROWS,
        search_mode_label=search_mode_label(get_search_mode(configuration or {})),
    )


def _new_configuration_draft(search_mode: str) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "search_mode": search_mode,
        "product_type": "",
        "description": "",
        "configuration_date": date.today().isoformat(),
        "version": 1,
        "created_at": None,
        "updated_at": None,
        "structure": [dict(row) for row in DEFAULT_STRUCTURE_ROWS],
        "option_positions": {"start": 10, "end": 19},
        "base_unit_price_rule": {"enabled": False, "search_type": "range", "start_position": 1, "end_position": 9},
        "conditional_price_rules": {"enabled": False, "positions": []},
        "configured_positions": [],
        "positions": {},
    }


def _capture_form_state(form: Any) -> dict[str, Any]:
    state: dict[str, Any] = {
        "product_type": form.get("product_type", ""),
        "description": form.get("description", ""),
        "configuration_date": form.get("configuration_date", date.today().isoformat()),
        "version": form.get("version", "1"),
        "selected_positions": [position for position in POSITIONS if form.get(f"position_{position}") == "on"],
        "ranges": {},
    }
    for position in POSITIONS:
        state["ranges"][str(position)] = {}
        for group in OPTION_GROUPS:
            state["ranges"][str(position)][str(group)] = {
                "enabled": form.get(f"range_{position}_{group}_enabled") == "on",
                "start_suffix": form.get(f"range_{position}_{group}_start", ""),
                "end_suffix": form.get(f"range_{position}_{group}_end", "Z"),
            }
    return state


def _capture_ranges(form: Any, selected_positions: list[int]) -> dict[int, list[dict[str, Any]]]:
    ranges_by_position: dict[int, list[dict[str, Any]]] = {}
    for position in selected_positions:
        ranges_by_position[position] = []
        for group in OPTION_GROUPS:
            if form.get(f"range_{position}_{group}_enabled") != "on":
                continue
            start_suffix = form.get(f"range_{position}_{group}_start", "")
            end_suffix = form.get(f"range_{position}_{group}_end", "Z")
            ranges_by_position[position].append(
                {
                    "group": group,
                    "start": _compose_option_code(group, start_suffix),
                    "end": _compose_option_code(group, end_suffix),
                }
            )
    return ranges_by_position


def _compose_option_code(group: int, suffix: str) -> str:
    normalized_suffix = suffix.strip().upper()
    return f"{group}{normalized_suffix}"


app = create_app()


if __name__ == "__main__":
    Timer(0.1,open_browser).start()
    app.run(debug=False, port=5001)
