# Step 10 — Optional Accessory Catalog Rows

This step ports the next layer of the Excel accessory-nameplate workflow.

The VBA does not only calculate accessories that are active in the model number. It also writes optional accessory rows into `AccRow1..AccRowN`, temporarily swaps those rows into `Motor3` and/or `Motor4`, and recalculates MCA/MOCP for each optional row.

Implemented in Python:

- Optional Power Exhaust row when PE/ERV is not already active.
- Optional Electric Heat rows for 50-series units with no selected heat.
- Optional Power Exhaust + Electric Heat combination rows.
- Shared MCA/MOCP/SPB calculation for active and optional accessory rows.
- Default heat-level catalog count of 3, with the VBA GE size-05 voltage-5 override to 7.

Still deferred:

- Exact Excel row ordering and blank-row layout.
- Full EDR lookup export.
- Legacy/split-system accessory catalog branches.
- Exact `AccMCARHSCCR` formatting quirks.
