import streamlit as st
import pandas as pd
import io

# Sayfa Ayarları
st.set_page_config(page_title="Puantaj & Mesai Hesaplayıcı", layout="wide")
st.title("Dinamik Puantaj ve Fazla Mesai Hesaplayıcı")

# Saat dönüştürme yardımcı fonksiyonları
def time_to_hours(time_str):
    if pd.isna(time_str) or str(time_str).strip() == '': return 0.0
    parts = str(time_str).split(':')
    try:
        if len(parts) >= 2:
            return int(parts[0]) + int(parts[1])/60.0
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
        for encoding in ('utf-8', 'utf-8-sig', 'cp1254', 'latin-1'):
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
def calculate_puantaj(df):
    df_calc = df.copy()
    
    # Meyer özet/boş satırlarını temizle
    df_calc = df_calc.dropna(subset=['mesaitarih'])
    df_calc = df_calc[df_calc['mesaitarih'].str.match(r'\d{1,2}\.\d{1,2}\.\d{4}', na=False)]
    
    df_calc['mesaitarih_dt'] = pd.to_datetime(df_calc['mesaitarih'], format='%d.%m.%Y', errors='coerce')
    
    df_calc['NM_h'] = df_calc['NM'].apply(time_to_hours)
    df_calc['FM_h'] = df_calc['FM'].apply(time_to_hours)
    df_calc['day_of_week'] = df_calc['mesaitarih_dt'].dt.dayofweek
    df_calc['week'] = df_calc['mesaitarih_dt'].dt.isocalendar().week
    
    for week in df_calc['week'].dropna().unique():
        week_mask = df_calc['week'] == week
        weekday_mask = week_mask & (df_calc['day_of_week'] < 5)
        weekend_mask = week_mask & (df_calc['day_of_week'] >= 5)
        
        weekday_nm = df_calc.loc[weekday_mask, 'NM_h'].sum()
        missing_nm = max(0, 45.0 - weekday_nm)
        
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

    # Geri HH:MM formatına çevir
    df_calc['NM (Güncel)'] = df_calc['NM_h'].apply(hours_to_time)
    df_calc['FM (Güncel)'] = df_calc['FM_h'].apply(hours_to_time)
    
    total_nm_h = df_calc['NM_h'].sum()
    total_fm_h = df_calc['FM_h'].sum()
    
    # Gereksiz hesap sütunlarını sil
    df_calc = df_calc.drop(columns=['mesaitarih_dt', 'NM_h', 'FM_h', 'day_of_week', 'week'])
    
    return df_calc, hours_to_time(total_nm_h), hours_to_time(total_fm_h)

# Dosya Yükleme Alanı
uploaded_file = st.file_uploader("Lütfen Puantaj Dosyanızı Yükleyin (CSV veya Excel)", type=["csv", "xlsx", "xls"])

if uploaded_file is not None:
    try:
        df = read_uploaded_file(uploaded_file)
            
        required_cols = ['mesaitarih', 'NM', 'FM']
        if not all(col in df.columns for col in required_cols):
            st.error(f"Hata: Yüklenen dosyada {', '.join(required_cols)} sütunları bulunamadı!")
        else:
            st.subheader("1. Ham Veri Düzenleme Alanı")
            st.info("Aşağıdaki tablo üzerinden giriş-çıkış saatlerini veya NM/FM sürelerini manuel değiştirebilirsiniz. Değişiklik yaptığınız anda sonuçlar otomatik güncellenir.")
            
            # Dinamik tablo (Kullanıcı arayüzde düzenleme yapabilir)
            edited_df = st.data_editor(df, use_container_width=True, num_rows="dynamic")
            
            # Düzenlenmiş veri üzerinden hesaplama yap
            processed_df, total_nm, total_fm = calculate_puantaj(edited_df)
            
            st.markdown("---")
            st.subheader("2. Kanuni Kesintiler Uygulanmış Sonuçlar")
            
            # Metrikleri Göster
            col1, col2 = st.columns(2)
            col1.metric("Toplam Normal Mesai (NM)", total_nm)
            col2.metric("Toplam Fazla Mesai (FM)", total_fm)
            
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