"""Uygulamanın sayfaları arasında üst sekme navigasyonu."""

import streamlit as st


def render_top_navigation(active_page: str) -> None:
    st.markdown(
        """
        <style>
        [data-testid="stSidebar"], [data-testid="collapsedControl"],
        [data-testid="stSidebarCollapsedControl"] {
            display: none;
        }
        .st-key-top_navigation {
            border-bottom: 1px solid #d9e2ec;
            margin-bottom: 1.25rem;
            padding-bottom: 0;
        }
        .st-key-top_navigation [data-testid="stHorizontalBlock"] {
            gap: 0.35rem;
        }
        .st-key-top_navigation button {
            border-radius: 0.55rem 0.55rem 0 0;
            border-bottom-width: 3px;
            min-height: 2.85rem;
            font-weight: 650;
        }
        .st-key-top_navigation button[kind="primary"] {
            background: #16324f;
            border-color: #16324f;
            color: white;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    with st.container(key="top_navigation"):
        calculator_tab, report_tab, _ = st.columns([1.15, 1.15, 3.7])
        with calculator_tab:
            calculator_clicked = st.button(
                "Puantaj Hesaplama",
                key="nav_calculator",
                type="primary" if active_page == "calculator" else "secondary",
                width="stretch",
            )
        with report_tab:
            report_clicked = st.button(
                "Puantaj Raporu V2",
                key="nav_report",
                type="primary" if active_page == "report" else "secondary",
                width="stretch",
            )
    if calculator_clicked and active_page != "calculator":
        st.switch_page("app.py")
    if report_clicked and active_page != "report":
        st.switch_page("pages/2_Aylik_Puantaj_Raporu.py")
