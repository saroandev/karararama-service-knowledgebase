"""
Settings modal component
"""
import streamlit as st
from config.settings import API_BASE_URL


def render_settings_modal():
    """Render the settings modal"""
    if not st.session_state.show_settings:
        return

    with st.expander("⚙️ Ayarlar", expanded=True):
        st.markdown("### API Ayarları")
        st.text_input("API URL", value=API_BASE_URL, disabled=True)

        st.markdown("### Sorgu Ayarları")
        default_top_k = st.slider("Varsayılan sonuç sayısı (top_k)", 1, 20, 5)
        use_reranker = st.checkbox("Reranker kullan", value=True)

        st.markdown("### Görünüm")
        dark_mode = st.checkbox("Karanlık Mod", value=False)

        if st.button("Kaydet", type="primary"):
            st.session_state.show_settings = False
            st.rerun()