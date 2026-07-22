"""Meyer puantaj hesaplama çekirdeği (Streamlit ve FastAPI ortak kullanır)."""

from __future__ import annotations

import io
from datetime import time, timedelta
from typing import BinaryIO

import pandas as pd

WEEKLY_MAX_HOURS = 45.0
DAILY_WORK_HOURS = 9.0
SUNDAY_CUT_ABSENCE_HOURS = 9.0
UNPAID_LEAVE_COLUMN = "UCZIZS"
DAY_NAMES = ("Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar")

GUN_DURUMLARI = (
    "Çalışma",
    "Ücretli İzin / Rapor",
    "Ücretsiz İzin",
    "Devamsızlık",
    "Hafta Sonu",
)

REQUIRED_CALC_COLUMNS = ("mesaitarih", "NM", "FM")


def time_to_hours(value):
    if pd.isna(value) or (isinstance(value, str) and value.strip() == ""):
        return 0.0
    if isinstance(value, (pd.Timedelta, timedelta)):
        return value.total_seconds() / 3600.0
    if isinstance(value, time):
        return value.hour + value.minute / 60.0 + value.second / 3600.0
    if isinstance(value, pd.Timestamp):
        return value.hour + value.minute / 60.0 + value.second / 3600.0

    text = str(value).strip()
    if "day" in text:
        try:
            return pd.to_timedelta(text).total_seconds() / 3600.0
        except (ValueError, TypeError):
            return 0.0

    parts = text.split(":")
    try:
        if len(parts) >= 2:
            seconds = int(float(parts[2])) / 3600.0 if len(parts) > 2 else 0.0
            return int(parts[0]) + int(parts[1]) / 60.0 + seconds
    except ValueError:
        return 0.0
    return 0.0


def hours_to_time(hours):
    h = int(hours)
    m = int(round((hours - h) * 60))
    if m == 60:
        h += 1
        m = 0
    return f"{h:02d}:{m:02d}"


def read_uploaded_file(uploaded_file: BinaryIO | str, filename: str | None = None) -> pd.DataFrame:
    name = str(filename if filename not in (None, "") else getattr(uploaded_file, "name", "")).lower()
    if name.endswith(".csv"):
        if hasattr(uploaded_file, "read"):
            raw = uploaded_file.read()
            if hasattr(uploaded_file, "seek"):
                uploaded_file.seek(0)
            if isinstance(raw, str):
                raw = raw.encode("utf-8")
            for encoding in ("cp1254", "utf-8", "utf-8-sig", "latin-1"):
                try:
                    return pd.read_csv(io.BytesIO(raw), sep=";", encoding=encoding)
                except UnicodeDecodeError:
                    continue
            return pd.read_csv(io.BytesIO(raw), sep=";", encoding="utf-8", errors="replace")
        for encoding in ("cp1254", "utf-8", "utf-8-sig", "latin-1"):
            try:
                return pd.read_csv(uploaded_file, sep=";", encoding=encoding)
            except UnicodeDecodeError:
                continue
        return pd.read_csv(uploaded_file, sep=";", encoding="utf-8", errors="replace")
    if name.endswith(".xls") and not name.endswith(".xlsx"):
        return pd.read_excel(uploaded_file, engine="xlrd")
    return pd.read_excel(uploaded_file, engine="openpyxl")


def resolve_column(df, *preferred_names, keyword=None):
    for name in preferred_names:
        if name in df.columns:
            return name
    if keyword:
        keyword = keyword.lower()
        for col in df.columns:
            if keyword in str(col).lower():
                return col
    return None


def normalize_meyer_columns(df):
    df = df.copy()
    izin_col = resolve_column(df, "İzin Açıklama", keyword="zin")
    if izin_col and izin_col != "İzin Açıklama":
        df = df.rename(columns={izin_col: "İzin Açıklama"})
    return df


