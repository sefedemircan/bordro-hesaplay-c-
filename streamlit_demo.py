"""Yerel Streamlit demo — Vercel deploy'a dahil değildir.

Çalıştırma:
  pip install -r requirements-streamlit.txt
  streamlit run streamlit_demo.py
"""

from __future__ import annotations

import io

import streamlit as st

from puantaj_calc import (
    build_employee_list,
    calculate_puantaj,
    filter_employee_df,
    hours_to_time,
    is_bulk_file,
    normalize_meyer_rows,
    read_uploaded_file,
)
from puantaj_report import (
    CODE_LEGEND,
    available_periods,
    build_report,
    create_excel_report,
    format_hours,
    read_puantaj_file,
)

st.set_page_config(page_title="Puantaj Demo", layout="wide", initial_sidebar_state="collapsed")

page = st.radio(
    "Sayfa",
    ("Puantaj Hesaplama", "Puantaj Raporu V2"),
    horizontal=True,
    label_visibility="collapsed",
)


# ── Hesaplama ──────────────────────────────────────────────────────────────


def _render_employee_detail(df, employee_label):
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
    h4.metric(
        "Devamsızlık",
        f"{summary['devamsizlik_gun']} gün · {hours_to_time(summary['devamsizlik_saat'])}",
    )

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


def _render_employee_list(employee_list):
    st.subheader("Personel Listesi")
    st.caption("Bir personel satırına tıklayın; hesaplama ekranı açılır.")

    search = st.text_input("Personel ara", placeholder="Ad veya soyad yazın...", key="calc_search")
    filtered = employee_list.copy()
    if search.strip():
        mask = (
            filtered["Ad"].str.contains(search, case=False, na=False)
            | filtered["Soyad"].str.contains(search, case=False, na=False)
        )
        filtered = filtered[mask]

    st.metric("Personel Sayısı", len(filtered))

    selection = st.dataframe(
        filtered,
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


def render_calc_page():
    st.title("Puantaj Hesaplama")
    st.caption("Meyer puantaj dosyalarından mesai düzenlemesi, izin ayrımı ve haftalık FM→NM aktarımı.")

    with st.expander("Nasıl çalışır?", expanded=False):
        st.markdown(
            """
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
Yalnızca tek bir iş gününde `9:00` saat **mazeretsiz** devamsızlık varsa o haftada pazar "Yanar" olur.  
Rapor, yıllık/ücretli mazeret izni ve resmi tatiller çalışılmış sayılır; hafta tatili kesilmez.  
Parçalı devamsızlık toplamı `9:00` olsa bile pazar kesintisi tetiklenmez.
            """
        )

    uploaded_file = st.file_uploader(
        "Puantaj dosyası yükleyin",
        type=["csv", "xlsx", "xls"],
        help="Tek personel dosyası veya tüm personeli içeren Meyer puantaj dosyası",
        key="calc_uploader",
    )

    if "master_df" not in st.session_state:
        st.session_state.master_df = None
    if "uploaded_name" not in st.session_state:
        st.session_state.uploaded_name = None
    if "selected_sicilno" not in st.session_state:
        st.session_state.selected_sicilno = None
    if "selected_employee_name" not in st.session_state:
        st.session_state.selected_employee_name = None

    if uploaded_file is None:
        return

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
            _render_employee_detail(employee_df, st.session_state.selected_employee_name)

        elif bulk:
            _render_employee_list(build_employee_list(master_df))

        else:
            df = normalize_meyer_rows(master_df)
            employee_name = "Personel"
            if "Ad" in df.columns and "Soyad" in df.columns and not df.empty:
                employee_name = f"{df['Ad'].iloc[0]} {df['Soyad'].iloc[0]}"
            _render_employee_detail(df, employee_name)

    except Exception as exc:  # noqa: BLE001
        st.error(f"Dosya işlenirken hata oluştu: {exc}")


# ── Rapor ──────────────────────────────────────────────────────────────────


def render_report_page():
    st.title("Puantaj Raporu V2")
    st.caption(
        "Meyer kişi-gün kayıtlarını ve yeni excel formatıdaki yatay puantaj dosyalarını "
        "sade bir aylık rapora dönüştürür."
    )

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
        key="report_uploader",
    )

    if uploaded is None:
        return

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

        search = st.text_input(
            "Personel ara", placeholder="Ad, soyad veya sicil no", key="report_search"
        )
        matrix = result.monthly
        summary = result.summary
        weekly = result.weekly
        detail = result.daily
        if search.strip():
            query = search.strip()
            matrix = matrix[
                matrix["Personel"].str.contains(query, case=False, na=False)
                | matrix["Sicil No"].astype(str).str.contains(query, case=False, na=False)
            ]
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
            for column in (
                "Hafta İçi NM",
                "Hafta Sonu Ham FM",
                "FM→NM Aktarım",
                "Toplam NM",
                "Kalan FM",
            ):
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
    except Exception as exc:  # noqa: BLE001
        st.error(f"Dosya işlenirken hata oluştu: {exc}")


if page == "Puantaj Hesaplama":
    render_calc_page()
else:
    render_report_page()
