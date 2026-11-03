# Carrier Internship — Engineering & Automation Projects

A collection of tools developed during a Carrier internship to support engineering workflows, product validation, data analysis, and internship operations.

The projects range from Excel/VBA utilities to Python desktop applications, Flask and Django web tools, and an Electron dashboard. They share a practical focus: turning spreadsheet, document, and engineering data into repeatable workflows with clearer results.

## Explore the projects

| Area | Project | What it does |
|---|---|---|
| Engineering planning | [Design Hour Estimator](APRIL/DESIGN%20HOUR%20ESTIMATOR/README.md) | Estimates modeling, detailing, and BOM hours from product, qBOM, complexity, and team data; generates scheduled task lists for Asana. |
| Quote automation | [ETO Quote Automation](FEBRUARY/ETO%20AUTOMATATION%20PROJECT/README.md) | Extracts ETO alert PDFs, groups materials by tumbling number, and creates Asana tasks with notes, fields, and attachments. |
| Product configuration | [SAP Configuration & Price Comparator](JULY/SAP%20VC%20COMPARISON%20TOOL/README.md) | Builds configuration matrices and associates catalog-number options with base-unit and option prices from pricing documents. |
| Engineering quality | [AHUQ](JULY/SELF-SERVICE%2039MBL%20KMAT%20cost%20breakdown%20tool/AHUQ-main/README.md) | Compares DXF geometry, displays visual differences, tests xPloder rules, and supports XML queries. |
| BOM validation | [ValidateSAP](SEPTEMBER/L1s%20TOOL/README.md) | Validates pasted BOM and SAP data, classifies parts as Add, Delete, or No Change, and saves comparison history as CSV. |
| Electrical calculations | [Wolong Nameplate Tool](MAY/Woolong/wolong_flask_step12/README.md) | Migrates an Excel/VBA nameplate workflow into model parsing, electrical-load calculations, MCA/MOCP results, and a Flask interface. |
| Warranty analytics | [AI Warranty Defect Classifier](AI_LLM_DEFECTS/README.txt) | Uses local language models to classify warranty claims, supports human review, and includes model-comparison and accuracy-analysis scripts. |
| Quality follow-up | [Turnback Notification System](MARCH/TURNBACK%20NOTIFICATION%20SYSTEM) | Matches turnback records to employees, summarizes monthly results, and prepares or sends notifications through Outlook. |
| Engineering administration | [L0 Project Processor](MARCH/L0%20auto) | Processes L0 meeting workbooks through a desktop interface, including worksheet formatting and dropdown-validation rules. |
| Workbook validation | [L1 Validation Workbooks](JANUARY/l1%20validation%20tool) | Contains Excel-based L1 validation and Add/Delete workflows, together with related input workbooks. |
| BOM comparison | [MCN Tool Updates](APRIL/MCN%20TOOL%202.0%20UPDATES) | Contains macro-enabled BOM comparison revisions and engineering-variant and plant-BOM reference workbooks. |
| Event operations | [Carrier Week Label Printer](AUGUST/CARRIER%20WEEK%20PRINTING%20TOOL/README.md) | Imports event-registration workbooks, maintains a student database, previews labels, and prints through Windows printer drivers. |
| Internship operations | [Intern Program Dashboard](OCTOBER/INTERNS%20DASHBOARD/README.md) | Connects to desktop Excel for interactive charts, intern records, filters, and internship-duration tracking through a Node.js/Electron interface. |

## Engineering workflow highlights

### From engineering estimates to scheduled tasks

The Design Hour Estimator uses reference workbooks and qBOM data to calculate design effort. Its companion desktop application turns saved projects into editable task lists, schedules work within each qBOM, and supports Asana CSV export and API integration.

### From documents to structured engineering data

ETO Quote Automation converts PDF reports into grouped task records. The SAP comparator reads pricing-document tables and maps catalog positions to configured options. Both projects focus on extracting useful structure from documents that would otherwise require manual review and entry.

### From workbook rules to application logic

ValidateSAP brings a paste-and-validate workflow into Django with explicit input checks and mutually exclusive action categories. The Wolong project progressively ports nameplate and electrical calculations from VBA into Python, with a workflow for comparing results against Excel expectations. Its supported model families and calculation limitations are documented in the project.

### From engineering files to inspectable differences

AHUQ compares drawing geometry rather than raw DXF text and provides overlays for reviewing differences. Related DXF experiments and earlier AHUQ versions are available under `MARCH/`.

## Repository layout

The month folders preserve the working organization of the collection. Each application is an independent project with its own dependencies and data requirements.