def normalize_meyer_rows(df):
    df = normalize_meyer_columns(df.copy())

    if "mesaitarih" not in df.columns:
        raise ValueError("Zorunlu sütunlar eksik: mesaitarih")

    if pd.api.types.is_datetime64_any_dtype(df["mesaitarih"]):
        df["mesaitarih_dt"] = pd.to_datetime(df["mesaitarih"], errors="coerce")
    else:
        df["mesaitarih_dt"] = pd.to_datetime(
            df["mesaitarih"], format="%d.%m.%Y", dayfirst=True, errors="coerce"
        )

    df = df.dropna(subset=["mesaitarih_dt"])
    if "sicilno" in df.columns:
        df = df[df["sicilno"].notna()]

    return df.reset_index(drop=True)


def is_placeholder(value):
    if pd.isna(value):
        return True
    text = str(value).strip()
    return text == "" or text == "#__#"


def column_hours(row, column):
    if column not in row.index or is_placeholder(row[column]):
        return 0.0
    return time_to_hours(row[column])


def paid_leave_hours(row):
    nm_h = column_hours(row, "NM")
    izin_from_codes = max(
        (column_hours(row, col) for col in ("IZS", "YIZS", "SGKIZS", "RM", "İzin Açıklama")),
        default=0.0,
    )
    if izin_from_codes > 0:
        return izin_from_codes

    em_h = column_hours(row, "EM")
    if nm_h < 0.1 and em_h >= DAILY_WORK_HOURS:
        return em_h

    return 0.0


def unpaid_leave_hours(row):
    return column_hours(row, UNPAID_LEAVE_COLUMN)


def izin_turu_label(row):
    aciklama = str(row.get("İzin Açıklama", "")).upper()
    if "YILLIK" in aciklama:
        return "Yıllık İzin"
    if "RAPOR" in aciklama or column_hours(row, "SGKIZS") > 0 or column_hours(row, "RM") > 0:
        return "Sağlık Raporu"
    if column_hours(row, "YIZS") > 0:
        return "Yıllık İzin"
    if column_hours(row, "IZS") > 0:
        return "Ücretli İzin"
    if column_hours(row, UNPAID_LEAVE_COLUMN) > 0:
        return "Ücretsiz İzin"
    if paid_leave_hours(row) > 0:
        return "Ücretli İzin"
    return ""


def classify_day(row, is_weekday):
    nm_h = column_hours(row, "NM")
    unpaid_h = unpaid_leave_hours(row)
    paid_h = paid_leave_hours(row)
    izin_turu = izin_turu_label(row)

    if unpaid_h > 0:
        return "Ücretsiz İzin", paid_h, unpaid_h, izin_turu or "Ücretsiz İzin"
    if paid_h > 0:
        credit = DAILY_WORK_HOURS if paid_h >= DAILY_WORK_HOURS else paid_h
        return "Ücretli İzin / Rapor", credit, 0.0, izin_turu or "Ücretli İzin"
    if nm_h > 0:
        return "Çalışma", 0.0, 0.0, ""
    if is_weekday:
        return "Devamsızlık", 0.0, 0.0, ""
    return "Hafta Sonu", 0.0, 0.0, ""


def expected_daily_hours(row, is_weekday):
    if not is_weekday:
        return 0.0
    ms_h = column_hours(row, "MS")
    return ms_h if ms_h > 0 else SUNDAY_CUT_ABSENCE_HOURS


def series_hours(df, column):
    if column not in df.columns:
        return pd.Series(0.0, index=df.index)
    return df[column].apply(time_to_hours)


def count_positive_days(hours_series):
    return int((hours_series > 0).sum())


