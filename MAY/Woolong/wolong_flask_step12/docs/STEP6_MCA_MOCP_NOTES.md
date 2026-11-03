# Step 6 - MCA/MOCP Python Port

This step ports the first production-useful part of `mMCA_Calc.bas` into Python.

## Implemented

- `GetMCAMOCP` wrapper behavior
- `GetMCAMOCPBase` cooling/base-unit formulas
- `StandardMOCP` fuse/breaker table
- `FreeBump` behavior using thresholds 30 / 60 / 80 / 100 / 400
- MCA calculation using 125% of the largest compressor/motor plus all loads
- MOCP/fuse calculation using the model MOCP factor, defaulting to 1.5
- Disconnect calculation using factor 1.15 without standard fuse rounding
- Best-effort LRA total from running loads plus largest locked-rotor delta

## Intentionally deferred

The following VBA areas still need a later step because Step 5 does not yet extract every intermediate Excel range needed by those formulas:

- `GetMCAMOCP50Base` electric-heat branch logic using `Motor(3,kW_M)`
- `MCA2` / `MOCP2` branch circuit output for electric heat
- feeder circuit behavior for dual-point wiring
- `GetSinglePointBox` and `GetSinglePointBoxHSCCR`
- accessory MCA rows for PE, ERV, convenience outlet, and other FIOPs
- exact VBA `GetLRA` continuation validation

## Important design change from Excel

The VBA writes loads into `Comp1..Comp3` and `Motor1..Motor7`, then reads them back to calculate MCA/MOCP. The Flask version keeps those loads as Python objects:

- `CompressorLoad`
- `MotorLoad`
- `AccessoryLoad`

This avoids the Excel-cell side effects and makes the calculation testable.
