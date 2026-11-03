# Design Hour Estimator

A local Flask application for estimating engineering design hours from product-family, qBOM, part, complexity, and team data.

## Requirements

- Python 3.10 or newer
- `pip`

## Run locally

```powershell
git clone https://github.com/Mauro-Montelongo_carrier/DESIGN-HOUR-ESTIMATOR.git
cd DESIGN-HOUR-ESTIMATOR
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python app.py
```

The app selects an available port starting at `5000` and opens it in your default browser. If the browser does not open automatically, use the local URL printed in the terminal.

## Run the Asana CSV desktop app

```powershell
python asana_task_app.py
```

Use **Generate from project** to choose a saved project `.csv`, `.xlsx`, or `.xlsm`. The app generates task rows from the project qBOM references in the background, lets you review and edit tasks, supports bulk updates, and exports an Asana-ready CSV.

Set the global **Start Date** in the **Project schedule** panel. Every qBOM starts on that same date as an independent parallel lane. Tasks stay sequential inside their own qBOM and use six working hours per Monday–Friday day; unused hours carry into the next task. Each generated row receives the date on which its cumulative qBOM hours finish. If whole-hour reconciliation displays a task as `0`, the app calculates `ceil(decimal hours × 60)` and exports the result with its unit, such as `0.32 h → 20 min`; the same rounded-up duration is used in scheduling. A true source zero consumes no capacity and remains `0`. A weekend start rolls forward to Monday. The displayed **Target Date** is the latest qBOM completion date across the project and is intentionally kept out of the Asana CSV. Changing Start Date or a generated task's Estimated Time recalculates the schedule automatically.

Search covers every field. **Overview** emphasizes names, hours, labels and assignments; choose **All fields** to show every CSV column plus the reference-only Product value. Double-click a task or press Enter to open the tabbed editor. The boxed **Row selection** control selects every currently visible row. **Project** and **Labels** are single-select fields in the discovered Asana project; **Task Type** is multi-select and its **Choose** control supports checkbox selection. Batch scope can target **Selected rows**, **Visible rows**, or **All tasks**; clearing a field from all tasks requires confirmation. Batch edits can replace, add or remove Task Type values. **Undo** restores the last 30 table and option changes, including deletions and project loads.

Export scope is explicit: **All tasks** exports the complete list (including tasks hidden by filters); **Selected tasks** exports only the selection. The export button shows the row count and saves automatically into the `ASANA-UPLOADS` folder next to the app, without opening another file dialog. Every CSV also receives a `.manifest.json` file containing the exact canonical Asana schema, source-project trace, task count, scope, timestamp, and CSV SHA-256 hash. Sorting changes the displayed order only. A partial export keeps the “Not fully exported” indicator until all current tasks have been exported together.

**Needs review** highlights missing names, invalid dates/numbers, missing estimates, zero-hour tasks and manual estimates outside the whole-hour/40-hour rule. Missing names and invalid dates/numbers must be corrected before export. Zero-hour and manually adjusted numeric estimates are advisory; the UI does not recalculate them. The generator reconciles whole task hours to the rounded raw design total before applying the 40-hour split. The distinct BOM / BOM/WT task categories are unchanged.

Press **F1** or **Help** for keyboard shortcuts and selection/export behavior. Dropdown options are saved in `asana_task_options.json` next to the app or packaged `.exe`. When an Assignee email is added or renamed, the app checks only that email through Asana's single-user workspace endpoint; it never downloads the workspace user directory. This targeted check needs only the token and workspace ID in `.env`, so a missing discovery JSON does not block adding a valid email. When `asana_project_fields.json` is present, the app also caches the verified GID there for upload preflight; an unknown email is not added. **Save draft** creates a versioned, shareable `.asana-draft.json` file containing all task fields, internal qBOM schedule identity, Start/Target dates, dropdown options, source trace, schema, timestamp, and recent action names; **Open draft** restores it. The UI prompts before discarding unexported tasks.

UI/UX findings and verification are documented in [UI_UX_AUDIT.md](UI_UX_AUDIT.md). Run the desktop and calculation regression checks with:

```powershell
python -m unittest test_asana_ui.py test_asana_task_app.py test_asana_upload.py test_asana_api.py test_asana_user_lookup.py test_asana_field_discovery.py test_generate_estimated_tasks.py test_summary_totals.py
```

The exported CSV headers and field types are derived from one canonical schema. It uses `Name` and `Description` as task fields, `Assignee` as an Asana user email field, `Due Date` as a task date in `MM/DD/YYYY` format, and the remaining columns as matching Asana custom fields. `Target Date` is intentionally excluded because it is a project-level calculation and is not copied to every task. `Product` remains visible in the desktop table and drafts as generated reference data, but it is deliberately excluded from both CSV exports and API payloads because that field is blocked and must be set manually in Asana. The internal `BOM/WT` task category is exported with the Asana-compatible `WTPART` label.

