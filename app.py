import streamlit as st
import pandas as pd
import io
from datetime import time, timedelta

# Sayfa Ayarları
st.set_page_config(page_title="Puantaj & Mesai Hesaplayıcı", layout="wide")
st.title("Dinamik Puantaj ve Fazla Mesai Hesaplayıcı")

# Saat dönüştürme yardımcı fonksiyonları
def time_to_hours(value):
    if pd.isna(value) or (isinstance(value, str) and value.strip() == ''):
        return 0.0
    if isinstance(value, (pd.Timedelta, timedelta)):
        return value.total_seconds() / 3600.0
    if isinstance(value, time):
        return value.hour + value.minute / 60.0 + value.second / 3600.0
    if isinstance(value, pd.Timestamp):
        return value.hour + value.minute / 60.0 + value.second / 3600.0

    text = str(value).strip()
    if 'day' in text:
        try:
            return pd.to_timedelta(text).total_seconds() / 3600.0
        except (ValueError, TypeError):
            return 0.0

    parts = text.split(':')
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
    if name.endswith('.csv'):
        for encoding in ('cp1254', 'utf-8', 'utf-8-sig', 'latin-1'):
            try:
                uploaded_file.seek(0)
                return pd.read_csv(uploaded_file, sep=';', encoding=encoding)
            except UnicodeDecodeError:
                continue
        uploaded_file.seek(0)
        return pd.read_csv(uploaded_file, sep=';', encoding='utf-8', errors='replace')
    if name.endswith('.xls') and not name.endswith('.xlsx'):
        return pd.read_excel(uploaded_file, engine='xlrd')
    return pd.read_excel(uploaded_file, engine='openpyxl')

# Hesaplama Mantığı (Kanuni Kural)
WEEKLY_MAX_HOURS = 45.0
WEEKLY_MIN_HOURS = 37.5
DAILY_WORK_HOURS = 7.5

PAID_LEAVE_COLUMNS = ('IZS', 'YIZS', 'SGKIZS', 'EM', 'İzin Açıklama', 'RM')
UNPAID_LEAVE_COLUMN = 'UCZIZS'

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
    izin_col = resolve_column(df, 'İzin Açıklama', keyword='zin')
    if izin_col and izin_col != 'İzin Açıklama':
        df = df.rename(columns={izin_col: 'İzin Açıklama'})
    return df

def normalize_meyer_rows(df):
    df = normalize_meyer_columns(df.copy())

    if pd.api.types.is_datetime64_any_dtype(df['mesaitarih']):
        df['mesaitarih_dt'] = pd.to_datetime(df['mesaitarih'], errors='coerce')
    else:
        df['mesaitarih_dt'] = pd.to_datetime(df['mesaitarih'], format='%d.%m.%Y', dayfirst=True, errors='coerce')

    df = df.dropna(subset=['mesaitarih_dt'])
    if 'sicilno' in df.columns:
        df = df[df['sicilno'].notna()]

    return df.reset_index(drop=True)

def is_placeholder(value):
    if pd.isna(value):
        return True
    text = str(value).strip()
    return text == '' or text == '#__#'

def column_hours(row, column):
    if column not in row.index or is_placeholder(row[column]):
        return 0.0
    return time_to_hours(row[column])

def paid_leave_hours(row):
    nm_h = column_hours(row, 'NM')
    izin_from_codes = max(
        (column_hours(row, col) for col in ('IZS', 'YIZS', 'SGKIZS', 'RM', 'İzin Açıklama')),
        default=0.0,
    )
    if izin_from_codes > 0:
        return izin_from_codes

    # Meyer Excel/CSV: tam gün ücretli izin genelde NM=0 iken EM'de 09:00 olarak görünür.
    # Küçük EM değerleri (ör. 00:11) eksik mesaidir, izin değildir.
    em_h = column_hours(row, 'EM')
    if nm_h < 0.1 and em_h >= DAILY_WORK_HOURS:
        return em_h

    return 0.0

def unpaid_leave_hours(row):
    return column_hours(row, UNPAID_LEAVE_COLUMN)

