from services.calculation_service import run_calculation
from services.model_parser import parse_model_number


def test_empty_model_returns_error():
    result = run_calculation("")
    assert result.errors.end is True
    assert any(msg.code == "MODEL_EMPTY" for msg in result.errors.messages)


def test_48_prefix_sets_series_gas_even_for_short_best_effort():
    result = run_calculation("48TC006476RP")
    assert result.model.series == 48
    assert result.model.gas is True


def test_50_prefix_sets_series_not_gas_even_for_short_best_effort():
    result = run_calculation("50TC006476RP")
    assert result.model.series == 50
    assert result.model.is_50 is True


def test_standard_fe_model_from_workbook_example_parses_without_position_errors():
    model, errors = parse_model_number("48FEDM08A2A6A0A0A0")
    assert model.model_string == "48FE"
    assert model.series == 48
    assert model.gas is True
    assert model.size == 8
    assert model.motor_drive == "2"  # VBA maps position-10 code A/2/E/H/K to fan-drive level 2
    assert model.voltage_index == 6
    assert not [m for m in errors.messages if m.severity == "error"]


def test_50ge_standard_model_routes_to_standard_parser():
    model, errors = parse_model_number("50GEDM08A2A6A0A0A0")
    assert model.model_string == "50GE"
    assert model.series == 50
    assert model.is_50 is True
    assert model.gas is False
    assert model.size == 8
    assert not [m for m in errors.messages if m.severity == "error"]


def test_invalid_standard_unit_type_is_flagged():
    model, errors = parse_model_number("48TCDM08A2A6A0A0A0")
    assert model.series == 48
    assert any(msg.code == "POSITION_3_4_UNIT_TYPE_INVALID" for msg in errors.messages)


def test_legacy_family_returns_warning_not_error():
    model, errors = parse_model_number("582LA0600000000000")
    assert model.model_string == "582L"
    assert any(msg.code == "LEGACY_FAMILY_NOT_PORTED" and msg.severity == "warning" for msg in errors.messages)
    assert not [m for m in errors.messages if m.severity == "error"]


def test_38ax_routes_to_split_system_parser():
    model, errors = parse_model_number("38AXDM08A6A0A0A000")
    assert model.model_string == "38AX"
    assert model.cdu is True
    assert model.size == 8


def test_step6_mca_mocp_base_unit_values():
    result = run_calculation("48FEDM08A2A6A0A0A0")
    assert result.mca_mocp.mca == 21
    assert result.mca_mocp.mocp == 25
    assert result.mca_mocp.fuse == 25
    assert result.mca_mocp.disconnect == 21
    assert result.mca_mocp.lra == 72
    assert "base-unit MCA/MOCP" in " ".join(result.mca_mocp.calculation_notes)


def test_step7_50_series_electric_heat_is_loaded_and_used():
    result = run_calculation("50GEBM08A2A6A0A0A0")
    heat_motors = [m for m in result.electrical.motors if "Electric Heat" in m.name]
    assert heat_motors
    assert heat_motors[0].part_number == "421A"
    assert heat_motors[0].kw == "25.0"
    assert result.mca_mocp.mca == 42
    assert result.mca_mocp.mocp == 45
    assert result.mca_mocp.num_wires == "6"
    assert "50-series electric-heat" in " ".join(result.mca_mocp.calculation_notes)


def test_step9_power_exhaust_accessory_load_and_row_are_created():
    result = run_calculation("48FEDM08A2A6A0N0A0")
    assert any("Power Exhaust" in m.name for m in result.electrical.motors)
    assert result.mca_mocp.accessory_rows
    assert any("Power Exhaust" in row.name for row in result.mca_mocp.accessory_rows)


def test_step9_convenience_outlet_accessory_load_and_row_are_created():
    result = run_calculation("48FEDM08A2A6A0A2A0")
    assert any("Outlet" in m.name for m in result.electrical.motors)
    assert any("Outlet" in row.name for row in result.mca_mocp.accessory_rows)


def test_step9_erv_accessory_loads_are_created():
    result = run_calculation("48FEDM08A2A6A020A0")
    names = " ".join(m.name for m in result.electrical.motors)
    assert "ERV Exhaust" in names
    assert "ERV Wheel" in names
    assert "ERV Supply" in names
    assert len(result.mca_mocp.accessory_rows) >= 3


def test_step10_optional_power_exhaust_catalog_row_for_base_48_unit():
    result = run_calculation("48FEDM08A2A6A0A0A0")
    names = [row.name for row in result.mca_mocp.accessory_rows]
    assert any(name == "Optional Power Exhaust" for name in names)


def test_step10_optional_electric_heat_catalog_rows_for_no_heat_50_unit():
    # Position 5 = A means no active electric heat in the Step 4 parser rules.
    result = run_calculation("50GEQM08A2A6A0A0A0")
    names = " | ".join(row.name for row in result.mca_mocp.accessory_rows)
    assert "Optional Electric Heat L" in names
    assert "Optional Power Exhaust + Electric Heat" in names


def test_step11_validation_examples_pass():
    from pathlib import Path
    from services.validation import validate_csv_file

    project_root = Path(__file__).resolve().parents[1]
    run = validate_csv_file(project_root / "validation" / "model_validation_examples.csv")
    assert run.total_cases == 3
    assert run.failed_cases == 0


def test_step11_validation_detects_failure():
    from services.validation import validate_csv_text

    csv_text = "case_id,model_number,expected_mca_mocp.mca\nBAD,48FEDM08A2A6A0A0A0,999\n"
    run = validate_csv_text(csv_text)
    assert run.total_cases == 1
    assert run.failed_cases == 1
    assert any(comp.status == "fail" for comp in run.cases[0].comparisons)


def test_step12_output_contains_info_plate_view():
    from services.output_builder import build_output

    result = run_calculation("48FEDM08A2A6A0A0A0")
    payload = build_output(result)
    assert "info_plate" in payload
    assert payload["info_plate"]["summary_cards"]
    assert any(section["id"] == "ratings" for section in payload["info_plate"]["sections"])
    assert any(table["id"] == "compressors" for table in payload["info_plate"]["tables"])


def test_step12_home_page_renders_info_plate_shell():
    import pytest
    pytest.importorskip("flask")
    from app import create_app

    client = create_app().test_client()
    response = client.get("/")
    assert response.status_code == 200
    assert b"Type a model number" in response.data
    assert b"info-plate-root" in response.data


def test_step12_api_calculate_returns_info_plate_payload():
    import pytest
    pytest.importorskip("flask")
    from app import create_app

    client = create_app().test_client()
    response = client.post("/api/calculate", json={"model_number": "48FEDM08A2A6A0A0A0"})
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["info_plate"]["model_number"] == "48FEDM08A2A6A0A0A0"
    assert payload["info_plate"]["summary_cards"]
