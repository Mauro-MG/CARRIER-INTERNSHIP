# Step 4 — Model parser migration notes

This step replaces the skeleton parser with the first real Python version of the VBA `CheckModelNumber` flow.

## What was ported

- Input normalization similar to Excel/VBA behavior.
- 18-character standard packaged model detection.
- Standard Carrier-style family routing for:
  - `48FE` / `50FE`
  - `48GE` / `50GE`
  - `48JE` / `50JE`
  - `48QE` / `50QE`
- Standard `38AX` split-system routing.
- Position-by-position validation using the validation messages visible in `vbaProject.bin`.
- Basic model fields filled into `ModelNumber`:
  - `series`
  - `gas`
  - `is_50`
  - `model_string`
  - `chassis`
  - `size`
  - `motor_drive`
  - `refrigerant_option`
  - `sensor_option`
  - `control_type_text`
  - `voltage_index`
  - `design`
  - `packaging`
  - several derived flags
- Early voltage text is now populated in `ElectricalResult`.

## What was intentionally not fully ported yet

The following workbook families are detected, but their exact brand-specific parser branches are not yet translated:

- Bryant/ICP legacy families such as `582L`, `559L`, `547L`, `551L`, `581L`, `549L`, `549Q`
- ICP/R-series families such as `RGF`, `RAF`, `RHF`, `RGG`, `RAG`, `RHG`, `RDG`
- `569L`, `575L`, `569J`, `575J`
- `CAL`, `CHL`
- special-order flows

Those branches have their own VBA procedures, so guessing them would create hidden calculation risk.

## Important limitation

Some extracted VBA modules are partially corrupted as text, so this Step 4 parser uses the readable procedure names and validation strings from the embedded VBA binary. The current parser is suitable for the first Flask MVP, but it should be validated against Excel outputs with real model-number test cases.

## Next step

Step 5 should start mapping parsed model fields to the `Data_*` CSV lookup tables, replacing VBA procedures such as:

- `WriteCompressors`
- `WriteIndoorFan`
- `WriteOutdoorFan`
- `WriteCharge`
- `GetVoltage`
- `GetSCCR`
- `GetChassis`
