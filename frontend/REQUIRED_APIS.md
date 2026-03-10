# Required Backend APIs for Class Scheduler Pro

Base URL expected by frontend: `VITE_API_BASE_URL` (default: `http://localhost:5000/api`)

## 1. Upload APIs

### POST `/uploads/faculty-id-map`
Purpose: Upload Excel/CSV containing faculty name <-> faculty id mapping.

Request:
- Content-Type: `multipart/form-data`
- Body field: `file`

Response (200):
```json
{
  "fileId": "fmap_123",
  "fileName": "faculty-id-map.xlsx",
  "rowsParsed": 52,
  "message": "Faculty ID map uploaded successfully"
}
```

### POST `/uploads/subject-faculty-map`
Purpose: Upload subject-to-faculty mapped file.

Request:
- Content-Type: `multipart/form-data`
- Body field: `file`

Response (200):
```json
{
  "fileId": "sfmap_123",
  "fileName": "subject-faculty-map.xlsx",
  "rowsParsed": 74,
  "message": "Subject faculty map uploaded successfully"
}
```

### POST `/uploads/subject-periods-map`
Purpose: Upload subject-to-number-of-periods allocation file.

Request:
- Content-Type: `multipart/form-data`
- Body field: `file`

Response (200):
```json
{
  "fileId": "spmap_123",
  "fileName": "subject-periods-map.xlsx",
  "rowsParsed": 74,
  "message": "Subject periods map uploaded successfully"
}
```

## 2. Faculty Availability API

### POST `/faculty/availability`
Purpose: Return faculty who are free in all selected periods for the given date.

Request (JSON):
```json
{
  "date": "2026-03-06",
  "periods": [1, 3, 5],
  "facultyRequired": 3,
  "ignoredYears": ["2nd Year"],
  "ignoredSections": ["2nd Year|A"]
}
```

Response (200):
```json
{
  "day": "Friday",
  "periods": [
    { "period": 1, "time": "9:10 - 10:00" },
    { "period": 3, "time": "11:00 - 11:50" },
    { "period": 5, "time": "1:30 - 2:20" }
  ],
  "faculty": ["Dr. Bhavani", "Dr. Kumar", "Prof. Lakshmi"]
}
```

## 3. Timetable Generation API

### POST `/timetables/generate`
Purpose: Generate timetable from manual form data and optional uploaded file references.

Request (JSON):
```json
{
  "year": "2nd Year",
  "section": "A",
  "subjects": [{ "subject": "Data Structures", "faculty": "Dr. Rajani" }],
  "labs": [{ "lab": "DS Lab", "faculty": ["Dr. Rajani", "Dr. Venkat"] }],
  "sharedClasses": [{ "year": "2nd Year", "sections": ["B", "C"], "subject": "English" }],
  "subjectHours": [{ "subject": "Data Structures", "hours": 4, "continuousHours": 1 }],
  "mappingFileIds": {
    "facultyIdMap": "fmap_123",
    "subjectFacultyMap": "sfmap_123",
    "subjectPeriodsMap": "spmap_123"
  }
}
```

Response (200):
```json
{
  "timetableId": "tt_20260306_001",
  "message": "Timetable generated successfully"
}
```

## Recommended Error Format (all APIs)

Response (4xx/5xx):
```json
{
  "error": "ValidationError",
  "message": "Human-readable error message",
  "details": []
}
```