def build_leave_breakdown(df_calc):
    izs_h = series_hours(df_calc, "IZS")
    yizs_h = series_hours(df_calc, "YIZS")
    sgkizs_h = series_hours(df_calc, "SGKIZS")
    rm_h = series_hours(df_calc, "RM")
    uczizs_h = series_hours(df_calc, "UCZIZS")

    yillik_mask = df_calc["izin_turu"] == "Yıllık İzin"
    rapor_mask = df_calc["izin_turu"] == "Sağlık Raporu"
    ucretli_mask = (df_calc["izin_turu"] == "Ücretli İzin") & ~yillik_mask & ~rapor_mask
    sgk_gun_mask = rapor_mask | (sgkizs_h > 0) | (rm_h > 0)

    yillik_saat = df_calc.loc[yillik_mask, "ucretli_izin_h"].sum()
    if yillik_saat == 0:
        yillik_saat = yizs_h.sum()

    ucretli_saat = df_calc.loc[ucretli_mask, "ucretli_izin_h"].sum()
    if ucretli_saat == 0:
        ucretli_saat = izs_h.sum()

    rapor_saat = max(
        df_calc.loc[rapor_mask, "ucretli_izin_h"].sum(),
        sgkizs_h.sum(),
        rm_h.sum(),
    )

    rows = [
        {
            "Kategori": "Çalışma",
            "Gün": int((df_calc["gun_durumu"] == "Çalışma").sum()),
            "Saat": hours_to_time(df_calc.loc[df_calc["gun_durumu"] == "Çalışma", "NM_h"].sum()),
            "Kaynak": "NM",
        },
        {
            "Kategori": "Yıllık İzin",
            "Gün": int(yillik_mask.sum()) or count_positive_days(yizs_h),
            "Saat": hours_to_time(yillik_saat),
            "Kaynak": "YIZS / IZS / EM",
        },
        {
            "Kategori": "Ücretli İzin",
            "Gün": int(ucretli_mask.sum()) or count_positive_days(izs_h),
            "Saat": hours_to_time(ucretli_saat),
            "Kaynak": "IZS / EM",
        },
        {
            "Kategori": "SGK Raporu",
            "Gün": int(sgk_gun_mask.sum()),
            "Saat": hours_to_time(rapor_saat),
            "Kaynak": "SGKIZS / RM",
        },
        {
            "Kategori": "Ücretsiz İzin",
            "Gün": int((df_calc["gun_durumu"] == "Ücretsiz İzin").sum()),
            "Saat": hours_to_time(uczizs_h.sum()),
            "Kaynak": "UCZIZS",
        },
        {
            "Kategori": "Devamsızlık",
            "Gün": int((df_calc["gun_durumu"] == "Devamsızlık").sum()),
            "Saat": hours_to_time(df_calc["devamsizlik_h"].sum()),
            "Kaynak": "Mazeretsiz eksik",
        },
        {
            "Kategori": "Hafta Sonu",
            "Gün": int((df_calc["gun_durumu"] == "Hafta Sonu").sum()),
            "Saat": "—",
            "Kaynak": "Cumartesi / Pazar",
        },
    ]
    return pd.DataFrame(rows)


