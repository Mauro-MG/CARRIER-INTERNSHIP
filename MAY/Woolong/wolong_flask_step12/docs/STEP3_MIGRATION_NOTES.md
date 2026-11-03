# Step 3 Migration Notes

This package is the first Python/Flask skeleton for replacing the Excel VBA workbook.

## What was converted from VBA structure

| VBA object/procedure | Python equivalent |
|---|---|
| `ModelNumber_Type` | `models/model_number.py::ModelNumber` |
| `Error_Type` | `models/errors.py::ErrorResult` |
| `Main()` | `services/calculation_service.py::run_calculation()` |
| `CheckModelNumber` | `services/model_parser.py::parse_model_number()` placeholder |
| `WriteCompressors`, `WriteIndoorFan`, etc. | `services/electrical_data.py::build_electrical_result()` placeholder |
| `CalculateMCA`, `GetMCAMOCP`, `GetMCAMOCP50` | `services/mca_mocp.py::calculate_mca_mocp()` placeholder |
| `mWrite_Values` output named ranges | JSON/result dataclasses |

## What is intentionally not done yet

The exact model decoding and MCA/MOCP formulas are not ported yet. This is deliberate. Step 3 creates the project shell and data model so the next step can port logic in smaller chunks and compare against Excel outputs.

## Next step

Step 4 should port the real model parser from `CheckModelNumber` and the unit-specific modules:

- `mFE_Std`
- `mFE_Bryant`
- `mFE_ICP`
- `m38AX_Std`
- `m38AX_Bryant`
- `m38Ax_ICP`
- `mUnit_Dependent`

Recommended method:

1. Pick one known model family first, probably the family used in the uploaded workbook.
2. Identify every substring position used by the VBA parser.
3. Implement only that family in Python.
4. Run Excel vs Flask comparison tests for 5–10 real model numbers.
