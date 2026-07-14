import streamlit as st

from puantaj_report import (
    CODE_LEGEND,
    available_periods,
    build_report,
    create_excel_report,
    format_hours,
    read_puantaj_file,
)
from ui_navigation import render_top_navigation


st.set_page_config(page_title="Puantaj Raporu V2", layout="wide", initial_sidebar_state="collapsed")
render_top_navigation("report")

st.title("Puantaj Raporu V2")
st.caption("Meyer kişi-gün kayıtlarını ve yeni excel formatıdaki yatay puantaj dosyalarını sade bir aylık rapora dönüştürür.")

with st.expander("Bu sayfa ne üretir?", expanded=False):
    st.markdown(
        """
- Her personel için ayın günlerini tek satırda gösteren **aylık puantaj matrisi**
- Normal çalışma, fazla mesai, izin, rapor ve devamsızlığı ayıran **personel özeti**
- Hafta sonu FM→NM aktarımı ve pazar kesintisini gösteren **haftalık kontrol**
- Kaynağa kadar izlenebilen **günlük detay** ve biçimlendirilmiş Excel raporu

Çalışılan günlerde hücre değeri `NM + FM` saati; diğer günlerde aşağıdaki durum kodudur.
"""
    )
    st.dataframe(CODE_LEGEND, width="stretch", hide_index=True)

uploaded = st.file_uploader(
    "Meyer puantaj dosyasını yükleyin",
    type=["xlsx", "xls", "csv"],
    help="Beklenen temel alanlar: sicilno, Ad, Soyad, mesaitarih, NM ve FM.",
)

if uploaded is not None:
    try:
        cache_key = ("sakra-v2", uploaded.name, uploaded.size)
        if st.session_state.get("report_upload_key") != cache_key:
            uploaded.seek(0)
            st.session_state.report_source_df = read_puantaj_file(uploaded, uploaded.name)
            st.session_state.report_upload_key = cache_key

        source_df = st.session_state.report_source_df
        periods = available_periods(source_df)
        if not periods:
            st.error("Dosyada geçerli bir mesaitarih alanı bulunamadı.")
            st.stop()

        labels = {f"{month:02d}.{year}": (year, month) for year, month in periods}
        selected_label = st.selectbox("Rapor dönemi", list(labels), index=len(labels) - 1)
        year, month = labels[selected_label]
        result = build_report(source_df, year, month)

        total_nm = result.summary["Normal Çalışma"].sum()
        total_fm = result.summary["Fazla Mesai"].sum()
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Personel", len(result.summary))
        c2.metric("Kişi-gün kaydı", len(result.daily))
        c3.metric("Normal çalışma", format_hours(total_nm))
        c4.metric("Fazla mesai", format_hours(total_fm))

        with st.expander("Veri kalitesi", expanded=False):
            st.dataframe(result.quality, width="stretch", hide_index=True)

        search = st.text_input("Personel ara", placeholder="Ad, soyad veya sicil no")
        matrix = result.monthly
        summary = result.summary
        weekly = result.weekly
        detail = result.daily
        if search.strip():
            query = search.strip()
            matrix = matrix[matrix["Personel"].str.contains(query, case=False, na=False) | matrix["Sicil No"].astype(str).str.contains(query, case=False, na=False)]
            selected_ids = set(matrix["Sicil No"])
            summary = summary[summary["Sicil No"].isin(selected_ids)]
            weekly = weekly[weekly["Sicil No"].isin(selected_ids)]
            detail = detail[detail["Sicil No"].isin(selected_ids)]

        tab_matrix, tab_summary, tab_weekly, tab_detail = st.tabs(
            ["Aylık Puantaj", "Personel Özeti", "Haftalık Kontrol", "Günlük Detay"]
        )
        with tab_matrix:
            st.dataframe(matrix, width="stretch", hide_index=True, height=520)
        with tab_summary:
            display_summary = summary.copy()
            for column in ("Normal Çalışma", "Fazla Mesai", "FM→NM Aktarım"):
                display_summary[column] = display_summary[column].map(format_hours)
            st.dataframe(display_summary, width="stretch", hide_index=True, height=520)
        with tab_weekly:
            display_weekly = weekly.copy()
            for column in ("Hafta İçi NM", "Hafta Sonu Ham FM", "FM→NM Aktarım", "Toplam NM", "Kalan FM"):
                display_weekly[column] = display_weekly[column].map(format_hours)
            st.dataframe(display_weekly, width="stretch", hide_index=True, height=520)
        with tab_detail:
            st.dataframe(detail, width="stretch", hide_index=True, height=520)

        report_bytes = create_excel_report(result)
        st.download_button(
            "Biçimlendirilmiş Excel raporunu indir",
            data=report_bytes,
            file_name=f"Aylik_Puantaj_Raporu_{year}_{month:02d}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary",
        )
    except Exception as exc:
        st.error(f"Dosya işlenirken hata oluştu: {exc}")