def calculate_puantaj(df):
    missing = [col for col in REQUIRED_CALC_COLUMNS if col not in df.columns]
    if missing:
        raise ValueError("Zorunlu sütunlar eksik: " + ", ".join(missing))

    df_calc = normalize_meyer_rows(df)

    df_calc["NM_h"] = df_calc["NM"].apply(time_to_hours)
    df_calc["FM_h"] = df_calc["FM"].apply(time_to_hours)
    df_calc["day_of_week"] = df_calc["mesaitarih_dt"].dt.dayofweek
    iso = df_calc["mesaitarih_dt"].dt.isocalendar()
    df_calc["year"] = iso.year
    df_calc["week"] = iso.week

    weekday_flags = df_calc["day_of_week"] < 5
    day_info = df_calc.apply(
        lambda row: classify_day(row, weekday_flags.loc[row.name]),
        axis=1,
        result_type="expand",
    )
    df_calc["gun_durumu"] = day_info[0]
    df_calc["ucretli_izin_h"] = day_info[1]
    df_calc["ucretsiz_izin_h"] = day_info[2]
    df_calc["izin_turu"] = day_info[3]
    df_calc["beklenen_gunluk_h"] = df_calc.apply(
        lambda row: expected_daily_hours(row, row["day_of_week"] < 5), axis=1
    )
    df_calc["devamsizlik_h"] = df_calc.apply(
        lambda row: row["beklenen_gunluk_h"] if row["gun_durumu"] == "Devamsızlık" else 0.0,
        axis=1,
    )

    weekly_rows = []
    for (year, week) in df_calc[["year", "week"]].drop_duplicates().itertuples(index=False):
        week_mask = (df_calc["year"] == year) & (df_calc["week"] == week)
        weekday_mask = week_mask & (df_calc["day_of_week"] < 5)
        weekend_mask = week_mask & (df_calc["day_of_week"] >= 5)

        weekday_nm = df_calc.loc[weekday_mask, "NM_h"].sum()
        missing_nm = max(0, WEEKLY_MAX_HOURS - weekday_nm)

        if missing_nm > 0:
            for idx in df_calc[weekend_mask].index:
                fm_available = df_calc.loc[idx, "FM_h"]
                if fm_available > 0 and missing_nm > 0:
                    deduct = min(missing_nm, fm_available)
                    df_calc.loc[idx, "FM_h"] -= deduct
                    df_calc.loc[idx, "NM_h"] += deduct
                    missing_nm -= deduct

        pazar_kesinti_tetik = bool(
            (
                df_calc.loc[weekday_mask, "devamsizlik_h"]
                >= SUNDAY_CUT_ABSENCE_HOURS
            ).any()
        )

        week_dates = df_calc.loc[week_mask, "mesaitarih_dt"]
        week_start = week_dates.min()
        week_end = week_dates.max()
        days_in_data = int(week_mask.sum())
        weekly_rows.append({
            "Hafta": f"{week_start.strftime('%d.%m.%Y')} (H{int(week)})",
            "Kapsam": f"{week_start.strftime('%d.%m')} – {week_end.strftime('%d.%m')}",
            "Gün (dosyada)": days_in_data,
            "Tür": "Kısmi" if days_in_data < 7 else "Tam",
            "Hafta İçi NM": hours_to_time(df_calc.loc[weekday_mask, "NM_h"].sum()),
            "Hafta Sonu FM": hours_to_time(df_calc.loc[weekend_mask, "FM_h"].sum()),
            "Toplam NM": hours_to_time(df_calc.loc[week_mask, "NM_h"].sum()),
            "Toplam FM": hours_to_time(df_calc.loc[week_mask, "FM_h"].sum()),
            "Pazar Durumu": "Yanar" if pazar_kesinti_tetik else "Hak Edildi",
        })

    weekly_df = pd.DataFrame(weekly_rows)
    leave_breakdown_df = build_leave_breakdown(df_calc)

    period_start = df_calc["mesaitarih_dt"].min()
    period_end = df_calc["mesaitarih_dt"].max()
    kismi_hafta = int((weekly_df["Tür"] == "Kısmi").sum()) if not weekly_df.empty else 0

    summary = {
        "toplam_nm": float(df_calc["NM_h"].sum()),
        "toplam_fm": float(df_calc["FM_h"].sum()),
        "toplam_nm_fmt": hours_to_time(df_calc["NM_h"].sum()),
        "toplam_fm_fmt": hours_to_time(df_calc["FM_h"].sum()),
        "ucretli_izin_gun": int((df_calc["gun_durumu"] == "Ücretli İzin / Rapor").sum()),
        "ucretli_izin_saat": float(df_calc["ucretli_izin_h"].sum()),
        "ucretli_izin_saat_fmt": hours_to_time(df_calc["ucretli_izin_h"].sum()),
        "ucretsiz_izin_gun": int((df_calc["gun_durumu"] == "Ücretsiz İzin").sum()),
        "ucretsiz_izin_saat": float(df_calc["ucretsiz_izin_h"].sum()),
        "ucretsiz_izin_saat_fmt": hours_to_time(df_calc["ucretsiz_izin_h"].sum()),
        "devamsizlik_gun": int((df_calc["gun_durumu"] == "Devamsızlık").sum()),
        "devamsizlik_saat": float(df_calc["devamsizlik_h"].sum()),
        "devamsizlik_saat_fmt": hours_to_time(df_calc["devamsizlik_h"].sum()),
        "calisma_gun": int((df_calc["gun_durumu"] == "Çalışma").sum()),
        "pazar_yanan_hafta": int((weekly_df["Pazar Durumu"] == "Yanar").sum()) if not weekly_df.empty else 0,
        "donem": f"{period_start.strftime('%d.%m.%Y')} – {period_end.strftime('%d.%m.%Y')}",
        "toplam_gun": len(df_calc),
        "iso_hafta_sayisi": len(weekly_df),
        "kisami_hafta_sayisi": kismi_hafta,
        "tam_hafta_sayisi": len(weekly_df) - kismi_hafta,
    }

    daily_df = pd.DataFrame({
        "Tarih": df_calc["mesaitarih_dt"].dt.strftime("%d.%m.%Y"),
        "Gün": df_calc["day_of_week"].map(dict(enumerate(DAY_NAMES))),
        "Gün Durumu": df_calc["gun_durumu"],
        "İzin Türü": df_calc["izin_turu"].replace("", "—"),
        "NM (Güncel)": df_calc["NM_h"].apply(hours_to_time),
        "FM (Güncel)": df_calc["FM_h"].apply(hours_to_time),
        "Ücretli İzin": df_calc["ucretli_izin_h"].apply(hours_to_time),
        "Ücretsiz İzin": df_calc["ucretsiz_izin_h"].apply(hours_to_time),
        "Devamsızlık Saat": df_calc["devamsizlik_h"].apply(hours_to_time),
    })

    df_calc["NM (Güncel)"] = df_calc["NM_h"].apply(hours_to_time)
    df_calc["FM (Güncel)"] = df_calc["FM_h"].apply(hours_to_time)
    df_calc["Gün Durumu"] = df_calc["gun_durumu"]
    df_calc["İzin Türü"] = df_calc["izin_turu"].replace("", "—")
    df_calc["Ücretli İzin"] = df_calc["ucretli_izin_h"].apply(hours_to_time)
    df_calc["Ücretsiz İzin"] = df_calc["ucretsiz_izin_h"].apply(hours_to_time)
    df_calc["Devamsızlık Saat"] = df_calc["devamsizlik_h"].apply(hours_to_time)

    df_calc = df_calc.drop(
        columns=["mesaitarih_dt", "NM_h", "FM_h", "day_of_week", "year", "week",
                 "gun_durumu", "ucretli_izin_h", "ucretsiz_izin_h", "izin_turu",
                 "beklenen_gunluk_h", "devamsizlik_h"]
    )

    return df_calc, daily_df, weekly_df, leave_breakdown_df, summary


