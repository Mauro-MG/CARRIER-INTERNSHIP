from __future__ import annotations

import json
import shutil
import zipfile
from io import BytesIO
from pathlib import Path

import pytest

from appV2 import create_app
from services.configuration_storage import save_configuration


@pytest.fixture()
def configuration_dir() -> Path:
    path = Path("test_product_configurations")
    if path.exists():
        shutil.rmtree(path)
    path.mkdir()
    yield path
    if path.exists():
        shutil.rmtree(path)


def test_new_configuration_page_loads() -> None:
    app = create_app({"TESTING": True})
    client = app.test_client()

    response = client.get("/configurations/new")

    assert response.status_code == 200
    assert b"How does this product identify pricing options?" in response.data
    assert b"Code Based" in response.data
    assert b"Character Based" in response.data


def test_code_based_builder_page_loads() -> None:
    app = create_app({"TESTING": True})
    client = app.test_client()

    response = client.get("/configurations/new?mode=code_based")

    assert response.status_code == 200
    assert b"Product Configuration Builder" in response.data
    assert b"Search Mode: Code Based" in response.data
    assert b"Position 10" in response.data
    assert b"Catalog structure" in response.data
    assert b"Base Unit Master Price Rule" in response.data
    assert b"configuration_builder.js" in response.data

    script_response = client.get("/static/js/configuration_builder.js")
    assert b"Paste specs from Excel" in script_response.data
    assert b"resolveTemplatePreview" in script_response.data


def test_character_based_builder_hides_matrix_controls() -> None:
    app = create_app({"TESTING": True})
    client = app.test_client()

    response = client.get("/configurations/new?mode=character_based")

    assert response.status_code == 200
    assert b"Search Mode: Character Based" in response.data
    assert b"Character-based option search" in response.data
    assert b"matrix-workbench code-mode-only" in response.data


def test_preview_configuration_generates_phase1_json() -> None:
    app = create_app({"TESTING": True})
    client = app.test_client()

    response = client.post(
        "/configurations/preview",
        data={
            "product_type": "30MP",
            "description": "30MP Product Configuration",
            "configuration_date": "2026-08-06",
            "version": "1",
            "position_10": "on",
            "range_10_1_enabled": "on",
            "range_10_1_start": "",
            "range_10_1_end": "C",
        },
    )

    assert response.status_code == 200
    assert b"30MP configuration" in response.data
    assert b'"configured_positions": [\n    10\n  ]' in response.data
    assert b'"1C"' in response.data


def test_save_list_edit_export_duplicate_and_delete_configuration(configuration_dir: Path) -> None:
    app = create_app({"TESTING": True, "CONFIGURATION_DIR": str(configuration_dir)})
    client = app.test_client()
    configuration = _completed_configuration()

    save_response = client.post("/configurations/save", json={"configuration": configuration})

    assert save_response.status_code == 200
    saved_name = save_response.get_json()["file_name"]
    assert saved_name == "30MP_2026-08-06_v1.json"
    assert (configuration_dir / saved_name).exists()

    list_response = client.get("/configurations")
    assert list_response.status_code == 200
    assert b"30MP" in list_response.data
    assert b"10" in list_response.data

    edit_response = client.get(f"/configurations/{saved_name}/edit")
    assert edit_response.status_code == 200
    assert b"configurationBuilderData" in edit_response.data
    assert b"30MP Product Configuration" in edit_response.data

    export_response = client.get(f"/configurations/{saved_name}/export")
    assert export_response.status_code == 200
    assert export_response.mimetype == "application/json"
    assert export_response.get_json()["base_unit_price_rule"]["end_position"] == 9

    duplicate_response = client.post(f"/configurations/{saved_name}/duplicate")
    assert duplicate_response.status_code == 302
    duplicate_config = (configuration_dir / "30MP_2026-08-06_v2.json")
    assert duplicate_config.exists()
    assert '"base_unit_price_rule"' in duplicate_config.read_text(encoding="utf-8")

    delete_response = client.post(f"/configurations/{saved_name}/delete")
    assert delete_response.status_code == 302
    assert not (configuration_dir / saved_name).exists()


def test_save_rejects_incomplete_matrix(configuration_dir: Path) -> None:
    app = create_app({"TESTING": True, "CONFIGURATION_DIR": str(configuration_dir)})
    client = app.test_client()
    configuration = _completed_configuration()
    configuration["positions"]["10"]["allowed_values_by_option_code"] = {}

    response = client.post("/configurations/save", json={"configuration": configuration})

    assert response.status_code == 400
    assert "Position 10 cannot be saved" in response.get_json()["errors"][0]


def test_character_based_save_does_not_require_matrix(configuration_dir: Path) -> None:
    app = create_app({"TESTING": True, "CONFIGURATION_DIR": str(configuration_dir)})
    client = app.test_client()
    configuration = _completed_configuration()
    configuration["search_mode"] = "character_based"
    configuration["configured_positions"] = []
    configuration["positions"] = {}

    response = client.post("/configurations/save", json={"configuration": configuration})

    assert response.status_code == 200
    saved = json.loads((configuration_dir / "30MP_2026-08-06_v1.json").read_text(encoding="utf-8"))
    assert saved["search_mode"] == "character_based"


