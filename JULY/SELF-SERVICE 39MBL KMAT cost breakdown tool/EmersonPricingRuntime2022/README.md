# Python Excel-Rules Migration

`pricing_rule_engine.py` is a read-only Python migration of the pricing logic in
`laufansledprice20251013 RELEASED.xlsm`. Excel is not launched and the workbook
is never modified.

The implementation keeps the workbook as the current rule-data source:

1. Reads cached values and comments directly from the `.xlsm` Open XML files.
2. Finds every `RULEBEGIN.*` / `RULEEND` table on `Rules`.
3. Creates the `P1`, `P2`, ... part-position hits.
4. Evaluates table matches in workbook order.
5. Reproduces substitutions (`*NAME#`), motor quantity multiplication,
   motor-base conversion, hit removal, errors, and the three price factors.
6. For `$DRIVEDLL`, launches the loopback helper as the current user, sends the
   rule-derived drive inputs, selects the second-lowest distinct solution like
   VBA, applies extra-belt cost when requested, and terminates the helper.

Every JSON result also contains `reconciliation`. It accumulates `$BASE*`,
`$SPRINGS*`, and `$OPTIONS*` as `sled`; `$MOTOR*` as `motor`; and `$DRIVE*` as
`drive`. It multiplies each bucket by its corresponding workbook factor and
compares their sum with `total_price`. Any remaining price category is listed
under `unclassified_price_hits` with its adjusted contribution.
`matches_total_price` is true when the absolute difference is no more than the
configured `price_tolerance` of `0.01`.

## Run one part

```powershell
py -3 pricing_rule_engine.py 39MBHHGTB10674MHDK
```

Write the structured result to a file:

```powershell
py -3 pricing_rule_engine.py 39MBHHGTB10674MHDK --json-out result.json
```

Rule-only diagnostic mode (no Emerson call):

```powershell
py -3 pricing_rule_engine.py 39MBHHGTB10674MHDK --no-drive --trace
```

## Regression test

```powershell
py -3 -m unittest -v test_pricing_rule_engine.py
```

The regression cases are prices already cached in the released workbook:

- `39MBHHGTB10674MHDK` -> `2333.811990811239`
- `39MBS9PRB13210PCCK` -> `4075.621778734150`

## Runtime version

The DLLs and six XML files in this directory are the versions that were located
beside the 2025 workbook: the original 2013 solver assemblies with the August
2022 catalog data. The December 2018 package is functional but produces
different drive costs, so it must not be used for price-parity validation.

## Known legacy behavior

The VBA attempts to use the second-lowest distinct positive drive cost. If only
one distinct cost exists, its fallback assigns a `999999` sentinel by mistake.
Python uses the only valid solution and emits a warning instead.
