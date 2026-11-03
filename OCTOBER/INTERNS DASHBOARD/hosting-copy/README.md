# Intern Program

The primary interface is now a Node.js HTML app with Highcharts. The existing Python logic stays in its original files: `excel_store.py` owns the desktop Excel connection, `dashboard_data.py` owns filters, metrics, counts, and recent-record ordering, and `workbook_store.py` retains the local workbook operations. `app.py` is preserved as the original Tkinter view.

## Run the new interface

The packaged app requires Windows x64 and desktop Excel. It includes Node/Electron, Python, Highcharts, and the Excel integration. No separate Node.js or Python installation is needed to run the `.exe`.

For development, use Node.js 22.12 or newer (Node 24 LTS recommended) and Python with the existing dependencies.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
npm install
```

For the Windows desktop app, run the installer or portable executable from `release/`. **Start App.cmd** opens the packaged desktop app when `release/win-unpacked` is present, and otherwise starts the browser view. `npm run desktop` starts the Electron development window. `npm start` retains the original browser workflow at **http://127.0.0.1:3210**, and `npm run serve` starts it without opening a browser. Keep the terminal open for browser mode; press Ctrl+C there to stop it. The desktop edition manages the server and Python process automatically.

The server prefers `.venv\Scripts\python.exe`. To use another interpreter, set `DASHBOARD_PYTHON` to its executable path before launching. Set `PORT` to change the local port. The server accepts the displayed `127.0.0.1` address and listens only on the local computer.

1. Open the original SharePoint workbook in desktop Excel using your company account.
2. Select its data worksheet, then click **Connect to Excel** in the dashboard.
3. Check the workbook path and worksheet shown below the dashboard.
4. Use the five filters or **Clear filters**. Metrics, all five Highcharts graphs, and the recent-interns table use the original Python calculations.
5. Click **Refresh** after changes in Excel. Refresh stays bound to the connected workbook path and worksheet, even if you switch to another workbook in Excel. Click **Connect to Excel** again to connect to a different active workbook.

Use the sidebar to switch between the read-only Dashboard and Intern management. Intern management lets you create, read, update, and permanently delete interns in the connected workbook, without an application login. Excel remains responsible for saving, query refresh, and SharePoint synchronization. The app does not open or close workbooks. If a read fails, the last loaded dashboard remains visible.

The dashboard recognizes the same English and Spanish headers, including `Full Name` / `Nombre`, `University` / `Universidad`, `Fecha de Ingreso`, `Género`, and `Carrera`. Missing fields remain empty. Limits, date conversion, counting, filtering, and recent-record ordering retain their existing behavior.

Highcharts and its accessibility and empty-state modules are installed locally through the pinned npm dependency. The interface does not need a chart CDN or send workbook data to a chart service. Highcharts production/commercial use requires the appropriate [Highcharts license](https://www.highcharts.com/download/).

## Desktop architecture and Windows packaging

```text
Electron window: HTML / CSS / Highcharts
        | local HTTP
Node.js server.js
        | JSON lines over a private child-process pipe
Bundled InternBackend.exe / dashboard_bridge.py adapter
        | direct calls
Existing dashboard_data.py + excel_store.py
```

Node.js serves assets and forwards requests; the Python child keeps the connected snapshot and performs the existing dashboard calculations. Excel reads and management writes are serialized in that child. New management logic is additive in `intern_management.py` and `excel_management.py`; the original dashboard and storage modules are unchanged.

The Electron desktop window hosts the same HTML interface. PyInstaller bundles the existing Python modules and pywin32 into `InternBackend.exe`; Electron Builder includes that executable and runtime, Highcharts, and the UI assets in both a per-user NSIS installer and a standalone portable launcher. Desktop mode uses an available local port, so it can coexist with the browser edition. Normal shutdown drains outstanding backend requests before sending EOF and closing the server. Closing the app leaves Excel open.

Build on Windows x64:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-build.txt
npm install
npm run package:win
npm run verify:package
```

The pinned `pnpm-lock.yaml` is also provided; `pnpm install --frozen-lockfile` can replace `npm install`. **Build Windows App.cmd** runs the build once dependencies are installed. `npm run package:dir` builds an unpacked app for testing, and `npm run build:backend` builds/verifies only the frozen backend. Set `DASHBOARD_BUILD_PYTHON` to an absolute interpreter path to build from a different Python environment. Windows builds must run on Windows; the resulting package does not depend on that build interpreter's location.