def is_bulk_file(df):
    if "sicilno" not in df.columns:
        return False
    valid = df[df["sicilno"].notna()]
    return valid["sicilno"].nunique() > 1


def build_employee_list(df):
    valid = df[df["sicilno"].notna()].copy()
    valid["sicilno"] = valid["sicilno"].astype(int).astype(str).str.zfill(5)

    group_cols = ["sicilno", "Ad", "Soyad"]
    agg = {"mesaitarih": "count"}
    for col in ("Firma", "Pozisyon"):
        if col in valid.columns:
            agg[col] = "first"
    bolum_col = resolve_column(valid, "Bölüm", keyword="lüm")
    if bolum_col:
        agg[bolum_col] = "first"

    listed = (
        valid.groupby(group_cols, as_index=False)
        .agg(agg)
        .rename(columns={"mesaitarih": "Kayıt"})
        .sort_values(["Ad", "Soyad"])
        .reset_index(drop=True)
    )
    if bolum_col and bolum_col != "Bölüm":
        listed = listed.rename(columns={bolum_col: "Bölüm"})
    return listed


def filter_employee_df(df, sicilno):
    employee_df = df[df["sicilno"].notna()].copy()
    employee_df["sicilno"] = employee_df["sicilno"].astype(int).astype(str).str.zfill(5)
    return employee_df[employee_df["sicilno"] == str(sicilno).zfill(5)].copy()