```text
.
├── AI_LLM_DEFECTS/    Warranty classification, model evaluation, and analysis
├── JANUARY/           L1 validation workbooks and input examples
├── FEBRUARY/          ETO PDF-to-Asana automation
├── MARCH/             AHUQ, DXF experiments, turnback notifications, L0 processing
├── APRIL/             Design-hour estimation and MCN comparison workbooks
├── MAY/               Wolong workbook analysis and Flask migration
├── JULY/              SAP configuration/pricing and 39MBL cost-breakdown resources
├── AUGUST/            Carrier Week / Carrier Day label printing
├── SEPTEMBER/         L1 and SAP validation web application
├── OCTOBER/           Intern Program dashboard and desktop interface
└── legacy_sources/    Additional source variants and older integration examples
```

Some folders contain earlier versions or `Copy` variants. Start with the linked project documentation when choosing an application entry point.

## Getting started

Clone the collection, then work from the directory of the application you want to run:

```powershell
git clone https://github.com/Mauro-MG/CARRIER-INTERNSHIP.git
cd CARRIER-INTERNSHIP
```

### Example: Design Hour Estimator

This project documents Python 3.10 or newer as its minimum requirement.

```powershell
cd "APRIL\DESIGN HOUR ESTIMATOR"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python app.py
```

The application opens a browser and selects an available local port starting at `5000`. To launch the companion task-generation desktop interface instead:

```powershell
python asana_task_app.py
```

Other projects have different entry points. Use their own dependency manifests and setup instructions rather than installing the entire collection into one environment.

### Application entry points

Run these commands from the corresponding project directory after completing its setup.

| Application | Entry point | Additional setup |
|---|---|---|
| ETO Quote Automation | `python app.py` | Asana credentials, project identifiers, and PDF ingestion configuration. |
| SAP Configuration & Price Comparator | `python appV2.py` | Product configurations and a compatible pricing DOCX; the earlier interface uses `app.py`. |
| Wolong Nameplate Tool | `python app.py` | Lookup tables and a supported model number; see the project validation examples. |
| AI Warranty Defect Classifier | `python app.py` | Ollama and the selected model; database access for SQL-backed workflows. |
| Turnback Notification System | `python turnbackn.py` | Input workbooks; Windows and configured Classic Outlook for email integration. |
| L0 Project Processor | `python L0_AUTOMATION.py` | The expected L0 meeting and source workbook layouts. |
| Carrier Week Label Printer | `python app.py` | Label artwork, registration data, and an installed Windows printer driver. |
| ValidateSAP | `python manage.py runserver` | Python dependencies and `DJANGO_SECRET_KEY` in the process environment. |
| Intern Program Dashboard | `npm start` or `npm run desktop` | Node.js, Python dependencies, Windows, and an open workbook in desktop Excel. |

## Configuration and data

Application configuration is project-specific. Use `.env.example` files where provided, and check whether the selected application loads a `.env` file or expects variables in the process environment.

| Integration | Configuration to check |
|---|---|
| Asana | Token, workspace/project identifiers, and required custom-field mappings. ETO tools use `ASANA_TOKEN`; the Design Hour Estimator uses `ASANA_ACCESS_TOKEN`. |
| SQL-backed warranty analysis | `DB_SERVER`, `DB_DATABASE`, `DB_USERNAME`, and `DB_PASSWORD`, plus an appropriate SQL Server ODBC driver. |
| Flask sessions | `FLASK_SECRET_KEY` for applications that read it. |
| Django validation app | `DJANGO_SECRET_KEY`; optional host and debug settings are defined in `config/settings.py`. |
| Excel / Outlook automation | Installed desktop applications, the expected workbook structure, and access to the relevant files or account. |
| Label printing | Printer selection, label dimensions, and artwork in the label-printer configuration. |

Workbook sheet names, column headers, lookup tables, and folder layouts are part of several tools' input contracts. Follow the individual README before replacing reference data or supplying new files. Macro-enabled workbooks require desktop Excel with the necessary macro settings.

## Technologies

- **Python:** data processing, document extraction, local services, desktop interfaces, and engineering calculations.
- **Flask and Django:** browser interfaces, ingestion endpoints, and validation workflows.
- **pandas and openpyxl:** spreadsheet transformation, reporting, and workbook operations.
- **Tkinter and ttkbootstrap:** desktop workflow tools.
- **JavaScript, Node.js, Electron, and Highcharts:** the Intern Program interface and charts.
- **Excel/VBA and Windows COM:** workbook-based engineering logic and desktop Excel/Outlook integration.
- **Ollama:** local language-model inference for warranty classification experiments.

Project READMEs contain the detailed input formats, supported workflows, build instructions, and available test commands.
