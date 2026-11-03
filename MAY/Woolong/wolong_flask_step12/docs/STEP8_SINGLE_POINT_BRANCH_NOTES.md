# Step 8 — Single Point Box and Branch Circuit Layer

This step extends Step 7 by porting the next electrical-output layer from the VBA workbook.

## Added

- Python equivalent of `GetSinglePointBox`
- Python equivalent of `GetSinglePointBoxHSCCR`
- Lookup against workbook ranges:
  - `Data_Common.SPBDesc12`
  - `Data_Common.SPBDesc34`
  - `Data_Common.SPBDesc5`
  - `Data_Common.SPB`
- Base-unit MOCP calculation with electric heat temporarily removed, matching the VBA block that blanks `Motor(CombusElecHeat, *)` before calling `GetSinglePointBox`
- Guarded MCA2/MOCP2/Disconnect2 branch-circuit path for the original condition:
  - 50-series
  - voltage index 5 / 208-230V 3-phase
  - heat level 3
  - non-gas
  - size not equal to 14

## Notes

The single-point-box result now appears in:

- `result.mca_mocp.single_point_box`
- `result.mca_mocp.single_point_box_hsccr`

For gas/48-series units, the VBA returns `-`, so this Python version does the same.

For 50-series electric heat units, the app now calculates the base MOCP without electric heat and uses that together with the total unit MCA/MOCP, voltage, chassis, wire count, HACR/disconnect, ERV, and HSCCR flags to select the SPB.

## Still deferred

- Accessory MCA rows for PE, ERV, convenience outlet, etc.
- Full accessory single-point-box rows
- Exact split-MCA literature output formatting
- Validation against a large set of real Excel expected outputs
