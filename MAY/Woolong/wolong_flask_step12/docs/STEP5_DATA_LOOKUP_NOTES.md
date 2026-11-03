# Step 5 — Data lookup integration

This step connects the parsed model number to the workbook's extracted `Data_*` lookup sheets.

## Added

- `services/workbook_ranges.py`
  - Loads workbook defined names from `data/defined_names.csv`.
  - Slices CSV sheets using Excel range coordinates.
  - Implements an approximate `NewLookup(value, range, return_col, False)` helper.

- `services/electrical_data.py`
  - Routes model families to data sheets.
  - Implements the first useful subset of `mWrite_Values` / `mAux_Routines`:
    - `GetVoltage`
    - `GetChassis`
    - `WriteCharge`
    - `WriteCompressors`
    - `WriteIndoorFan`
    - `WriteOutdoorFan`

- `services/model_parser.py`
  - Corrected standard FE/GE/JE/QE positional parsing to match `mFE_Std.bas`.
  - Position 5 = heat option.
  - Position 6 = refrigerant/system option.
  - Position 10 = indoor fan drive level.
  - Position 11 = coil/RTPF.
  - Position 12 = voltage code.

## Current limitations

This is not yet a full workbook replacement. Step 5 does not yet port:

- Electric heat accessories
- Convenience outlet
- Power exhaust / ERV full branch
- Gas values
- SCCR / disconnect / fuse / single point box logic
- Full MCA/MOCP logic
- Literature generation
- Brand-specific Bryant/ICP parser branches

## Validation approach

For any model used in production, compare these Python outputs against Excel:

- Voltage
- Chassis
- Charge
- Compressor RLA/LRA
- Indoor fan FLA/LRA/BHP
- Outdoor fan FLA/LRA/BHP

Once those match, continue to Step 6: MCA/MOCP calculation.
