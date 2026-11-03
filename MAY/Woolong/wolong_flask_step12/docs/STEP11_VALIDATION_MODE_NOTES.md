# Step 11 — Excel vs Flask validation mode

This step adds a repeatable validation workflow so the Python/Flask implementation can be compared against known-good Excel/VBA outputs.

## New files

- `services/validation.py` — validation engine.
- `scripts/validate_models.py` — command-line validation runner.
- `validation/model_validation_template.csv` — blank CSV template for Excel-confirmed expected values.
- `validation/model_validation_examples.csv` — Python-baseline examples used for smoke testing.
- `templates/validation.html` — browser upload form for CSV validation.

## CSV format

Each row needs at least:

```csv
case_id,model_number
BASE48,48FEDM08A2A6A0A0A0
```

Expected fields can be added using dotted result paths prefixed by `expected_`:

```csv
expected_mca_mocp.mca,expected_mca_mocp.mocp,expected_electrical.voltage
21,25,460-3-60
```

Useful fields:

- `expected_model.series`
- `expected_model.model_string`
- `expected_model.size`
- `expected_model.chassis`
- `expected_electrical.voltage`
- `expected_electrical.charge_summary`
- `expected_mca_mocp.mca`
- `expected_mca_mocp.mocp`
- `expected_mca_mocp.fuse`
- `expected_mca_mocp.disconnect`
- `expected_mca_mocp.lra`
- `expected_mca_mocp.single_point_box`
- `expected_mca_mocp.single_point_box_hsccr`
- `expected_mca_mocp.num_wires`
- `expected_mca_mocp.actual_num_wires`
- `expected_error_codes`
- `expected_warning_codes`

Multiple expected error/warning codes can be separated with `|` or `;`.

## Command-line usage

From the project root:

```bash
python scripts/validate_models.py validation/model_validation_examples.csv
```

Optional:

```bash
python scripts/validate_models.py validation/model_validation_examples.csv \
  --output validation/my_report.csv \
  --tolerance 0.01 \
  --fields mca_mocp.mca,mca_mocp.mocp,electrical.voltage
```

## Flask usage

Run:

```bash
python app.py
```

Open:

```text
/validate
```

Upload a CSV and review pass/fail results in the browser.

## Important note

`validation/model_validation_examples.csv` currently uses the Python baseline values produced by the port. For real sign-off, replace those expected values with outputs copied from the original Excel macro after entering the same model numbers.
