# Step 7 — 50-Series Electric Heat MCA/MOCP

This step ports the first practical 50-series electric-heat path from VBA into Python.

## VBA areas mapped

- `mWrite_Values.WriteCombustionFan`
  - Loads electric heat as `Motor3`.
  - Uses `ElecHeatPartNumFiop*` / `ElecHeatPartNumL*` ranges from the unit data sheet.
  - Uses `Data_Common.ElecHeatDataSinglePhase`, `ElecHeatDataThreePhase`, or `ElecHeatData50`.
  - Reads heater quantity, FLA/LRA, kW, `NumofWires`, and `ActNumofWires`.

- `mMCA_Calc.GetMCAMOCP50`
- `mMCA_Calc.GetMCAMOCP50Base`
  - Removes electric heat from the normal motor list.
  - Treats electric heat as its own load.
  - Calculates cooling section and heating section.
  - Returns the maximum of cooling and heating results.
  - Implements the 50 kW exception where applicable.

## Implemented

- Position 5 heat-level decoding for 50-series models:
  - `A` = heat level 1
  - `B` = heat level 2
  - `C` = heat level 3
  - `Q` = heat pump/no electric heater
  - `-` = no electric heater

- Electric heat lookup:
  - Part number
  - FLA/LRA
  - kW
  - number of wires
  - actual number of wires

- 50-series MCA/MOCP calculation:
  - MCA
  - MOCP/Fuse
  - Disconnect
  - LRA continues as base/cooling LRA until fully validated

## Known limitations

Still deferred:

- Feeder/literature branch rows
- `MCA2` / `MOCP2` branch circuit output
- exact single-point-box selection via `GetSinglePointBox`
- HSCCR single-point-box override via `GetSinglePointBoxHSCCR`
- accessory MCA rows for PE, ERV, convenience outlet, etc.
- full Excel cached formula resolution for all data-table formula cells

## Validation examples

The test suite now includes a 50-series electric heat case:

```text
50GEBM08A2A6A0A0A0
```

Expected first-pass values:

```text
Electric heat part: 421A
Electric heat kW: 25.0
MCA: 42
MOCP/Fuse: 45
Num wires: 6
Actual num wires: 6
```