Deliverables:

- `release/Intern-Program-1.0.0-Setup.exe`: installer with desktop and Start menu shortcuts, optional installation folder selection, and normal uninstall support. It installs for the current user without requiring administrator privileges.
- `release/Intern-Program-1.0.0-Portable.exe`: move/distribute this single `.exe`; it extracts its bundled runtime when launched.
- `release/win-unpacked/`: complete unpacked desktop application for diagnostics. All files in this folder must stay together; copying only its `Intern Program.exe` is insufficient.
- `release/build-manifest.json`: runtime and build-tool versions used for this build.

Builds are unsigned by default (`win.signExecutable: false`); production signing can be enabled in `electron-builder.cjs` with the organization's signing configuration. The build does not publish or upload packages. The desktop distribution includes runtime license texts and the Highcharts license notice. Desktop Excel, workbook permissions, and appropriate Highcharts licensing remain external requirements.

The package uses an explicit source/asset allowlist. Workbook files, backups, test fixtures, `.venv`, credentials, and development caches are excluded. Verification checks package contents, frozen COM imports, JSON protocol, all five Highcharts graphs, the management form, absence of login, and backend process cleanup after normal exit. Application regression tests cover registration, editing, history, duration, and migration with disposable workbooks.

Desktop settings and logs live in the user's application-data directory, outside the installation or portable extraction folder. Use **File > Open settings folder** to find `settings.json` and `desktop.log`. Example optional settings:

```json
{
  "fieldMap": {},
  "backupDirectory": null
}
```

Populate `fieldMap` with the canonical-to-header mapping described below. `backupDirectory` can name an absolute writable folder; `null` retains the existing backup location. Existing `DASHBOARD_FIELD_MAP` and `DASHBOARD_BACKUP_DIR` environment overrides still take precedence. Settings and workbook backups are retained when uninstalling the desktop app.

## Original interface and storage utilities

Run `python app.py` to use the preserved Tkinter dashboard with the same installed Python dependencies. `workbook_store.py` still provides the earlier local `.xlsx` read/append utilities; there is no local-file editor in either current dashboard view.

The existing storage safeguards are unchanged: literal text writes, workbook identity/digest checks, local backups, read-only/protected-sheet checks, and supported table/layout limits. They do not provide a distributed lock or certify cloud synchronization.

