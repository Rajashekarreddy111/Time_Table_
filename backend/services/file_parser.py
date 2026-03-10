from io import BytesIO, StringIO
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
import pdfplumber
import pytesseract
from fastapi import HTTPException, UploadFile


def validation_error(message: str, details: list | None = None) -> HTTPException:
    return HTTPException(
        status_code=400,
        detail={
            "error": "ValidationError",
            "message": message,
            "details": details or [],
        },
    )


def _normalize_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    cleaned = df.copy()
    cleaned.columns = [str(col).strip() for col in cleaned.columns]
    cleaned = cleaned.where(pd.notnull(cleaned), None)
    return cleaned


def parse_tabular_upload(file_name: str, file_bytes: bytes) -> pd.DataFrame:
    suffix = Path(file_name).suffix.lower()
    if suffix == ".csv":
        frame = pd.read_csv(StringIO(file_bytes.decode("utf-8-sig")))
        return _normalize_dataframe(frame)
    if suffix in {".xlsx", ".xls"}:
        frame = pd.read_excel(BytesIO(file_bytes))
        return _normalize_dataframe(frame)
    if suffix == ".pdf":
        return _normalize_dataframe(parse_pdf_to_dataframe(file_bytes))
    if suffix in {".png", ".jpg", ".jpeg"}:
        return _normalize_dataframe(parse_image_to_dataframe(file_bytes))
    raise validation_error("Unsupported file format", [f"Received extension: {suffix}"])


def parse_pdf_to_dataframe(file_bytes: bytes) -> pd.DataFrame:
    records: list[dict] = []
    with pdfplumber.open(BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables() or []
            for table in tables:
                if not table or len(table) < 2:
                    continue
                headers = [str(h).strip().lower() for h in table[0]]
                for row in table[1:]:
                    records.append({headers[i]: row[i] if i < len(row) else None for i in range(len(headers))})
    if records:
        return pd.DataFrame(records)
    raise validation_error("No structured table found in PDF", [])


def parse_image_to_dataframe(file_bytes: bytes) -> pd.DataFrame:
    import re

    np_arr = np.frombuffer(file_bytes, dtype="uint8")
    image = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
    if image is None:
        raise validation_error("Unable to decode image", [])

    text = pytesseract.image_to_string(image)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        raise validation_error("No readable text found in image", [])

    # Try different delimiters: comma, tab, or 2+ spaces
    def split_line(l):
        # Prefer tab/comma, then fallback to multi-space
        if "\t" in l:
            return [p.strip() for p in l.split("\t") if p.strip()]
        if "," in l:
            return [p.strip() for p in l.split(",") if p.strip()]
        # Fallback: Treat 2+ spaces as a delimiter (common in OCR tables)
        return [p.strip() for p in re.split(r"\s{2,}", l) if p.strip()]

    header = [h.strip().lower() for h in split_line(lines[0])]
    if not header:
        raise validation_error("Header row is empty or unparseable", [])

    rows = []
    for line in lines[1:]:
        parts = [p.strip() for p in split_line(line)]
        if len(parts) == 0:
            continue
        # Allow some flexibility in column count for OCR noise
        if len(parts) < len(header):
            # Pad with empty strings if slightly short
            parts = parts + [""] * (len(header) - len(parts))
        elif len(parts) > len(header):
            # Truncate if too long
            parts = parts[:len(header)]

        rows.append({header[i]: parts[i] for i in range(len(header))})

    if rows:
        return pd.DataFrame(rows)
    raise validation_error(
        "OCR output is not in a recognized tabular format",
        [{"tip": "Try formatting input as a CSV-like text with clear columns or borders."}],
    )


def require_columns(df: pd.DataFrame, required_columns: list[str]) -> None:
    missing = [column for column in required_columns if column not in df.columns]
    if missing:
        raise validation_error(
            "Required columns are missing",
            [{"missingColumns": missing, "receivedColumns": list(df.columns)}],
        )


def dataframe_rows(df: pd.DataFrame) -> list[dict]:
    # Convert to dict with lowercased keys for case-insensitive access, but preserve original column names
    records = []
    column_map = {str(col).strip().lower(): str(col).strip() for col in df.columns}
    for _, row in df.iterrows():
        record = {}
        for lower_col, orig_col in column_map.items():
            record[lower_col] = row[orig_col]
            # Also store original column name for cases where we need it
            record[f"__orig_{lower_col}"] = orig_col
        records.append(record)
    return records


def read_upload_bytes(file: UploadFile) -> bytes:
    content = file.file.read()
    if not content:
        raise validation_error("Uploaded file is empty", [])
    return content


def create_excel_template(records: list[dict]) -> bytes:
    frame = pd.DataFrame(records)
    stream = BytesIO()
    frame.to_excel(stream, index=False, engine="openpyxl")
    stream.seek(0)
    return stream.read()
