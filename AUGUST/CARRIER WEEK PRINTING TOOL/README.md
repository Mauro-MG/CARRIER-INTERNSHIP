# Student Label Printer

Local Windows desktop application for importing Carrier Week and Carrier Day Microsoft Forms response workbooks, maintaining an Excel master database, previewing labels, and printing through an installed Windows printer driver.

## Setup

```powershell
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python app.py
```

Place the university label artwork at `assets/label_template.png`. It should ideally be 799 × 400 pixels, though the renderer resizes it to the configured dimensions. Optional custom bold font: `assets/fonts/DejaVuSans-Bold.ttf`.

Printer selection and label text positions are stored in `config.json`. After testing on the Ribetec RT-420BE, calibrate label pixel dimensions, text coordinates and font sizes in that file, then adjust the Windows printer driver's stock size, orientation, margins, darkness, and speed.

`database\students.xlsx` may contain Power Query/OneDrive-connected sheets named `Students - Carrier Day` and `Students - Carrier Week`. Use **Refresh Database** in the app to ask Microsoft Excel to refresh all connections, wait for the queries, save the workbook, and reload the student list. Microsoft Excel must be installed and the workbook must not already be open. Each source has its own stable app ID sequence starting at 1; the mapping to the original Forms `Id` is stored in `database\student_id_map.json`. Print history is stored separately in `database\print_history.json` so refreshing query results cannot erase it.

The application sends a raster image through the normal Windows GDI printer path. The Ribetec (or another thermal printer) must already be installed in Windows with a working driver and correct label stock configured.

## Build the Windows executable

Build from the project directory:

```powershell
.\build_exe.bat
```

The script creates an isolated `.build-venv` environment and installs only the required application and packaging dependencies. Internet access is required the first time it runs.

The portable application is created at `dist\StudentLabelPrinter\StudentLabelPrinter.exe`. Copy and distribute the entire `StudentLabelPrinter` folder. Libraries and bundled assets are kept under `_internal`; the writable `database` folder and `config.json` remain beside the executable. The build script copies the current `students.xlsx`, stable ID mapping, and print history into the distribution.

Keep the distributed folder in a user-writable location such as the Desktop or Documents. The application saves `config.json`, `database`, `logs`, and `temp` beside the executable, so installing it under `C:\Program Files` would require a future change to use `%LOCALAPPDATA%` for writable data.