def test_save_reports_name_conflict(configuration_dir: Path) -> None:
    app = create_app({"TESTING": True, "CONFIGURATION_DIR": str(configuration_dir)})
    client = app.test_client()
    configuration = _completed_configuration()

    first = client.post("/configurations/save", json={"configuration": configuration})
    second = client.post("/configurations/save", json={"configuration": configuration})

    assert first.status_code == 200
    assert second.status_code == 409
    assert second.get_json()["conflict"] is True
    assert second.get_json()["suggested_version"] == 2


def test_existing_configuration_without_base_unit_rule_still_loads(configuration_dir: Path) -> None:
    app = create_app({"TESTING": True, "CONFIGURATION_DIR": str(configuration_dir)})
    client = app.test_client()
    configuration = _completed_configuration()
    configuration.pop("base_unit_price_rule")
    save_configuration(configuration, configuration_dir=configuration_dir)

    response = client.get("/analysis?config=30MP_2026-08-06_v1.json")

    assert response.status_code == 200
    assert b"30MP_2026-08-06_v1.json" in response.data


def test_existing_configuration_without_search_mode_defaults_to_code_based(configuration_dir: Path) -> None:
    app = create_app({"TESTING": True, "CONFIGURATION_DIR": str(configuration_dir)})
    client = app.test_client()
    configuration = _completed_configuration()
    configuration.pop("search_mode", None)
    save_configuration(configuration, configuration_dir=configuration_dir)

    list_response = client.get("/configurations")
    assert b"Code Based" in list_response.data

    edit_response = client.get("/configurations/30MP_2026-08-06_v1.json/edit")
    assert b"Search Mode: Code Based" in edit_response.data


def test_import_preserves_base_unit_rule(configuration_dir: Path) -> None:
    app = create_app({"TESTING": True, "CONFIGURATION_DIR": str(configuration_dir)})
    client = app.test_client()
    configuration = _completed_configuration()
    configuration["version"] = 7

    response = client.post(
        "/configurations/import",
        data={"configuration_file": (BytesIO(json.dumps(configuration).encode("utf-8")), "import.json")},
        content_type="multipart/form-data",
    )

    assert response.status_code == 302
    imported = (configuration_dir / "30MP_2026-08-06_v7.json").read_text(encoding="utf-8")
    assert '"base_unit_price_rule"' in imported
    assert '"end_position": 9' in imported


def test_import_preserves_search_mode(configuration_dir: Path) -> None:
    app = create_app({"TESTING": True, "CONFIGURATION_DIR": str(configuration_dir)})
    client = app.test_client()
    configuration = _completed_configuration()
    configuration["version"] = 10
    configuration["search_mode"] = "character_based"
    configuration["configured_positions"] = []
    configuration["positions"] = {}

    response = client.post(
        "/configurations/import",
        data={"configuration_file": (BytesIO(json.dumps(configuration).encode("utf-8")), "character.json")},
        content_type="multipart/form-data",
    )

    assert response.status_code == 302
    imported = json.loads((configuration_dir / "30MP_2026-08-06_v10.json").read_text(encoding="utf-8"))
    assert imported["search_mode"] == "character_based"


def test_hyphen_mapping_survives_save_export_duplicate_and_import(configuration_dir: Path) -> None:
    app = create_app({"TESTING": True, "CONFIGURATION_DIR": str(configuration_dir)})
    client = app.test_client()
    configuration = _completed_configuration()
    configuration["version"] = 8
    configuration["positions"]["10"]["allowed_values_by_option_code"] = {"1": ["-", "0"]}
    configuration["positions"]["10"]["excluded_characters"] = ["A", "B"]

    save_response = client.post("/configurations/save", json={"configuration": configuration})
    assert save_response.status_code == 200
    saved_name = save_response.get_json()["file_name"]

    export_response = client.get(f"/configurations/{saved_name}/export")
    assert export_response.status_code == 200
    exported = export_response.get_json()
    assert exported["positions"]["10"]["allowed_values_by_option_code"]["1"] == ["-", "0"]
    assert exported["positions"]["10"]["excluded_characters"] == ["A", "B"]

    duplicate_response = client.post(f"/configurations/{saved_name}/duplicate")
    assert duplicate_response.status_code == 302
    duplicated = json.loads((configuration_dir / "30MP_2026-08-06_v9.json").read_text(encoding="utf-8"))
    assert duplicated["positions"]["10"]["allowed_values_by_option_code"]["1"] == ["-", "0"]
    assert duplicated["positions"]["10"]["excluded_characters"] == ["A", "B"]

    (configuration_dir / saved_name).unlink()
    import_response = client.post(
        "/configurations/import",
        data={"configuration_file": (BytesIO(json.dumps(exported).encode("utf-8")), "hyphen.json")},
        content_type="multipart/form-data",
    )
    assert import_response.status_code == 302
    imported = json.loads((configuration_dir / saved_name).read_text(encoding="utf-8"))
    assert imported["positions"]["10"]["allowed_values_by_option_code"]["1"] == ["-", "0"]
    assert imported["positions"]["10"]["excluded_characters"] == ["A", "B"]


