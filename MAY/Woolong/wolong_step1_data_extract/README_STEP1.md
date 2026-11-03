# Wolong Excel Tool — Step 1 Data Extraction
Source file: `48TC006476RP_Wolong_NEW.xlsm`
## Summary
- Sheets: 22 (22 visible, 0 hidden)
- Defined/named ranges: 1209
- Excel Tables/ListObjects: 4
- Formula cells detected: 34660

## Important files
- `workbook_sheet_inventory.csv`: sheet names, visibility, size, formulas, and CSV file paths.
- `defined_names.csv`: named ranges and their references.
- `excel_tables.csv`: official Excel tables and their sheet/range.
- `excel_table_columns.csv`: official Excel table column names.
- `sheets_csv/`: one CSV export per worksheet. Formula cells are written as `=FORMULA`.
- `formulas_csv/`: per-sheet formula listings with cached values.
- `tables_csv/`: direct CSV exports of official Excel tables.

## Sheets
- 01. `Revisions` — visible, G23, nonempty=104, formulas=0
- 02. `List of Worksheets` — visible, A19, nonempty=19, formulas=0
- 03. `Run_All_EDRs` — visible, G10, nonempty=14, formulas=0
- 04. `Info_Plate` — visible, XFD103, nonempty=2610, formulas=0
- 05. `Data_Common` — visible, EE990, nonempty=16395, formulas=2442
- 06. `Data_Misc` — visible, BB413, nonempty=4323, formulas=385
- 07. `Data_FE` — visible, GK590, nonempty=12368, formulas=741
- 08. `Data_FE_Copeland` — visible, GK590, nonempty=12388, formulas=741
- 09. `Data_FE_LG` — visible, GK590, nonempty=12388, formulas=741
- 10. `Data_ERV` — visible, W64, nonempty=510, formulas=0
- 11. `Data_GE` — visible, GA500, nonempty=10349, formulas=583
- 12. `Data_JE` — visible, ET583, nonempty=11633, formulas=615
- 13. `Data_38AX` — visible, CM301, nonempty=3826, formulas=48
- 14. `worksheet color index` — visible, A5, nonempty=5, formulas=0
- 15. `Releaser Check List` — visible, H41, nonempty=243, formulas=0
- 16. `Engineer Check List` — visible, J15, nonempty=119, formulas=0
- 17. `Info_Plate_Special_Order` — visible, , nonempty=0, formulas=0
- 18. `Notes` — visible, A10, nonempty=4, formulas=0
- 19. `Data_GasFE` — visible, AM161, nonempty=3560, formulas=772
- 20. `Data_GasGE` — visible, AM159, nonempty=3540, formulas=1092
- 21. `Data_GasJE` — visible, AM159, nonempty=3540, formulas=1134
- 22. `FIOPList_FEStd` — visible, AI1155, nonempty=29797, formulas=25366

## Migration helper files
- `migration_sheet_map.csv`: first-pass classification of sheets as UI, lookup data, QC/documentation, or batch control.
- `vba_sheet_references.csv`: how often each sheet name is referenced in extracted VBA.
- `vba_named_range_references.csv`: named ranges sorted by likely VBA relevance.
- `vba_literal_worksheet_calls.csv` and `vba_literal_range_calls.csv`: raw VBA calls found by regex.
