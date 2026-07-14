import streamlit as st
import pandas as pd
import io
from datetime import time, timedelta
from ui_navigation import render_top_navigation

st.set_page_config(page_title="Puantaj Hesaplama", layout="wide", initial_sidebar_state="collapsed")
render_top_navigation("calculator")

WEEKLY_MAX_HOURS = 45.0
DAILY_WORK_HOURS = 9.0
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
    name = str(getattr(uploaded_file, "name", "")).lower()
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
    return employee_df[employee_df["sicilno"] == str(sicilno)].copy()

def render_employee_detail(df, employee_label):
    required_cols = ["mesaitarih", "NM", "FM"]
    if not all(col in df.columns for col in required_cols):
        st.error(f"Dosyada zorunlu sütunlar eksik: {', '.join(required_cols)}")
        return

    st.subheader(employee_label)

    with st.expander("Ham veri düzenleme", expanded=False):
        st.info("NM, FM veya izin sütunlarını düzenleyebilirsiniz. Değişiklikler anında yansır.")
        edited_df = st.data_editor(
            df, use_container_width=True, num_rows="dynamic", key=f"editor_{employee_label}"
        )

    processed_df, daily_df, weekly_df, leave_breakdown_df, summary = calculate_puantaj(edited_df)

    st.divider()
    st.subheader("Özet")
    st.caption(f"**Dönem:** {summary['donem']} · **Toplam kayıt:** {summary['toplam_gun']} gün")

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Toplam NM", hours_to_time(summary["toplam_nm"]))
    m2.metric("Toplam FM", hours_to_time(summary["toplam_fm"]))
    m3.metric("Çalışılan Gün", summary["calisma_gun"])
    m4.metric("Pazar Kesilen Hafta", summary["pazar_yanan_hafta"])

    st.markdown("**İzin, rapor ve devamsızlık dağılımı**")
    st.dataframe(leave_breakdown_df, use_container_width=True, hide_index=True)

    st.markdown("**Dönem ve hafta bilgisi**")
    h1, h2, h3, h4 = st.columns(4)
    h1.metric("ISO Hafta Sayısı", summary["iso_hafta_sayisi"])
    h2.metric("Tam Hafta", summary["tam_hafta_sayisi"])
    h3.metric("Kısmi Hafta", summary["kisami_hafta_sayisi"])
    h4.metric("Devamsızlık", f"{summary['devamsizlik_gun']} gün · {hours_to_time(summary['devamsizlik_saat'])}")

    st.info(
        "Hafta sayısı takvim ayına göre sabit değildir. Dosyadaki tarihlerin düştüğü "
        "**ISO haftaları** (Pazartesi–Pazar) sayılır. Ayın 1'i veya son günü haftanın ortasındaysa "
        "o hafta **kısmi** görünür; dosyada o haftaya ait kaç gün varsa o kadar gün listelenir."
    )

    st.divider()
    st.subheader("Günlük Özet")
    st.dataframe(daily_df, use_container_width=True, hide_index=True)

    st.subheader("Haftalık Mesai Dağılımı")
    st.caption("45 saat kuralı sonrası NM/FM toplamları ve pazar kesinti durumu.")
    st.dataframe(weekly_df, use_container_width=True, hide_index=True)

    with st.expander("Tam detay tablosu", expanded=False):
        st.dataframe(processed_df, use_container_width=True)

    safe_name = employee_label.replace(" ", "_")
    csv_buffer = io.StringIO()
    daily_df.to_csv(csv_buffer, sep=";", index=False, encoding="utf-8")
    st.download_button(
        "Günlük özeti indir (CSV)",
        data=csv_buffer.getvalue(),
        file_name=f"Puantaj_{safe_name}.csv",
        mime="text/csv",
        type="primary",
    )

def render_employee_list(employee_list):
    st.subheader("Personel Listesi")
    st.caption("Bir personel satırına tıklayın; hesaplama ekranı açılır.")

    search = st.text_input("Personel ara", placeholder="Ad veya soyad yazın...")
    filtered = employee_list.copy()
    if search.strip():
        mask = (
            filtered["Ad"].str.contains(search, case=False, na=False)
            | filtered["Soyad"].str.contains(search, case=False, na=False)
        )
        filtered = filtered[mask]

    st.metric("Personel Sayısı", len(filtered))

    display_cols = list(filtered.columns)
    selection = st.dataframe(
        filtered[display_cols],
        use_container_width=True,
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row",
        key="employee_table",
    )

    if selection.selection.rows:
        row = filtered.iloc[selection.selection.rows[0]]
        st.session_state.selected_sicilno = row["sicilno"]
        st.session_state.selected_employee_name = f"{row['Ad']} {row['Soyad']}"
        st.rerun()

# ── Arayüz ─────────────────────────────────────────────────────────────────

st.title("Puantaj Hesaplama")
st.caption("Meyer puantaj dosyalarından mesai düzenlemesi, izin ayrımı ve haftalık FM→NM aktarımı.")

with st.expander("Nasıl çalışır?", expanded=False):
    st.markdown("""
**Dosya türleri**  
- **Toplu dosya** (tüm personel): Önce personel listesi açılır; satıra tıklayınca o kişinin hesaplama ekranı gelir.  
- **Tekil dosya** (tek personel): Doğrudan hesaplama ekranı açılır.

**45 saat kuralı**  
Hafta içi toplam NM 45 saatin altındaysa, hafta sonu FM saatleri otomatik olarak NM'ye aktarılır.

**İzin entegrasyonu** (Meyer sütunları)  
| Sütun | Anlam |
|-------|-------|
| `IZS`, `YIZS`, `SGKIZS`, `RM` | Ücretli izin / rapor (saatlik) |
| `EM` | Tam gün ücretli izin (NM=0 ve EM≥9 saat) |
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
    help="Tek personel dosyası veya tüm personeli içeren Meyer puantaj dosyası",
)

if "master_df" not in st.session_state:
    st.session_state.master_df = None
if "uploaded_name" not in st.session_state:
    st.session_state.uploaded_name = None
if "selected_sicilno" not in st.session_state:
    st.session_state.selected_sicilno = None
if "selected_employee_name" not in st.session_state:
    st.session_state.selected_employee_name = None

if uploaded_file is not None:
    try:
        if uploaded_file.name != st.session_state.uploaded_name:
            st.session_state.uploaded_name = uploaded_file.name
            st.session_state.master_df = read_uploaded_file(uploaded_file)
            st.session_state.selected_sicilno = None
            st.session_state.selected_employee_name = None

        master_df = st.session_state.master_df
        bulk = is_bulk_file(master_df)

        if bulk and st.session_state.selected_sicilno:
            if st.button("← Personel listesine dön", type="secondary"):
                st.session_state.selected_sicilno = None
                st.session_state.selected_employee_name = None
                st.rerun()

            employee_df = filter_employee_df(master_df, st.session_state.selected_sicilno)
            employee_df = normalize_meyer_rows(employee_df)
            render_employee_detail(employee_df, st.session_state.selected_employee_name)

        elif bulk:
            employee_list = build_employee_list(master_df)
            render_employee_list(employee_list)

        else:
            df = normalize_meyer_rows(master_df)
            employee_name = "Personel"
            if "Ad" in df.columns and "Soyad" in df.columns and not df.empty:
                employee_name = f"{df['Ad'].iloc[0]} {df['Soyad'].iloc[0]}"
            render_employee_detail(df, employee_name)

    except Exception as e:
        st.error(f"Dosya işlenirken hata oluştu: {e}")