## Validation

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
npm test
```

Tests cover original dashboard behavior, calendar-month boundaries/leap years, workbook migrations, durable XLSX fixture writes, edits that preserve other fields/formulas, departing-intern history, stale snapshots, literal text, direct management access without login, and request boundaries. A live connection additionally requires an open, saved workbook in desktop Excel. Automated persistence checks use disposable Excel-object-model fixtures backed by XLSX files, rather than modifying the live SharePoint workbook.

## Intern management

No application login or credential setup is required. Registration, editing, workbook setup, and complete record details are available directly on this computer. The server retains its local-only address and same-origin request checks. Excel/SharePoint permissions govern workbook access.

1. Start the app and connect to Excel.
2. Select **Review workbook setup** to inspect missing columns. **Prepare workbook** applies the additive migration with a workbook backup first. This setup does not run automatically against the live workbook.
3. **Add intern** captures personal, internship, academic, emergency-contact, insurance, and other existing fields. Full name and start date are required; the other information is optional. New interns appear immediately in the table with a search for their name.
4. **Edit** saves only changed fields, preserving all other existing information. Record keys and the legacy Months field cannot be edited. Cells containing formulas are protected from app writes.
5. To record a departure, edit **Internship status** to **Completed** or **Inactive** and supply the actual end date. The intern leaves the Active directory but stays in Completed/Inactive, Former interns, and All records.
6. **Delete** permanently removes that intern’s row from the connected workbook after confirmation. A recovery backup is created before the deletion; use that backup to restore a record if it was deleted by mistake.
6. Search by name, university, department, role, supervisor, or other visible fields. Sort by name, start date, or duration, in either direction. The table scrolls horizontally; **View details** exposes the complete record, including personal contact, emergency-contact, insurance, and other administrative information. The table itself uses a compact set of internship columns.

The original dashboard continues to summarize all connected workbook rows, including former interns; its calculations have not been moved or changed. The directory defaults to Active. Legacy blank statuses are interpreted as Active, and missing end dates on old former records display an unknown duration until corrected.

## Automatic Months as Intern

The numeric duration is computed on each directory/details request from the start date. Active interns use today's date in `America/Mexico_City`; Completed/Inactive interns use their recorded end date. The table checks for a new local calendar day every minute and updates when returning to the page. Refreshes and new sessions recalculate the value; it is never written as a manually maintained field.

Completed months are calendar anniversaries. If the original day does not exist in the target month, the anniversary is the month's last day: January 31 to February 28 counts as one completed month, and February 29 to the following February 28 counts as twelve. Remaining days are measured from that anniversary. Missing/invalid dates show a reason; future start dates show zero months and “Not started.” Former records with an invalid/missing end date remain unknown rather than growing indefinitely.

The workbook's existing `Months` column is preserved as historical information and ignored by the dynamic calculation. Management date writes use actual Excel dates in its 1900 date system, so the existing dashboard date handling continues to work. Date writes to a workbook using the 1904 system are rejected.

## Field mapping and migration scripts

Mapping uses normalized exact English/Spanish aliases. In the current workbook, `Area` maps to department, `Inter ID` remains the original business ID, `Fecha de Finalización IRPAC` maps to internship end date, and `Número Teléfonico` maps to emergency-contact phone. Confirm those meanings for your organization. Personal phone, semester, insurance expiration, status, and any other missing canonical fields are appended; existing columns are not renamed or removed. A separate `Intern Record Key` supplies stable identity without changing existing business IDs.

To override an ambiguous column, create a JSON field map and set `DASHBOARD_FIELD_MAP` before starting. For example, if the generic phone column is personal rather than emergency:

```json
{
  "phone": "Número Teléfonico",
  "emergency_phone": "Emergency contact phone"
}
```

Each override must name an existing exact workbook header, and one column cannot be assigned to two fields. Add the intended emergency-phone header in Excel before using that example. The directory reports the chosen mapping in each field's schema; invalid/ambiguous mappings fail explicitly. Other original columns (birth date, gender, manager, graduation dates, insurance-coverage indicator, and other administrative fields) remain available in details and forms.

The migration can also be previewed from the terminal:

```powershell
.\.venv\Scripts\python.exe scripts/migrate_workbook.py
.\.venv\Scripts\python.exe scripts/migrate_workbook.py --apply
```

The preview is read-only; `--apply` explicitly applies the migration. Re-running a completed migration makes no changes. Duplicate record keys require correction in Excel. New columns cannot overlap adjacent data. Backups use the existing `%LOCALAPPDATA%\ExcelConnectionTester\backups` directory, or `DASHBOARD_BACKUP_DIR` if configured. Digest checks reject stale forms/workbooks before writing. If Excel fails during a mutation/save, the error identifies the backup and asks you to inspect and refresh; the app does not automatically retry or roll back changes that AutoSave may have propagated.

## Added and modified files

- `desktop/main.js`, `desktop/settings.js`: desktop window, bundled backend startup, settings, logging, and graceful shutdown.
- `electron-builder.cjs`, `packaging/`, `requirements-build.txt`: Windows installer/portable configuration, backend freezing, icons, runtime licenses, and user guide.
- `scripts/build_windows.js`, `scripts/verify_package.js`, `scripts/desktop.js`, `Build Windows App.cmd`: reproducible build, package verification, and development launch.
- `intern_management.py`: canonical field mapping, validation, directory querying, and dynamic duration.
- `excel_management.py`: additive migration and guarded create/update/delete writes over the original Excel connection.
- `scripts/migrate_workbook.py`: migration preview/application.
- `server.js`, `dashboard_bridge.py`: extend the existing HTTP/JSON-lines adapter with local management actions.
- `public/index.html`, `public/app.js`, `public/management.js`, `public/management.css`: directory, dialogs, forms, and dashboard update integration.
- Tests, `package.json`, `.gitignore`, and this README: validation and configuration documentation.

The original `app.py`, `dashboard_data.py`, `excel_store.py`, and `workbook_store.py` remain unchanged.
