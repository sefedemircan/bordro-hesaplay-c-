"""FastAPI application (public entrypoint: main:app)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Repo root on path so `puantaj_calc` / `puantaj_report` import when cwd differs (Vercel).
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from api.routes import calc, report  # noqa: E402
from api.schemas import CodeLegendItem, HealthResponse, MetaResponse  # noqa: E402
from puantaj_calc import (  # noqa: E402
    DAILY_WORK_HOURS,
    DAY_NAMES,
    GUN_DURUMLARI,
    REQUIRED_CALC_COLUMNS,
    SUNDAY_CUT_ABSENCE_HOURS,
    UNPAID_LEAVE_COLUMN,
    WEEKLY_MAX_HOURS,
)
from puantaj_report import CODE_LEGEND, STATUS_LABELS  # noqa: E402

app = FastAPI(
    title="Bordro / Puantaj API",
    description=(
        "Meyer puantaj hesaplama ve aylık rapor API'si. "
        "Stateless: her istekte dosya yeniden yüklenir. "
        "Frontend referansı: docs/FRONTEND_API.md"
    ),
    version="1.0.0",
)

_cors_raw = os.getenv("CORS_ORIGINS", "*").strip()
_cors_origins = [o.strip() for o in _cors_raw.split(",") if o.strip()] or ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=False if _cors_origins == ["*"] else True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(calc.router)
app.include_router(report.router)


@app.get("/health", response_model=HealthResponse, tags=["meta"])
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@app.get("/api/v1/meta", response_model=MetaResponse, tags=["meta"])
def meta() -> MetaResponse:
    return MetaResponse(
        weekly_max_hours=WEEKLY_MAX_HOURS,
        daily_work_hours=DAILY_WORK_HOURS,
        sunday_cut_absence_hours=SUNDAY_CUT_ABSENCE_HOURS,
        unpaid_leave_column=UNPAID_LEAVE_COLUMN,
        gun_durumlari=list(GUN_DURUMLARI),
        day_names=list(DAY_NAMES),
        code_legend=[CodeLegendItem(kod=code, aciklama=desc) for code, desc in CODE_LEGEND],
        status_labels=dict(STATUS_LABELS),
        calc_required_columns=list(REQUIRED_CALC_COLUMNS),
        report_required_columns=["sicilno", "Ad", "Soyad", "mesaitarih", "NM", "FM"],
        meyer_hour_columns=["MS", "NM", "FM", "IZS", "YIZS", "SGKIZS", "UCZIZS", "RM", "EM"],
    )
