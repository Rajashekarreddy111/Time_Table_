from __future__ import annotations

import logging
import os
from typing import Any

from services.env_config import load_backend_env

load_backend_env()

try:
    import cloudinary
    import cloudinary.uploader
except ImportError:  # pragma: no cover - optional dependency
    cloudinary = None


logger = logging.getLogger(__name__)


def _cloudinary_ready() -> bool:
    return bool(
        cloudinary
        and os.getenv("CLOUDINARY_CLOUD_NAME")
        and os.getenv("CLOUDINARY_API_KEY")
        and os.getenv("CLOUDINARY_API_SECRET")
    )


def is_cloudinary_enabled() -> bool:
    return _cloudinary_ready()


def _configure_cloudinary() -> None:
    if not cloudinary:
        return
    cloudinary.config(
        cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
        api_key=os.getenv("CLOUDINARY_API_KEY"),
        api_secret=os.getenv("CLOUDINARY_API_SECRET"),
        secure=True,
    )


def upload_source_file(filename: str, file_bytes: bytes, folder: str = "timetable/uploads") -> dict[str, Any] | None:
    """
    Upload original spreadsheet to Cloudinary when credentials are available.
    Returns metadata that can be stored along with parsed rows.
    """
    if not _cloudinary_ready():
        return None
    try:
        _configure_cloudinary()
        result = cloudinary.uploader.upload(  # type: ignore[union-attr]
            file_bytes,
            resource_type="raw",
            folder=folder,
            filename_override=filename,
            use_filename=True,
            unique_filename=True,
        )
        return {
            "publicId": result.get("public_id"),
            "url": result.get("secure_url") or result.get("url"),
            "resourceType": result.get("resource_type"),
            "format": result.get("format"),
            "bytes": result.get("bytes"),
        }
    except Exception as exc:  # pragma: no cover - network dependency
        logger.warning("Cloudinary upload failed for %s: %s", filename, exc)
        return None
