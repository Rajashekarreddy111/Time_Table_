import os
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from services.cloudinary_storage import is_cloudinary_enabled
from services.env_config import load_backend_env
from routers import auth, faculty, templates, timetables, uploads
from services.auth import ensure_default_admin, get_current_user
from fastapi import Depends
from storage.memory_store import store

load_backend_env()


def error_payload(error: str, message: str, details: list | None = None) -> dict:
    return {
        "error": error,
        "message": message,
        "details": details or [],
    }


@asynccontextmanager
async def lifespan(_: FastAPI):
    ensure_default_admin()
    # Warmup check only; health endpoint reports current Mongo status.
    try:
        store.ping()
    except Exception:
        pass
    yield


app = FastAPI(title="Class Scheduler Pro Backend", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1|\[::1\]|192\.168\.\d+\.\d+|10\.\d+\.\d+\.\d+|172\.(1[6-9]|2[0-9]|3[0-1])\.\d+\.\d+)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

@app.middleware("http")
async def log_requests(request, call_next):
    print(f"INFO: {request.method} {request.url.path}")
    response = await call_next(request)
    print(f"INFO: Response status: {response.status_code}")
    return response

app.include_router(auth.router, prefix="/api")
app.include_router(uploads.router, prefix="/api", dependencies=[Depends(get_current_user)])
app.include_router(templates.router, prefix="/api", dependencies=[Depends(get_current_user)])
app.include_router(faculty.router, prefix="/api", dependencies=[Depends(get_current_user)])
app.include_router(timetables.router, prefix="/api", dependencies=[Depends(get_current_user)])

@app.get("/api/health")
async def health_check() -> dict:
    mongo_error = None
    try:
        store.ping()
        mongo_status = "connected"
    except Exception as e:
        mongo_status = "disconnected"
        mongo_error = str(e)
    
    return {
        "status": "ok" if mongo_status == "connected" else "degraded",
        "mongo": mongo_status,
        "mongo_error": mongo_error,
        "cloudinary": "configured" if is_cloudinary_enabled() else "not_configured",
    }


@app.exception_handler(HTTPException)
async def http_exception_handler(_, exc: HTTPException):
    detail = exc.detail
    if isinstance(detail, dict) and {"error", "message", "details"}.issubset(detail.keys()):
        return JSONResponse(status_code=exc.status_code, content=detail)
    return JSONResponse(
        status_code=exc.status_code,
        content=error_payload("HttpError", str(detail), []),
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content=error_payload("ValidationError", "Request validation failed", exc.errors()),
    )


@app.exception_handler(Exception)
async def generic_exception_handler(_, exc: Exception):
    import traceback
    print(f"ERROR: Unhandled exception: {str(exc)}")
    traceback.print_exc()
    return JSONResponse(
        status_code=500,
        content=error_payload("InternalServerError", str(exc), []),
    )


if __name__ == "__main__":
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "5000"))
    reload_enabled = os.getenv("RELOAD", "true").strip().lower() in {"1", "true", "yes", "on"}
    uvicorn.run("main:app", host=host, port=port, reload=reload_enabled)
