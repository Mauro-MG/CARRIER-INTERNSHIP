# ValidateSAP Django replacement

This project replaces the workbook's `ValidationSAP` paste-and-validate workflow with a deterministic Django web application. It parses copied tabular data, blocks comparison when input is malformed or ambiguous, and then assigns every normalized part number to exactly one action category.

## Run locally

The current workspace already contains Django in `.deps`, and `manage.py` loads it automatically:

```powershell
py -3 manage.py runserver
```

Open `http://127.0.0.1:8000/`. For a clean installation elsewhere:

```powershell
py -3 -m pip install -r requirements.txt
py -3 manage.py runserver
```

Run verification with:

```powershell
py -3 manage.py check
py -3 manage.py test validatesap
```

## Save results and history

After a successful comparison, the application extracts the Tumbling name from any of these forms:

- `Tumbling Name: 30MPW017`
- a `Tumbling Name` cell followed by the value in the next column or row
- the first parsed Tumbling value as a fallback

When the name is valid, **Save Results CSV** saves the exact server-side comparison snapshot as `saved_results/<Tumbling Name>.csv`. Windows-invalid filename characters are replaced with `_`; meaningful characters such as `-`, `_`, and `.` are preserved. Existing files require an explicit overwrite confirmation.

CSV files use Excel-friendly UTF-8 with BOM and contain Part Number, Description, Quantity, Position, Source, Status, SAP Ready Record, and Reason. Rows are ordered Adds, Deletes, then No Change.

**View Past Validations** opens `/history/`, which lists CSV files newest first, calculates status counts from each file, and provides client-side Tumbling search. Opening a saved validation reads and groups the CSV directly; it does not rerun validation or comparison. CSV filenames are the sole history index—no database is used.

## Expected paste formats

Headers are optional. Paste from Excel normally produces tab-separated data; comma- and semicolon-separated data are also accepted.

| Dataset | Positional columns |
|---|---|
| Tumbling | Part Number (additional columns are preserved) |
| Adds | Item, Part Number, Quantity, Source |
| Deletes | Item, Part Number, Quantity |
| Standard BOM | Level, Item, Part Number, Description, Quantity |
| SAP Data | Level, Item, Part Number, Description, Quantity, Unit, PGr, Source Code 1, Source Code 2 |

Standard BOM and SAP Data are required. Adds, Deletes, and Tumbling may be empty.

## Validation phase

Comparison is blocked when any of these conditions is found:

- a required dataset, column, item, part number, quantity, or Add source is missing;
- a positional row has too few columns;
- quantity is non-numeric, zero, or negative;
- a normalized part number is duplicated inside one dataset;
- the same normalized part number appears in both Adds and Deletes;
- Add source is not `R`, `M`, or `B`;
- the SAP source pair is not blank/blank (`R`), 50/50 (`M`), or 0/0 (`B`).

Errors identify the dataset, row, part number when available, and the exact failure. Invalid runs return no action lists.

Part numbers are compared case-insensitively after removing pasted whitespace. The original value and original pasted record remain unchanged for display and copying.

## Comparison rules

Rules are evaluated in priority order:

1. If a part is in Deletes and is present in SAP Data or Standard BOM, it is `NEEDS_TO_BE_DELETED`.
2. Otherwise, if a part is in Adds and absent from both SAP Data and Standard BOM, it is `NEEDS_TO_BE_ADDED`.
3. Every remaining part is `NO_CHANGE`.

Add and Delete output rows use the original pasted action record so they can be copied without reconstruction. A part can never occur in more than one result category.

## Tumbling assumption

The analyzed workbook contains no identifiable Tumbling range, VBA rule, or classification behavior. The application therefore parses Tumbling, validates missing/duplicate part numbers, and includes its unique parts under `NO_CHANGE`, but it does not let Tumbling cause an Add or Delete. This is isolated in `validatesap/services/comparison.py` so a confirmed rule can be added without changing the parser or UI.

## Project structure

- `validatesap/services/parsers.py` — paste formats, header aliases, row parsing
- `validatesap/services/normalization.py` — part, quantity, and source normalization
- `validatesap/services/validators.py` — all blocking validation rules
- `validatesap/services/comparison.py` — mutually exclusive action classification
- `validatesap/services/processing.py` — two-phase orchestration
- `validatesap/templates/` and `validatesap/static/` — responsive server-rendered UI
- `validatesap/tests/` — service and view regression tests