def test_analysis_page_loads(configuration_dir: Path) -> None:
    app = create_app({"TESTING": True, "CONFIGURATION_DIR": str(configuration_dir)})
    client = app.test_client()

    response = client.get("/analysis")

    assert response.status_code == 200
    assert b"Analyze DOCX Pricing" in response.data
    assert b"Extract option prices" in response.data


def test_builder_exposes_orientation_bulk_controls_and_hyphen_character(configuration_dir: Path) -> None:
    app = create_app({"TESTING": True, "CONFIGURATION_DIR": str(configuration_dir)})
    response = app.test_client().get("/configurations/new?mode=code_based")

    assert response.status_code == 200
    assert b"Matrix orientation" in response.data
    assert b"Characters as columns" in response.data
    assert b"Exclude Characters" in response.data
    assert b"configuration_matrix_state.js" in response.data
    assert b'matrixRows: ["-", "0", "1"' in response.data


def test_analysis_extracts_docx_prices_with_saved_configuration(configuration_dir: Path) -> None:
    app = create_app({"TESTING": True, "CONFIGURATION_DIR": str(configuration_dir)})
    client = app.test_client()
    configuration = _completed_configuration()
    save_configuration(configuration, configuration_dir=configuration_dir)
    docx_path = configuration_dir / "pricing.docx"
    _write_analysis_docx(docx_path)

    with docx_path.open("rb") as docx_file:
        response = client.post(
            "/analysis",
            data={
                "configuration_file": "30MP_2026-08-06_v1.json",
                "catalog_number": "30MPW0315A",
                "docx_file": (docx_file, "pricing.docx"),
            },
            content_type="multipart/form-data",
        )

    assert response.status_code == 200
    assert b"Low Sound" in response.data
    assert b"$1,250.00" in response.data
    assert b"Position 10: A -> 1" in response.data


def test_analysis_requires_docx_upload(configuration_dir: Path) -> None:
    app = create_app({"TESTING": True, "CONFIGURATION_DIR": str(configuration_dir)})
    client = app.test_client()
    save_configuration(_completed_configuration(), configuration_dir=configuration_dir)

    response = client.post(
        "/analysis",
        data={"configuration_file": "30MP_2026-08-06_v1.json", "catalog_number": "30MPW0315A"},
    )

    assert response.status_code == 400
    assert b"Select a DOCX file to analyze." in response.data


def _completed_configuration() -> dict:
    return {
        "schema_version": 1,
        "search_mode": "code_based",
        "product_type": "30MP",
        "description": "30MP Product Configuration",
        "configuration_date": "2026-08-06",
        "version": 1,
        "created_at": "2026-08-06T10:30:00",
        "updated_at": "2026-08-06T10:30:00",
        "structure": [
            {
                "characteristic_key": "PRODUCT_TYPE",
                "start_position": 1,
                "end_position": 4,
                "description": "Product family or type",
                "used": True,
                "specifications": [{"catalog_value": "30MP", "label": "30MP", "description": "", "allowed": True}],
            },
            {
                "characteristic_key": "OPTIONS",
                "start_position": 10,
                "end_position": 19,
                "description": "Configurable option characters",
                "used": True,
                "specifications": [],
            },
        ],
        "base_unit_price_rule": {
            "enabled": True,
            "search_type": "range",
            "start_position": 1,
            "end_position": 9,
        },
        "configured_positions": [10],
        "positions": {
            "10": {
                "option_code_ranges": [{"group": 1, "start": "1", "end": "1A"}],
                "option_codes": ["1", "1A"],
                "allowed_values_by_option_code": {"1": ["0", "A"]},
            }
        },
    }


def _write_analysis_docx(path: Path) -> None:
    _write_minimal_docx(
        path,
        [
            ("p", "POSITION 10"),
            (
                "tbl",
                [
                    ["DESCRIPTION", "MASTER PRICE"],
                    ["", "017-033"],
                    ["Low Sound 1", "$1,250.00"],
                ],
            ),
        ],
    )


def _write_minimal_docx(path: Path, body_items: list[tuple[str, object]]) -> None:
    body_xml = []
    for kind, payload in body_items:
        if kind == "p":
            body_xml.append(_paragraph_xml(str(payload)))
        else:
            body_xml.append(_table_xml(payload))  # type: ignore[arg-type]
    document_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body>{''.join(body_xml)}<w:sectPr/></w:body></w:document>"
    )
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("[Content_Types].xml", '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>')
        archive.writestr("_rels/.rels", '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>')
        archive.writestr("word/document.xml", document_xml)


def _paragraph_xml(text: str) -> str:
    return f"<w:p><w:r><w:t>{text}</w:t></w:r></w:p>"


def _table_xml(rows: list[list[str]]) -> str:
    row_xml = []
    for row in rows:
        cells = "".join(f"<w:tc>{_paragraph_xml(cell)}</w:tc>" for cell in row)
        row_xml.append(f"<w:tr>{cells}</w:tr>")
    return f"<w:tbl>{''.join(row_xml)}</w:tbl>"
