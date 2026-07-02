import streamlit as st
import pandas as pd
import io
from datetime import time, timedelta

st.set_page_config(page_title="Puantaj & Mesai Hesaplayıcı", layout="wide", initial_sidebar_state="collapsed")

WEEKLY_MAX_HOURS = 45.0
DAILY_WORK_HOURS = 7.5
SUNDAY_CUT_ABSENCE_HOURS = 9.0
UNPAID_LEAVE_COLUMN = "UCZIZS"
DAY_NAMES = ("Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar")

# ── Yardımcı fonksiyonlar ──────────────────────────────────────────────────

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

def read_uploaded_file(uploaded_file):
    name = uploaded_file.name.lower()
    if name.endswith(".csv"):
        for encoding in ("cp1254", "utf-8", "utf-8-sig", "latin-1"):
            try:
                uploaded_file.seek(0)
                return pd.read_csv(uploaded_file, sep=";", encoding=encoding)
            except UnicodeDecodeError:
                continue
        uploaded_file.seek(0)
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
            if keyword in col.lower():
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

def calculate_puantaj(df):
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

        week_start = df_calc.loc[week_mask, "mesaitarih_dt"].min()
        weekly_rows.append({
            "Hafta": f"{week_start.strftime('%d.%m.%Y')} (H{int(week)})",
            "Hafta İçi NM": hours_to_time(df_calc.loc[weekday_mask, "NM_h"].sum()),
            "Hafta Sonu FM": hours_to_time(df_calc.loc[weekend_mask, "FM_h"].sum()),
            "Toplam NM": hours_to_time(df_calc.loc[week_mask, "NM_h"].sum()),
            "Toplam FM": hours_to_time(df_calc.loc[week_mask, "FM_h"].sum()),
            "Pazar Durumu": "Yanar" if pazar_kesinti_tetik else "Hak Edildi",
        })

    weekly_df = pd.DataFrame(weekly_rows)

    summary = {
        "toplam_nm": df_calc["NM_h"].sum(),
        "toplam_fm": df_calc["FM_h"].sum(),
        "ucretli_izin_gun": int((df_calc["gun_durumu"] == "Ücretli İzin / Rapor").sum()),
        "ucretli_izin_saat": df_calc["ucretli_izin_h"].sum(),
        "ucretsiz_izin_gun": int((df_calc["gun_durumu"] == "Ücretsiz İzin").sum()),
        "ucretsiz_izin_saat": df_calc["ucretsiz_izin_h"].sum(),
        "devamsizlik_gun": int((df_calc["gun_durumu"] == "Devamsızlık").sum()),
        "devamsizlik_saat": df_calc["devamsizlik_h"].sum(),
        "calisma_gun": int((df_calc["gun_durumu"] == "Çalışma").sum()),
        "pazar_yanan_hafta": int((weekly_df["Pazar Durumu"] == "Yanar").sum()),
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

    return df_calc, daily_df, weekly_df, summary

# ── Arayüz ─────────────────────────────────────────────────────────────────

st.title("Puantaj & Mesai Hesaplayıcı")
st.caption("Meyer puantaj dosyalarından mesai düzenlemesi, izin ayrımı ve haftalık FM→NM aktarımı.")

with st.expander("Nasıl çalışır?", expanded=False):
    st.markdown("""
**45 saat kuralı**  
Hafta içi toplam NM 45 saatin altındaysa, hafta sonu FM saatleri otomatik olarak NM'ye aktarılır.

**İzin entegrasyonu** (Meyer sütunları)  
| Sütun | Anlam |
|-------|-------|
| `IZS`, `YIZS`, `SGKIZS`, `RM` | Ücretli izin / rapor (saatlik) |
| `EM` | Tam gün ücretli izin (NM=0 ve EM≥7,5 saat) |
| `UCZIZS` | Ücretsiz izin |
| `İzin Açıklama` | İzin türü metni (ör. YILLIK IZIN) |

**Gün durumları**  
Çalışma · Ücretli İzin / Rapor · Ücretsiz İzin · Devamsızlık · Hafta Sonu

**Pazar kesinti kuralı**  
Yalnızca tek bir iş gününde `9:00` saat tam devamsızlık varsa o haftada pazar "Yanar" olur.  
Parçalı devamsızlık toplamı `9:00` olsa bile pazar kesintisi tetiklenmez.
    """)

uploaded_file = st.file_uploader(
    "Puantaj dosyası yükleyin",
    type=["csv", "xlsx", "xls"],
    help="Meyer'den dışa aktarılan CSV veya Excel dosyası",
)

if uploaded_file is not None:
    try:
        df = normalize_meyer_rows(read_uploaded_file(uploaded_file))
        required_cols = ["mesaitarih", "NM", "FM"]

        if not all(col in df.columns for col in required_cols):
            st.error(f"Dosyada zorunlu sütunlar eksik: {', '.join(required_cols)}")
        else:
            with st.expander("Ham veri düzenleme", expanded=False):
                st.info("NM, FM veya izin sütunlarını düzenleyebilirsiniz. Değişiklikler anında yansır.")
                edited_df = st.data_editor(df, use_container_width=True, num_rows="dynamic", key="editor")

            processed_df, daily_df, weekly_df, summary = calculate_puantaj(edited_df)

            st.divider()
            st.subheader("Özet")

            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Toplam NM", hours_to_time(summary["toplam_nm"]))
            m2.metric("Toplam FM", hours_to_time(summary["toplam_fm"]))
            m3.metric("Çalışılan Gün", summary["calisma_gun"])
            m4.metric("Devamsızlık", f"{summary['devamsizlik_gun']} gün")

            m5, m6, m7, m8 = st.columns(4)
            m5.metric(
                "Ücretli İzin",
                f"{summary['ucretli_izin_gun']} gün",
                delta=hours_to_time(summary["ucretli_izin_saat"]) + " saat",
                delta_color="off",
            )
            m6.metric(
                "Ücretsiz İzin",
                f"{summary['ucretsiz_izin_gun']} gün",
                delta=hours_to_time(summary["ucretsiz_izin_saat"]) + " saat" if summary["ucretsiz_izin_gun"] else None,
                delta_color="off",
            )
            m7.metric("Hafta Sayısı", len(weekly_df))
            m8.metric("Toplam Kayıt", len(daily_df))

            m9, m10 = st.columns(2)
            m9.metric("Devamsızlık Saati", hours_to_time(summary["devamsizlik_saat"]))
            m10.metric("Pazar Yanan Hafta", summary["pazar_yanan_hafta"])

            st.divider()
            st.subheader("Günlük Özet")
            st.dataframe(daily_df, use_container_width=True, hide_index=True)

            st.subheader("Haftalık Mesai Dağılımı")
            st.caption("45 saat kuralı sonrası NM/FM toplamları ve pazar kesinti durumu.")
            st.dataframe(weekly_df, use_container_width=True, hide_index=True)

            with st.expander("Tam detay tablosu", expanded=False):
                st.dataframe(processed_df, use_container_width=True)

            export_df = daily_df.copy()
            csv_buffer = io.StringIO()
            export_df.to_csv(csv_buffer, sep=";", index=False, encoding="utf-8")

            st.download_button(
                "Günlük özeti indir (CSV)",
                data=csv_buffer.getvalue(),
                file_name="Puantaj_Ozet.csv",
                mime="text/csv",
                type="primary",
            )

    except Exception as e:
        st.error(f"Dosya işlenirken hata oluştu: {e}")
