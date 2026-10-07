# Data Import API Handoff Document

This document provides the frontend integration specifications for the Universal CSV Data Import Engine.

## Overview

The data import process is broken into a predictable lifecycle:
`UPLOAD (pending) -> VALIDATE (validated + preview) -> EXECUTE (completed/failed)`

## Available Endpoints

All endpoints require authentication and the `data_import.view` or `data_import.execute` permission.

---

### A. List Templates
**GET `/api/v1/data-import/templates/`**
**Permission:** `data_import.view`

Returns a list of all 9 supported CSV templates and their schemas.

**Response (200 OK):**
```json
[
  {
    "key": "employees",
    "display_name": "Employees",
    "filename": "employees_template.csv",
    "description": "...",
    "version": "1.0",
    "headers": ["employee_code", "first_name", "..."],
    "fields": [
      {
        "csv_header": "employee_code",
        "type": "string",
        "required": true,
        "description": "Unique employee identifier"
      }
    ]
  }
]
```

---

### B. Download Template
**GET `/api/v1/data-import/templates/{key}/download/`**
**Permission:** `data_import.view`

Downloads a ready-to-use UTF-8 encoded CSV file with the exact required headers.
Returns `text/csv` with `Content-Disposition: attachment`.

---

### C. Create Job (Upload)
**POST `/api/v1/data-import/jobs/`**
**Permission:** `data_import.execute`
**Format:** `multipart/form-data`

Initiates a new import job. The job is created in the `pending` state. No validation occurs yet.

**Request:**
- `template_key`: string (e.g. `"employees"`)
- `file`: File object (the CSV file)

**Response (201 Created):**
```json
{
  "id": "uuid",
  "template_key": "employees",
  "status": "pending",
  "original_filename": "data.csv",
  "total_rows": 0,
  "valid_rows": 0,
  "created_count": 0,
  "updated_count": 0,
  "error_count": 0,
  "started_at": null,
  "completed_at": null,
  "created_at": "2026-10-06T12:00:00Z",
  "preview_data": []
}
```

---

### D. Validate & Preview
**POST `/api/v1/data-import/jobs/{id}/validate/`**
**Permission:** `data_import.execute`

Parses the CSV, catches type errors, validates headers, and generates a 5-row preview. The database domain records are **NOT** mutated.

**Response (200 OK):**
Same as Job object, but `status` will be `validated`. `total_rows` will be populated, and `preview_data` will contain up to 5 rows of parsed JSON for frontend display.

```json
{
  "id": "uuid",
  "status": "validated",
  "total_rows": 100,
  "preview_data": [
    {
      "row": 1,
      "status": "ok",
      "data": {
        "employee_code": "EMP001",
        "first_name": "John"
      }
    },
    {
      "row": 2,
      "status": "error",
      "error": "Value must be >= 0."
    }
  ],
  ...
}
```

*Note: If the file is malformed, too large, or headers don't match, this returns `400 Bad Request` with an `error` string.*

---

### E. Execute
**POST `/api/v1/data-import/jobs/{id}/execute/`**
**Permission:** `data_import.execute`

Commits the valid rows to the database. Operations are atomic per-row using transaction savepoints. Invalid rows are recorded as errors.

**Response (200 OK):**
Job object with `status` transitioned to either `completed` or `completed_with_errors`. Counters will be populated.

---

### F. Error Reporting
**GET `/api/v1/data-import/jobs/{id}/errors/`**
**Permission:** `data_import.view`

If a job completes with errors, this endpoint returns the row-level error details.

**Response (200 OK):**
```json
[
  {
    "row_number": 42,
    "field": "payment_mode",
    "error_type": "invalid_enum",
    "message": "Value must be one of: BANK_TRANSFER, CHEQUE, CASH.",
    "row_data": {"employee_code": "EMP042", "payment_mode": "bitcoin"}
  }
]
```

## Recommended Frontend State Flow

1. **SELECT TEMPLATE**: User selects template from List API.
2. **DOWNLOAD TEMPLATE**: Optional download if user needs a blank template.
3. **SELECT FILE**: Client-side file selection.
4. **UPLOAD**: Call Job Creation API (POST `/jobs/`). Returns Job ID.
5. **VALIDATE**: Call Validate API (POST `/jobs/{id}/validate/`).
6. **PREVIEW**: Show `preview_data` to user and confirm they want to proceed.
7. **EXECUTE**: Call Execute API (POST `/jobs/{id}/execute/`).
8. **RESULT**: Display success metrics. If errors > 0, fetch and display Error API results.