def day_quota_credit(row, is_weekday):
    nm_h = column_hours(row, 'NM')
    unpaid_h = unpaid_leave_hours(row)
    paid_h = paid_leave_hours(row)

    if unpaid_h > 0:
        return 0.0, 'Ücretsiz İzin', unpaid_h

    if paid_h > 0:
        credit = DAILY_WORK_HOURS if paid_h >= DAILY_WORK_HOURS else paid_h
        return credit, 'Ücretli İzin / Rapor', 0.0

    if nm_h > 0:
        return nm_h, 'Çalışma', 0.0

    if is_weekday:
        return 0.0, 'Devamsızlık', 0.0

    return 0.0, 'Hafta Sonu', 0.0

def calculate_puantaj(df):
    df_calc = normalize_meyer_rows(df)
    
    df_calc['NM_h'] = df_calc['NM'].apply(time_to_hours)
    df_calc['FM_h'] = df_calc['FM'].apply(time_to_hours)
    df_calc['day_of_week'] = df_calc['mesaitarih_dt'].dt.dayofweek
    iso = df_calc['mesaitarih_dt'].dt.isocalendar()
    df_calc['year'] = iso.year
    df_calc['week'] = iso.week

    weekday_flags = df_calc['day_of_week'] < 5
    quota_info = df_calc.apply(
        lambda row: day_quota_credit(row, weekday_flags.loc[row.name]),
        axis=1,
        result_type='expand',
    )
    df_calc['quota_h'] = quota_info[0]
    df_calc['gun_durumu'] = quota_info[1]
    
    weekly_checks = []
    
    for (year, week) in df_calc[['year', 'week']].dropna().drop_duplicates().itertuples(index=False):
        week_mask = (df_calc['year'] == year) & (df_calc['week'] == week)
        weekday_mask = week_mask & (df_calc['day_of_week'] < 5)
        weekend_mask = week_mask & (df_calc['day_of_week'] >= 5)
        
        weekday_nm = df_calc.loc[weekday_mask, 'NM_h'].sum()
        missing_nm = max(0, WEEKLY_MAX_HOURS - weekday_nm)
        
        # Hafta içi eksik varsa, hafta sonu mesaisinden (FM) düş, Normal Mesaiye (NM) ekle
        if missing_nm > 0:
            weekend_indices = df_calc[weekend_mask].index
            for idx in weekend_indices:
                fm_available = df_calc.loc[idx, 'FM_h']
                if fm_available > 0 and missing_nm > 0:
                    deduct = min(missing_nm, fm_available)
                    df_calc.loc[idx, 'FM_h'] -= deduct
                    df_calc.loc[idx, 'NM_h'] += deduct
                    missing_nm -= deduct

        weekday_rows = df_calc.loc[weekday_mask]
        quota_total = weekday_rows['quota_h'].sum()
        weekday_count = len(weekday_rows)
        expected_quota = DAILY_WORK_HOURS * weekday_count

        devamsizlik_gun = int((weekday_rows['gun_durumu'] == 'Devamsızlık').sum())
        ucretsiz_izin_gun = int((weekday_rows['gun_durumu'] == 'Ücretsiz İzin').sum())
        below_min = quota_total < expected_quota
        eksik_saat_h = max(0, expected_quota - quota_total) if below_min else 0.0
        eksik_gun = round(eksik_saat_h / DAILY_WORK_HOURS, 2) if below_min else 0.0
        hafta_tatili_yanar = below_min
        weekend_rest_days = int(weekend_mask.sum())
        sgk_kod15_gun = devamsizlik_gun + (weekend_rest_days if hafta_tatili_yanar else 0)

        week_start = df_calc.loc[week_mask, 'mesaitarih_dt'].min()
        weekly_checks.append({
            'Hafta': f"{week_start.strftime('%d.%m.%Y')} (H{int(week)})",
            'Beklenen Kota': hours_to_time(expected_quota),
            'Kotaya Sayılan': hours_to_time(quota_total),
            'Durum': 'Eksik Kota' if below_min else 'Tam',
            'Eksik Saat': hours_to_time(eksik_saat_h) if below_min else '00:00',
            'Eksik Gün': eksik_gun,
            'Devamsızlık Günü': devamsizlik_gun,
            'Ücretsiz İzin Günü': ucretsiz_izin_gun,
            'Hafta Tatili': 'Yanar' if hafta_tatili_yanar else 'Hak Edildi',
            'SGK Kod 15 (Tahmini)': sgk_kod15_gun,
        })

    weekly_df = pd.DataFrame(weekly_checks)

    # Geri HH:MM formatına çevir
    df_calc['NM (Güncel)'] = df_calc['NM_h'].apply(hours_to_time)
    df_calc['FM (Güncel)'] = df_calc['FM_h'].apply(hours_to_time)
    df_calc['Kotaya Sayılan'] = df_calc['quota_h'].apply(hours_to_time)
    df_calc['Gün Durumu'] = df_calc['gun_durumu']
    
    total_nm_h = df_calc['NM_h'].sum()
    total_fm_h = df_calc['FM_h'].sum()
    
    # Gereksiz hesap sütunlarını sil
    df_calc = df_calc.drop(columns=['mesaitarih_dt', 'NM_h', 'FM_h', 'day_of_week', 'year', 'week', 'quota_h', 'gun_durumu'])
    
    return df_calc, hours_to_time(total_nm_h), hours_to_time(total_fm_h), weekly_df

