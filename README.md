# Timetable Project

This repo has two apps:

- `backend`: FastAPI API on `http://localhost:5000`
- `frontend`: Vite + React app on `http://localhost:8080`

## First-time setup on a new PC

### Backend

```powershell
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
Copy-Item .env.example .env
uvicorn main:app --host 0.0.0.0 --port 5000 --reload
```

### Frontend

Open a second terminal:

```powershell
cd frontend
npm install
Copy-Item .env.example .env
npm run dev
```

Then open `http://localhost:8080`.

## Notes

- Do not commit real credentials in `backend/.env`.
- If MongoDB is not available, the backend can still start in in-memory fallback mode for basic usage.
- The frontend expects the backend at `http://localhost:5000/api` unless `VITE_API_BASE_URL` is changed.
