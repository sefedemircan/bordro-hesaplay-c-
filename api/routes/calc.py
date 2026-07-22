"""Puantaj hesaplama (Streamlit sayfa 1) endpoints."""

from __future__ import annotations

from typing import Any

import pandas as pd
from fastapi import APIRouter, File, Request, UploadFile
from starlette.datastructures import UploadFile as StarletteUploadFile

from api.deps import (
    api_error,
    dataframe_to_records,
    load_calc_dataframe,
    read_upload_bytes,
    rows_to_dataframe,
)
from api.schemas import ComputeJsonRequest, ComputeResponse, InspectResponse
from puantaj_calc import (
    build_employee_list,
    calculate_puantaj,
    filter_employee_df,
    is_bulk_file,
    normalize_meyer_rows,
)

router = APIRouter(prefix="/api/v1/calc", tags=["calc"])


def _employee_label(df: pd.DataFrame, fallback: str = "Personel") -> str:
    if "Ad" in df.columns and "Soyad" in df.columns and not df.empty:
        return f"{df['Ad'].iloc[0]} {df['Soyad'].iloc[0]}".strip() or fallback
    return fallback


def _compute_payload(
    df: pd.DataFrame,
    employee_label: str | None = None,
    sicilno: str | None = None,
) -> dict[str, Any]:
    try:
        processed_df, daily_df, weekly_df, leave_breakdown_df, summary = calculate_puantaj(df)
    except ValueError as exc:
        message = str(exc)
        code = "MISSING_COLUMNS" if "Zorunlu sütunlar" in message else "INVALID_FILE"
        raise api_error(400, code, message) from exc

    summary = dict(summary)
    summary["employee_label"] = employee_label or _employee_label(df)
    if sicilno:
        summary["sicilno"] = str(sicilno).zfill(5)
    elif "sicilno" in df.columns and not df.empty:
        try:
            summary["sicilno"] = str(int(df["sicilno"].iloc[0])).zfill(5)
        except (TypeError, ValueError):
            summary["sicilno"] = str(df["sicilno"].iloc[0])
    return {
        "summary": summary,
        "leave_breakdown": dataframe_to_records(leave_breakdown_df),
        "daily": dataframe_to_records(daily_df),
        "weekly": dataframe_to_records(weekly_df),
        "processed": dataframe_to_records(processed_df),
    }


@router.post("/inspect", response_model=InspectResponse)
async def inspect_file(file: UploadFile = File(...)) -> InspectResponse:
    data, filename = await read_upload_bytes(file)
    df = load_calc_dataframe(data, filename)
    bulk = is_bulk_file(df)
    employees: list[dict[str, Any]] = []
    if bulk or ("sicilno" in df.columns and df["sicilno"].notna().any()):
        try:
            employees = dataframe_to_records(build_employee_list(df))
        except Exception as exc:  # noqa: BLE001
            raise api_error(400, "INVALID_FILE", f"Personel listesi oluşturulamadı: {exc}") from exc
    return InspectResponse(is_bulk=bulk, record_count=len(df), employees=employees)


@router.post("/compute", response_model=ComputeResponse)
async def compute(request: Request) -> ComputeResponse:
    """Dosya (multipart) veya JSON rows ile hesaplama.

    - `multipart/form-data`: `file` (+ toplu dosyada `sicilno`)
    - `application/json`: `{ "rows": [...], "employee_label"?: string }`
    """
    content_type = (request.headers.get("content-type") or "").lower()

    if "application/json" in content_type:
        payload = await request.json()
        body = ComputeJsonRequest.model_validate(payload)
        df = rows_to_dataframe(body.rows)
        return ComputeResponse(**_compute_payload(df, body.employee_label))

    form = await request.form()
    upload = form.get("file")
    if upload is None or not isinstance(upload, (UploadFile, StarletteUploadFile)):
        raise api_error(
            400,
            "INVALID_FILE",
            "multipart/form-data ile `file` gönderin veya application/json ile `rows` gönderin.",
        )

    sicil_raw = form.get("sicilno")
    sicilno = str(sicil_raw).strip() if sicil_raw not in (None, "") else None

    data, filename = await read_upload_bytes(upload)  # type: ignore[arg-type]
    master_df = load_calc_dataframe(data, filename)
    bulk = is_bulk_file(master_df)

    if bulk:
        if not sicilno:
            raise api_error(
                400,
                "EMPLOYEE_NOT_FOUND",
                "Toplu dosyada sicilno zorunludur. Önce /inspect ile personel listesini alın.",
            )
        employee_df = filter_employee_df(master_df, sicilno)
        if employee_df.empty:
            raise api_error(400, "EMPLOYEE_NOT_FOUND", f"Sicil bulunamadı: {sicilno}")
        employee_df = normalize_meyer_rows(employee_df)
        label = _employee_label(employee_df)
        return ComputeResponse(**_compute_payload(employee_df, label, sicilno))

    df = normalize_meyer_rows(master_df)
    if sicilno:
        filtered = filter_employee_df(master_df, sicilno)
        if filtered.empty:
            raise api_error(400, "EMPLOYEE_NOT_FOUND", f"Sicil bulunamadı: {sicilno}")
        df = normalize_meyer_rows(filtered)
    label = _employee_label(df)
    return ComputeResponse(**_compute_payload(df, label, sicilno))
