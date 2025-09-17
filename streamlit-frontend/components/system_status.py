"""
System status indicator component
"""
import streamlit as st
from utils.api_client import api_client


def render_system_status():
    """Render system health status indicator"""
    st.markdown('<div class="system-status">', unsafe_allow_html=True)

    if api_client.check_health():
        st.markdown("🟢")
    else:
        st.markdown("🔴")

    st.markdown('</div>', unsafe_allow_html=True)