## Discover Asana project fields

Fill in the local, Git-ignored `.env` file with `ASANA_ACCESS_TOKEN`, `ASANA_WORKSPACE_GID`, and `ASANA_PROJECT_GID`. `ASANA_SECTION_GID` is optional. Empty slots are also provided for each custom-field GID after the discovery results have been reviewed. Never commit or share this file; `.env.example` contains the safe blank template.

Run the read-only discovery utility:

```powershell
python discover_asana_project_fields.py
```

It writes `asana_project_fields.json` by default. The output includes project/workspace identity, sections, every project custom field, enum option GIDs, duration metadata, and suggested matches for the desktop app fields. The token is never written to the output. To capture the configured assignee GIDs and emails, use:

```powershell
python discover_asana_project_fields.py --include-users
```

This resolves only the emails listed under `Assignee` in `asana_task_options.json`; it no longer stores the entire workspace user directory. To test a smaller explicit set, repeat `--assignee-email`:

```powershell
python discover_asana_project_fields.py --include-users `
  --assignee-email JessicaJanett.Gonzalez@carrier.com `
  --assignee-email Eduardo.Solano@carrier.com
```

`ASANA_ASSIGNEE_EMAILS` in `.env` can also provide a comma-separated override. The JSON records resolved and unresolved configured emails under `user_lookup`.

Use `--output path.json` to choose another output file or `--env-file path` to load another local configuration.

## Upload tasks through the Asana API

Run discovery with `--include-users`, review the generated tasks, and use **Upload to Asana**. Before creating anything, the app performs a local preflight that validates every row and resolves custom-field, option, and assignee GIDs. Product is never resolved or sent. The app then shows the exact destination project, optional section, and task count for confirmation.

For the first real test, choose **Selected tasks**, select one task, and confirm the upload. Tasks are created sequentially with `POST /tasks`; when `ASANA_SECTION_GID` is configured, each task is then placed with the section endpoint while preserving row order. Every successful create is immediately recorded in `ASANA-UPLOADS/asana_upload_journal.json`, so retrying the same generated row skips the existing task. Every run also writes an `*_asana_upload_report.json` with task GIDs, links, failures, partial section placements, and uncertain network outcomes. Never delete the journal unless duplicate protection is intentionally being reset.

## Included application files

- `app.py` — Flask routes and application logic
- `asana_task_app.py` — ttkbootstrap desktop app for generating Asana CSV files
- `asana_task_widgets.py` — shared field controls and tabbed task editor
- `asana_upload.py` — offline Asana metadata validation and API request-preview builder
- `asana_api.py` — confirmed task creation, section placement, results, and duplicate journal
- `asana_user_lookup.py` — targeted single-email Assignee validation
- `estimator.py` — workbook loading and estimate calculations
- `templates/` — user-interface templates
- `Product Data/estimator_data_updated.xlsx` — estimator reference data

## Local data

The app creates `Project Files/Qboms` and `Project Files/Projects` when it starts. Saved estimates and backups in that directory are local user data and are intentionally excluded from Git.

To update estimator reference values, edit `Product Data/estimator_data_updated.xlsx` while preserving the expected `parts`, `sets`, and `hours` worksheets and their column names.

## Generate estimated-time tasks from a project

`generate_estimated_tasks.py` reads one saved project and locates every file named in its `QBomSaved` column. For the standard folder layout, place the project in `Project Files/Projects` and its qBOM CSV files in `Project Files/Qboms`.

```powershell
python generate_estimated_tasks.py "Project Files/Projects/MyProject.csv"
```

The default output is `MyProject_tasks.xlsx`. It contains:

- `Tasks` — the import-ready task rows. Whole hours are allocated across tasks so their sum equals the rounded raw design-hour total; rows above 40 hours are then split into capped rows with `_1`, `_2`, etc. added to the task name.
- `Components` — base qBOM hours plus the primary, secondary, and tertiary contribution for every task before rounding and splitting.
- `Audit` — the same contribution breakdown summarized by qBOM.

Use `--qbom-dir` for a different qBOM folder. When `--output tasks.csv` is used, the script also creates `tasks_components.csv` and `tasks_audit.csv`.

The quantity multiplier applied to every Modeling, Detailing, and BOM subtotal is:

```text
(Primary L1s Qty × 1) + (Secondary L1s Qty × 0.25) + (Tertiary L1s Qty × 0.10)
```

Excel project files are also supported. If the referenced qBOMs are worksheets in the same workbook, the script reads those sheets automatically.
