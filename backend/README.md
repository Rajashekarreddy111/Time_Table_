# Class Scheduler Pro Backend

## Run

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
uvicorn main:app --host 0.0.0.0 --port 5000 --reload
```

Base API URL:

`http://localhost:5000/api`

## MongoDB Configuration

Set environment variables before starting backend:

- `MONGO_URI` or `MONGODB_URI` (default: `mongodb://localhost:27017`)
- `MONGO_DB_NAME` (default: `timetable_app`)

The backend auto-loads `backend/.env` at startup, so values in that file are
picked up even when the shell does not export them. Start by copying
`backend/.env.example` to `backend/.env` and then adjust values for the local machine.

## Optional Cloudinary File Backup

If these variables are set, uploaded spreadsheet source files are backed up
to Cloudinary and linked in stored upload metadata:

- `CLOUDINARY_CLOUD_NAME`
- `CLOUDINARY_API_KEY`
- `CLOUDINARY_API_SECRET`

## Implemented APIs

- `POST /api/uploads/faculty-id-map`
- `POST /api/uploads/subject-faculty-map` (requires `year`; optional `batchType=ALL|CREAM|GENERAL`; optional `section` ignored for backward compatibility)
- `POST /api/uploads/subject-periods-map` (requires form field `year`)
- `POST /api/uploads/faculty-availability`
- `GET /api/uploads/mapping-status?year=...`
- `GET /api/uploads/faculty-id-status`
- `GET /api/templates/faculty-id-map`
- `GET /api/templates/subject-faculty-map`
- `GET /api/templates/subject-faculty-map?year=...&sectionList=C1,C2,G1,G2...`
- `GET /api/templates/subject-periods-map`
- `GET /api/templates/subject-periods-map?batchType=CREAM|GENERAL|ALL`
- `GET /api/templates/subject-periods-map-cream`
- `GET /api/templates/subject-periods-map-general`
- `GET /api/templates/faculty-availability`
- `GET /api/templates/faculty-workload`
- `POST /api/faculty/availability`
- `POST /api/timetables/generate`
- `GET /api/timetables`
- `GET /api/timetables/{timetableId}`
- `GET /api/health`

## Error format

```json
{
  "error": "ValidationError",
  "message": "Human-readable error message",
  "details": []
}
```

## Upload file formats

All upload APIs accept `.xlsx`, `.xls`, and `.csv`.
