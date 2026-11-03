# Emerson Pricing Runtime

Self-contained, per-user runtime for the local belt-drive pricing test. It does
not install a Windows service, reserve an HTTP URL, write to machine registry
locations, or require administrator rights.

## Run the smoke test

```powershell
py -3 test_loopback_pricing.py
```

A successful run prints a response beginning with `GOOD:`. The script chooses
an available `127.0.0.1` port, starts `WcfEmersonEXE-loopback.exe`, submits the
hardcoded XML request, and terminates the helper.

## Runtime components

- `WcfEmersonEXE-loopback.exe`: loopback-only, non-admin HTTP host.
- `WcfEmersonEXE.exe`: service implementation loaded by the host.
- `PTS.VbeltDriveLibrary.dll`: public configurator API.
- `PTS.VbeltDriveConfigurator.dll`: drive-selection implementation.
- `EPT.Internet.ProductSelection.dll`: product-selection dependency.
- `log4net.dll`: logging dependency.
- `Belts.xml`, `Bushings.xml`, `FixedPitchSheaves.xml`,
  `VariablePitchSheaves.xml`, `Multipliers.xml`, `DesignatedParts.xml`: matched
  December 2018 Emerson catalog/configuration set.
- `test_loopback_pricing.py`: integration smoke test and future client example.

Keep the DLL and XML versions together. Mixing files from the older archive
folders can change selections, costs, or XML compatibility.