# Dosya Yükleme Alanı
uploaded_file = st.file_uploader("Lütfen Puantaj Dosyanızı Yükleyin (CSV veya Excel)", type=["csv", "xlsx", "xls"])

if uploaded_file is not None:
    try:
        df = normalize_meyer_rows(read_uploaded_file(uploaded_file))
            
        required_cols = ['mesaitarih', 'NM', 'FM']
        if not all(col in df.columns for col in required_cols):
            st.error(f"Hata: Yüklenen dosyada {', '.join(required_cols)} sütunları bulunamadı!")
        else:
            st.subheader("1. Ham Veri Düzenleme Alanı")
            st.info("Aşağıdaki tablo üzerinden giriş-çıkış saatlerini veya NM/FM sürelerini manuel değiştirebilirsiniz. Değişiklik yaptığınız anda sonuçlar otomatik güncellenir.")
            
            # Dinamik tablo (Kullanıcı arayüzde düzenleme yapabilir)
            edited_df = st.data_editor(df, use_container_width=True, num_rows="dynamic")
            
            # Düzenlenmiş veri üzerinden hesaplama yap
            processed_df, total_nm, total_fm, weekly_df = calculate_puantaj(edited_df)
            
            st.markdown("---")
            st.subheader("2. Kanuni Kesintiler Uygulanmış Sonuçlar")
            
            # Metrikleri Göster
            col1, col2 = st.columns(2)
            col1.metric("Toplam Normal Mesai (NM)", total_nm)
            col2.metric("Toplam Fazla Mesai (FM)", total_fm)

            eksik_haftalar = weekly_df[weekly_df['Durum'] == 'Eksik Kota']
            if not eksik_haftalar.empty:
                st.warning(
                    f"{len(eksik_haftalar)} haftada çalışma kotası (37,5 saat) tamamlanmadı. "
                    "Bu haftalarda hafta tatili yanabilir ve SGK eksik gün oluşabilir."
                )

            st.subheader("3. Haftalık Kota Kontrolü (37,5 saat)")
            st.caption(
                "Kotaya sayılan süre = fiili NM + ücretli izin/rapor (IZS, YIZS, SGKIZS, EM, İzin Açıklama, RM). "
                "Ücretsiz izin ve mazeretsiz devamsızlık kotaya dahil edilmez. "
                "Ay sonu kısmi haftalarda beklenen kota, o haftadaki iş günü sayısına göre hesaplanır."
            )
            st.dataframe(weekly_df, use_container_width=True, hide_index=True)

            toplam_sgk = int(weekly_df['SGK Kod 15 (Tahmini)'].sum())
            if toplam_sgk > 0:
                st.metric("Toplam SGK Kod 15 Günü (Tahmini)", toplam_sgk)
            
            st.dataframe(processed_df, use_container_width=True)
            
            # İndirme Butonu Hazırlığı
            csv_buffer = io.StringIO()
            processed_df.to_csv(csv_buffer, sep=';', index=False, encoding='utf-8')
            
            st.download_button(
                label="Dışa Aktar (CSV)",
                data=csv_buffer.getvalue(),
                file_name="Guncel_Puantaj_Hesaplanmis.csv",
                mime="text/csv",
                type="primary"
            )
            
    except Exception as e:
        st.error(f"Dosya işlenirken bir hata oluştu: {e}")