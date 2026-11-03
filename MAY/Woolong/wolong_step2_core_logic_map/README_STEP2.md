# Wolong Step 2 - Core VBA Logic Map

This package maps the VBA procedures, named ranges, worksheet dependencies, and first migration model for converting the XLSM macro workflow into a Flask/Python app.

## Counts
- VBA modules parsed: 60
- Procedures parsed: 352
- Procedure call edges detected: 725
- Core dependency nodes traced from Main/CalculateMCA/CalculateSplitMCA: 171
- Core named ranges detected in dependency scope: 127

## Key files
- `main_mca_call_sequence.csv`: ordered calls inside Main / CalculateMCA / CalculateSplitMCA.
- `main_dependency_trace.csv`: procedure dependency trace from Main.
- `calculate_mca_dependency_trace.csv`: dependency trace from CalculateMCA.
- `core_reference_summary.csv`: named ranges, literal ranges, and sheet references used by core VBA.
- `core_defined_names_used.csv`: workbook defined names that appear in the traced logic.
- `core_output_write_candidates.csv`: VBA lines that likely write values to Info_Plate/output ranges.
- `step2_migration_model.csv`: recommended Flask/Python migration model.

## Interpretation
The core app path is: Info_Plate model input -> Main -> model validation/parser -> data sheet selection -> Write* electrical output ranges -> MCA/MOCP calculation -> output named ranges.
