"""Shared helpers for FastAPI routes."""

from __future__ import annotations

import math
from io import BytesIO
from typing import Any

import pandas as pd
from fastapi import HTTPException, UploadFile

from puantaj_calc import hours_to_time, read_uploaded_file
from puantaj_report import format_hours, read_puantaj_file


def api_error(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"code": code, "message": message})


def sanitize_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, pd.Timestamp):
        return value.strftime("%d.%m.%Y")
    if isinstance(value, (pd.Timedelta,)):
        return str(value)
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
        return value
    if isinstance(value, (int, str, bool)):
        return value
    if pd.isna(value):
        return None
    text = str(value)
    return text if text != "NaT" else None


def dataframe_to_records(df: pd.DataFrame) -> list[dict[str, Any]]:
    if df is None or df.empty:
        return []
    records: list[dict[str, Any]] = []
    for row in df.to_dict(orient="records"):
        records.append({str(key): sanitize_value(val) for key, val in row.items()})
    return records


async def read_upload_bytes(upload: UploadFile) -> tuple[bytes, str]:
    filename = upload.filename or "upload.bin"
    data = await upload.read()
    if not data:
        raise api_error(400, "INVALID_FILE", "Yüklenen dosya boş.")
    lower = filename.lower()
    if not lower.endswith((".csv", ".xlsx", ".xls")):
        raise api_error(400, "INVALID_FILE", "Desteklenen formatlar: csv, xlsx, xls.")
    return data, filename


def load_calc_dataframe(data: bytes, filename: str) -> pd.DataFrame:
    try:
        return read_uploaded_file(BytesIO(data), filename)
    except Exception as exc:  # noqa: BLE001 — surface file parse errors to client
        raise api_error(400, "INVALID_FILE", f"Dosya okunamadı: {exc}") from exc


def load_report_dataframe(data: bytes, filename: str) -> pd.DataFrame:
    try:
        return read_puantaj_file(BytesIO(data), filename)
    except Exception as exc:  # noqa: BLE001
        raise api_error(400, "INVALID_FILE", f"Dosya okunamadı: {exc}") from exc


def format_hour_columns(df: pd.DataFrame, columns: list[str], suffix: str = "_fmt") -> pd.DataFrame:
    out = df.copy()
    for column in columns:
        if column in out.columns:
            out[f"{column}{suffix}"] = out[column].map(format_hours)
    return out


def rows_to_dataframe(rows: list[dict[str, Any]]) -> pd.DataFrame:
    if not rows:
        raise api_error(400, "MISSING_COLUMNS", "rows dizisi boş olamaz.")
    return pd.DataFrame(rows)


__all__ = [
    "api_error",
    "dataframe_to_records",
    "format_hour_columns",
    "hours_to_time",
    "load_calc_dataframe",
    "load_report_dataframe",
    "read_upload_bytes",
    "rows_to_dataframe",
    "sanitize_value",
]
