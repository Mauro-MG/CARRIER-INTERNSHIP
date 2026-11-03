# Step 9 — Accessory Loads and Accessory MCA Rows

This step ports the first active accessory-load layer from the VBA workbook into Python.

## VBA areas mapped

- `mWrite_Values.WritePowerExhaustFan`
  - Active Power Exhaust path using `PwrExhVoltageData`, `PwrExhFLAData`, and `PwrExhLRAData`
  - ERV Exhaust fallback path using `Data_ERV.ERVExhDataCH#`
- `mWrite_Values.WriteConvenienceOutlet`
  - Powered convenience outlet using `Data_Common.OutletData`
- `mWrite_Values.WriteERVWheel`
  - ERV wheel using `Data_ERV.ERVWheelDataCH#`
- `mWrite_Values.WriteERVSupply`
  - ERV supply using `Data_ERV.ERVSupplyDataCH#`
- First active accessory MCA rows similar to the workbook `AccMCA` / `AccMCARHSCCR` section

## Python behavior

Active accessory loads are appended to `result.electrical.motors` as Motor4-Motor7 equivalents:

- Motor4: Power Exhaust or ERV Exhaust
- Motor5: Outlet
- Motor6: ERV Wheel
- Motor7: ERV Supply

Then `services.mca_mocp` creates `result.mca_mocp.accessory_rows`. Each accessory row calculates:

- MCA
- MOCP
- Disconnect
- LRA
- Single point box
- HSCCR single point box

## Important note on Excel formulas

Some exported CSV cells contain formulas instead of cached values, especially in `OutletData` (for example `=1000/460` or `=AI9`). The Step 9 implementation evaluates simple `=1000/x` formulas directly and uses the same FLA value as a conservative fallback for formula-reference outlet LRA cells until formula-cache extraction is added.

## Current limitations

Still deferred:

- Full optional accessory catalog rows when an accessory is not active in the base model
- Exact Excel print/literature row formatting
- Full formula evaluation for all workbook formula cells
- Large validation set against known Excel output examples

## Validation

The test suite now includes active Power Exhaust, Outlet, and ERV accessory cases.
