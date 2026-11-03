# RPA_ETO_QUOTES_AUTOMATION

# ETO Quote Automation – PDF → Asana Task Pipeline

## Overview

This project automates the processing of **ETO Alert Report PDFs** and converts them into structured **Asana tasks**.

The system receives PDFs via an HTTP API, extracts relevant information, groups parts by **tumbling number**, and automatically creates tasks in an **Asana project**, including custom fields, notes, and attachments.

This eliminates manual entry and ensures consistent task creation.

---

# Architecture

The solution integrates several components:

```
Email → Power Automate → Flask API → PDF Extraction → Asana API
```

Detailed flow:

```
Email with PDF
        ↓
Power Automate Flow
        ↓
HTTP POST request
        ↓
Flask API (/ingest endpoint)
        ↓
PDF Parsing (pdfplumber)
        ↓
Data normalization & grouping
        ↓
Asana Task Creation
        ↓
Attach original PDF
```

---

# Key Features

### Automated PDF Processing

* Accepts PDF input via HTTP POST
* Validates file type and format
* Supports raw PDF bytes or Base64 encoded payloads

### Intelligent Data Extraction

Uses `pdfplumber` to extract:

* Header information
* Material numbers
* Catalog numbers
* Distributor text
* Quantity
* Tumbling numbers

### Grouping Logic

Items are grouped by **tumbling number** to ensure:

* One Asana task per tumbling
* All related materials included in task notes

### Asana Integration

Automatically:

* Creates tasks in the specified project
* Populates custom fields dynamically
* Assigns tasks based on product type
* Uploads the original PDF as an attachment

### Automated File Retention

PDF files are temporarily stored in:

```
incoming_pdfs/
```

A cleanup function removes files older than **7 days**.

---

# Repository Structure

```
.
├── app.py
├── pdf_extraction.py
├── asana_client.py
├── incoming_pdfs/
└── README.md
```

### app.py

Main Flask API service.

Responsibilities:

* Accept HTTP requests
* Validate input
* Trigger PDF processing
* Create Asana tasks
* Attach files

### pdf_extraction.py

Contains all PDF parsing logic including:

* Line item extraction
* Header extraction
* Tumbling detection
* Item grouping

### asana_client.py

Handles all Asana interactions:

* Fetch project custom field settings
* Map field names to IDs
* Create tasks
* Upload attachments

---

# API Specification

## Endpoint

```
POST /ingest
```

## Headers

| Header       | Description                 |
| ------------ | --------------------------- |
| Content-Type | `application/pdf`           |
| X-API-KEY    | Optional authentication key |
| X-Filename   | Optional original filename  |

---

## Request Body

Raw PDF bytes.

Example using curl:

```bash
curl -X POST http://SERVER_IP:5000/ingest \
  -H "Content-Type: application/pdf" \
  --data-binary "@report.pdf"
```

---

## Response

Example response:

```json
{
  "ok": true,
  "file_saved": "incoming_pdfs/20260305_101200__report.pdf",
  "header_info": {},
  "items_all_count": 52,
  "items_unique_count": 6,
  "tasks_created": [
    {
      "gid": "123456789",
      "name": "38421",
      "attachment_gid": "987654321"
    }
  ]
}
```

---

# Requirements

Python version:

```
Python 3.11+
```

Required packages:

```
Flask
pdfplumber
requests
tzdata
```

---

# Running the API

Development mode:

```bash
python app.py
```

Server will start on:

```
http://0.0.0.0:5000
```

---

# Production Deployment

For production environments, run the application using **Waitress** instead of Flask’s development server.

Install:

```bash
pip install waitress
```

Run:

```bash
waitress-serve --host=0.0.0.0 --port=5000 app:app
```

---

# Environment Variables

The application supports configuration via environment variables.

| Variable               | Description                         |
| ---------------------- | ----------------------------------- |
| ASANA_TOKEN            | Asana personal access token         |
| ASANA_PROJECT_GID      | Target Asana project                |
| ASANA_AHU_USER_GID     | Default assignee for AHU            |
| ASANA_ROOFTOP_USER_GID | Default assignee for rooftop units  |
| API_KEY                | Optional API authentication key     |
| UPLOAD_DIR             | Directory for temporary PDF storage |

Example:

```
ASANA_TOKEN=xxxx
ASANA_PROJECT_GID=xxxx
API_KEY=my_secret_key
```

---

# Deployment Considerations

## Network Access

The API must be reachable by the Power Automate workflow.

Possible approaches:


# Logging and Debugging

Errors during extraction or Asana interaction return detailed JSON responses and stack traces in server logs.

Example:

```
PDF extraction failed
Asana API request failed
Invalid file format
```

---

# Future Improvements

Possible enhancements:

* Async task processing (Celery or Redis queue)
* Docker containerization
* CI/CD deployment pipeline
* Structured logging
* Monitoring and alerting
* Serverless deployment (AWS Lambda + API Gateway)

---

# License

Internal project – Carrier Corporation.

