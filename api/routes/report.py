"""Aylık puantaj raporu (Streamlit sayfa 2) endpoints."""

from __future__ import annotations

from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import Response

from api.deps import (
    api_error,
    dataframe_to_records,
    format_hour_columns,
    load_report_dataframe,
    read_upload_bytes,
)
from api.schemas import PeriodItem, PeriodsResponse, ReportBuildResponse, ReportMeta
from puantaj_report import (
    available_periods,
    build_report,
    create_excel_report,
    format_hours,
)

router = APIRouter(prefix="/api/v1/report", tags=["report"])


def _period_label(year: int, month: int) -> str:
    return f"{month:02d}.{year}"


@router.post("/periods", response_model=PeriodsResponse)
async def list_periods(file: UploadFile = File(...)) -> PeriodsResponse:
    data, filename = await read_upload_bytes(file)
    df = load_report_dataframe(data, filename)
    periods = available_periods(df)
    if not periods:
        raise api_error(400, "NO_PERIODS", "Dosyada geçerli bir mesaitarih alanı bulunamadı.")
    return PeriodsResponse(
        periods=[
            PeriodItem(year=year, month=month, label=_period_label(year, month))
            for year, month in periods
        ]
    )


@router.post("/build", response_model=ReportBuildResponse)
async def build_monthly_report(
    file: UploadFile = File(...),
    year: int = Form(...),
    month: int = Form(...),
) -> ReportBuildResponse:
    if not (1 <= month <= 12):
        raise api_error(400, "INVALID_PERIOD", "month 1–12 arasında olmalıdır.")
    data, filename = await read_upload_bytes(file)
    df = load_report_dataframe(data, filename)
    try:
        result = build_report(df, year, month)
    except ValueError as exc:
        message = str(exc)
        code = "MISSING_COLUMNS" if "Zorunlu sütunlar" in message else "INVALID_PERIOD"
        if "bulunamadı" in message.lower():
            code = "NO_PERIODS"
        raise api_error(400, code, message) from exc

    summary = format_hour_columns(
        result.summary,
        ["Normal Çalışma", "Fazla Mesai", "FM→NM Aktarım"],
    )
    weekly = format_hour_columns(
        result.weekly,
        ["Hafta İçi NM", "Hafta Sonu Ham FM", "FM→NM Aktarım", "Toplam NM", "Kalan FM"],
    )
    daily = result.daily.copy()
    hour_cols = [c for c in daily.columns if str(c).endswith("_h")]
    daily = format_hour_columns(daily, hour_cols)

    total_nm = float(result.summary["Normal Çalışma"].sum()) if not result.summary.empty else 0.0
    total_fm = float(result.summary["Fazla Mesai"].sum()) if not result.summary.empty else 0.0

    meta = ReportMeta(
        year=year,
        month=month,
        label=_period_label(year, month),
        period_start=result.period_start.strftime("%d.%m.%Y"),
        period_end=result.period_end.strftime("%d.%m.%Y"),
        employee_count=len(result.summary),
        record_count=len(result.daily),
        total_nm=total_nm,
        total_fm=total_fm,
        total_nm_fmt=format_hours(total_nm),
        total_fm_fmt=format_hours(total_fm),
    )
    return ReportBuildResponse(
        meta=meta,
        quality=dataframe_to_records(result.quality),
        monthly=dataframe_to_records(result.monthly),
        summary=dataframe_to_records(summary),
        weekly=dataframe_to_records(weekly),
        daily=dataframe_to_records(daily),
    )


@router.post("/excel")
async def download_excel_report(
    file: UploadFile = File(...),
    year: int = Form(...),
    month: int = Form(...),
) -> Response:
    if not (1 <= month <= 12):
        raise api_error(400, "INVALID_PERIOD", "month 1–12 arasında olmalıdır.")
    data, filename = await read_upload_bytes(file)
    df = load_report_dataframe(data, filename)
    try:
        result = build_report(df, year, month)
        report_bytes = create_excel_report(result)
    except ValueError as exc:
        message = str(exc)
        code = "MISSING_COLUMNS" if "Zorunlu sütunlar" in message else "INVALID_PERIOD"
        if "bulunamadı" in message.lower():
            code = "NO_PERIODS"
        raise api_error(400, code, message) from exc

    out_name = f"Aylik_Puantaj_Raporu_{year}_{month:02d}.xlsx"
    return Response(
        content=report_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{out_name}"'},
    )
