# SAP Product Configuration and Price Comparator

A local Flask application for building product configuration matrices and extracting Carrier base-unit and option pricing. Version 2 analyzes Carrier pricing DOCX files directly from WordprocessingML XML tables so base-unit rows, option codes, size columns, voltage rows, and master prices can be located more reliably than from PDF geometry. All processing is local and uploaded DOCX files exist only as temporary files during a request.

## Requirements and setup

Python 3.11 or 3.12 is recommended.

```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Run the application

```powershell
.venv\Scripts\Activate.ps1
python appV2.py
```

Open `http://127.0.0.1:5001`. Create or select a saved product configuration, enter a complete catalog number, upload the Carrier pricing DOCX, and click **Extract option prices**.

For the legacy SAP/PDF comparator, run `python app.py` and open `http://127.0.0.1:5000`.

## Run tests

```powershell
python -m pytest
```

## DOCX price association

The appV2 extractor reads `word/document.xml` from the uploaded `.docx`, extracts Word tables, and performs two independent lookups:

- Base Unit Master Price: an optional per-product rule derives the DOCX base-unit search key from the complete SAP catalog number, then searches table cells and reads the value from the detected `MASTER PRICE` / `LIST PRICE` column.
- Option/component prices: `POSITION` sections map catalog-position characters through the saved configuration matrix to option codes, then select document values by size column and voltage row.

It reports numeric prices separately from standard, dash, unavailable, not-found, ambiguous, invalid-price, and condenser-structure mismatch diagnostics.

## Base Unit Master Price rules

Old configurations without a `base_unit_price_rule` still load as base-unit extraction disabled. New configurations can enable either:

```json
{
  "base_unit_price_rule": {
    "enabled": true,
    "search_type": "range",
    "start_position": 1,
    "end_position": 9
  }
}
```

or:

```json
{
  "base_unit_price_rule": {
    "enabled": true,
    "search_type": "full_search",
    "template": "{1:4}-{6:10}--{13}---0"
  }
}
```

All positions are 1-based and inclusive. The template language is deliberately small and safe: `{13}` selects character 13, `{1:4}` selects characters 1 through 4, and all text outside braces is copied as a literal.

## Current limitations

- appV2 supports DOCX pricing input only.
- PDF extraction for appV2 was removed because the 30MP tables are more reliable in DOCX XML than in PDF text geometry.
- The older `app.py` PDF comparator remains as legacy code for now.
- DOCX extraction depends on real Word tables. Tables built from screenshots, floating text boxes, or heavily manual spacing may still need special handling.
- Detection is exact after case and whitespace normalization. No fuzzy match is automatically accepted.
- A single option code may appear in multiple DOCX rows; appV2 currently returns each matching priced component.
- No database, authentication, permanent uploads, or external processing is used.
- Upload size is limited to 25 MB. Processing very large DOCX files remains request-bound and may take time.
