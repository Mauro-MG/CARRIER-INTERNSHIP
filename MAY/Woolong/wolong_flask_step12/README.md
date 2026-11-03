# Wolong Nameplate Tool - Flask Migration Skeleton

This is Step 3 of the Excel/VBA-to-Flask migration.

The goal of this package is to replace the macro workflow:

```text
Info_Plate change -> Main -> CheckModelNumber -> Write electrical values -> CalculateMCA -> write outputs
```

with this Flask/Python workflow:

```text
Web form/API -> run_calculation() -> parse model -> load lookup data -> build electrical loads -> calculate MCA/MOCP -> return structured result
```

## Install

```bash
python -m venv .venv
.venv\Scripts\activate      # Windows
# source .venv/bin/activate  # Mac/Linux
pip install -r requirements.txt
```

## Run

```bash
python app.py
```

Then open:

```text
http://127.0.0.1:5000
```

## API example

```bash
curl -X POST http://127.0.0.1:5000/api/calculate \
  -H "Content-Type: application/json" \
  -d "{\"model_number\": \"48TC006476RP\"}"
```

## Add the Step 1 extracted CSV data

From the project root, run:

```bash
python scripts/copy_step1_csvs.py /path/to/wolong_step1_data_extract/sheets_csv
```

This copies the core Excel lookup sheets into `data/` with clean names.

## Current status

This is a skeleton, not a production calculator yet.

Working now:

- Flask app starts
- Web form accepts model number
- JSON API accepts model number
- VBA `ModelNumber_Type` is represented as a Python dataclass
- Structured error/message system exists
- Structured electrical/MCA/MOCP output objects exist
- Lookup-table loader is ready

Pending:

- Exact `CheckModelNumber` port
- Exact electrical lookup port from `mWrite_Values`
- Exact MCA/MOCP port from `mMCA_Calc`
- Excel-vs-Python validation tests

## Step 4 update

Step 4 adds the first real model-number parser migrated from the VBA `CheckModelNumber` flow.

New files:

- `services/parser_rules.py`
- updated `services/model_parser.py`
- updated `services/electrical_data.py`
- `docs/STEP4_MODEL_PARSER_NOTES.md`

Supported first-pass parser branches:

- Standard 18-character FE/GE/JE/QE packaged models
- Standard 18-character 38AX split-system models
- Legacy Bryant/ICP/special-order families are detected and returned as warnings when not yet ported

Run tests:

```bash
PYTHONPATH=. pytest -q
```


## Step 5 status

The app now performs real workbook-style data lookups for the first electrical output slice:

- Voltage
- Chassis
- Refrigerant charge
- Compressor part numbers/RLA/LRA
- Indoor fan FLA/LRA/BHP
- Outdoor fan FLA/LRA/BHP

Run tests:

```bash
python -m pytest -q
```

Run the app:

```bash
python app.py
```

Known limitation: Step 5 is still pre-MCA/MOCP. The next migration step should calculate MCA/MOCP from the generated compressor/motor load objects instead of from Excel cells.


## Step 6 update

Step 6 implements the first Python MCA/MOCP calculation path. The app now uses compressor and fan loads from the `Data_*` lookup tables and calculates base-unit MCA, MOCP/fuse, disconnect, and a best-effort LRA value.

Run tests with:

```bash
PYTHONPATH=. pytest -q
```

Known limitations are documented in `docs/STEP6_MCA_MOCP_NOTES.md`.


## Step 7 update

Step 7 adds the first 50-series electric-heat path:

- `WriteCombustionFan` electric-heat lookup into Python
- `GetMCAMOCP50` / `GetMCAMOCP50Base` main-circuit calculation
- Electric heat part/kW/FLA/wire extraction from `Data_Common` and `Data_*` ranges
- 50-series heat-level parsing from position 5

Run tests with:

```bash
PYTHONPATH=. pytest -q
```

Known limitations are documented in `docs/STEP7_ELECTRIC_HEAT_MCA_MOCP_NOTES.md`.

## Step 8 status

Step 8 adds single-point-box selection and the first branch-circuit output layer. The app now ports `GetSinglePointBox`, `GetSinglePointBoxHSCCR`, and a guarded MCA2/MOCP2 branch-circuit path for the original 75 kW 208/230V electric-heat condition.

Run tests with:

```bash
PYTHONPATH=. pytest -q
```


## Step 9 status

Step 9 adds the first accessory-load layer migrated from `mWrite_Values` and the first accessory MCA rows from `AccMCA` / `AccMCARHSCCR` behavior.

Implemented now:

- `WritePowerExhaustFan` active Motor4 path for Power Exhaust and ERV Exhaust
- `WriteConvenienceOutlet` active Motor5 path
- `WriteERVWheel` active Motor6 path
- `WriteERVSupply` active Motor7 path
- Active accessory MCA row calculations for Motor4-Motor7 loads
- Accessory rows returned in `result.mca_mocp.accessory_rows` and displayed in the results template

Run tests with:

```bash
PYTHONPATH=. pytest -q
```

## Step 10 update

Step 10 adds optional accessory catalog rows. The app now creates AccRow-style rows for optional power exhaust, optional electric heat levels, and optional power exhaust + electric heat combinations where the original VBA generated accessory nameplate rows.

## Step 11 validation mode

This package includes a validation workflow to compare Flask outputs against expected Excel/VBA outputs.

Run the browser app:

```bash
python app.py
```

Then open `/validate` and upload `validation/model_validation_template.csv` after filling expected values from Excel.

Run from command line:

```bash
python scripts/validate_models.py validation/model_validation_examples.csv
```

The command writes a detailed comparison CSV to `validation/validation_report.csv` by default.

## Step 12 — Info_Plate-style visualization

Run the app:

```bash
python app.py
```

Open:

```text
http://127.0.0.1:5000/
```

Type a model number. The page auto-calculates and displays the generated Info_Plate-style output: summary cards, nameplate values, electrical ratings, decoded options, compressors, motors, accessory rows, notes, errors/warnings, every generated field, and raw JSON.

Example models:

```text
48FEDM08A2A6A0A0A0
50GEBM08A2A6A0A0A0
48FEDM08A2A6A0N0A0
48FEDM08A2A6A0A2A0
48FEDM08A2A6A020A0
```
