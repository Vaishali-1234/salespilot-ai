"""SalesPilot AI — Streamlit Multi-Page SaaS Application Entrypoint."""

import streamlit as st

from frontend.analytics import render_analytics_page
from frontend.api_client import api_client
from frontend.appointments import render_appointments_page
from frontend.call_history import render_call_history_page
from frontend.crm import render_crm_page
from frontend.dashboard import render_overview_page
from frontend.knowledge_base import render_knowledge_base_page
from frontend.settings_page import render_settings_page
from frontend.styles import inject_custom_css
from frontend.voice_agent import render_voice_agent_page


st.set_page_config(
    page_title="SalesPilot AI — TechNova Solutions",
    page_icon="🎙️",
    layout="wide",
    initial_sidebar_state="expanded",
)

inject_custom_css()

PAGES = [
    "Live AI Sales Agent",
    "Overview Dashboard",
    "CRM / Lead Management",
    "Knowledge Base",
    "Appointment Management",
    "Call History",
    "Analytics",
    "Settings",
]

with st.sidebar:
    st.markdown("## 🎙️ SalesPilot AI")
    st.caption("TechNova Solutions • Autonomous Voice Agent")
    st.divider()
    selected_page = st.radio("Navigation", PAGES, index=0)
    st.divider()

    health = api_client.health()
    if health:
        llm_stat = health.get("llm_status", {})
        if llm_stat.get("is_demo_mode"):
            st.warning("AI Mode: **Demo Fallback**")
        else:
            st.success(f"AI Mode: **{llm_stat.get('model')}**")
        st.caption(f"Backend: Connected • KB Chunks: {health.get('total_kb_chunks', 0)}")
    else:
        st.error("FastAPI Backend Offline")
        st.code("uvicorn backend.main:app --reload", language="bash")

if not health:
    st.error(
        "Cannot connect to the FastAPI backend (`http://127.0.0.1:8000`). "
        "Please start the backend server in a second CMD window (first startup takes ~25-40s while loading AI/RAG models):\n\n"
        "`cd C:\\Users\\vvais\\.gemini\\antigravity\\scratch\\salespilot-ai`\n\n"
        "`uvicorn backend.main:app --host 127.0.0.1 --port 8000`"
    )
    if st.button("Retry Backend Connection", type="primary"):
        st.rerun()
    st.stop()

if selected_page == "Overview Dashboard":
    render_overview_page(health)
elif selected_page == "Live AI Sales Agent":
    render_voice_agent_page(health)
elif selected_page == "CRM / Lead Management":
    render_crm_page()
elif selected_page == "Knowledge Base":
    render_knowledge_base_page()
elif selected_page == "Appointment Management":
    render_appointments_page()
elif selected_page == "Call History":
    render_call_history_page()
elif selected_page == "Analytics":
    render_analytics_page()
elif selected_page == "Settings":
    render_settings_page(health)
