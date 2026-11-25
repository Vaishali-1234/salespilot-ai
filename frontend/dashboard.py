"""Page 1: Overview Dashboard."""

import pandas as pd
import streamlit as st

from frontend.api_client import api_client
from frontend.styles import category_pill, render_hero, render_kpi_card


def render_overview_page(health: dict) -> None:
    llm_stat = health.get("llm_status", {})
    is_demo = llm_stat.get("is_demo_mode", True)
    badge = (
        '<span class="sp-pill sp-pill-demo">Demo Fallback Mode</span>'
        if is_demo
        else '<span class="sp-pill sp-pill-live">Live Gemini AI</span>'
    )
    render_hero(
        "SalesPilot AI — Executive Overview",
        "Autonomous AI Voice Sales Representative for TechNova Solutions",
        badge_html=badge,
    )

    analytics = api_client.get_analytics()
    leads = api_client.list_leads().get("leads", [])
    appts = api_client.list_appointments(status="Confirmed").get("appointments", [])

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        render_kpi_card("Total Calls", str(analytics.get("total_calls", 0)), "Isolated voice & chat sessions")
    with c2:
        render_kpi_card("Total Leads", str(analytics.get("total_leads", 0)), f"Avg score: {analytics.get('average_lead_score', 0)}/100")
    with c3:
        render_kpi_card("Appointments Booked", str(analytics.get("appointments_booked", 0)), "Double-booking guarded")
    with c4:
        render_kpi_card("Conversion Rate", f"{analytics.get('lead_conversion_rate', 0.0)}%", "Leads -> Confirmed Demos")

    st.markdown("### System Stack Health")
    s1, s2, s3, s4 = st.columns(4)
    with s1:
        st.info(f"**LLM Engine:** {llm_stat.get('model', 'unknown')}\n\nMode: `{llm_stat.get('active_mode')}`")
    with s2:
        st.info(f"**RAG Index:** FAISS + `{health.get('embedding_mode')}`\n\nIndexed Chunks: `{health.get('total_kb_chunks', 0)}`")
    with s3:
        st.info(f"**Speech-to-Text:** Faster-Whisper\n\nModel: `{health.get('whisper_model', 'base')}`")
    with s4:
        st.info(f"**Text-to-Speech:** Edge TTS\n\nVoice: `{health.get('edge_tts_voice', 'en-US-AriaNeural')}`")

    col_left, col_right = st.columns([3, 2])
    with col_left:
        st.markdown("### Recent Qualified Leads")
        if leads:
            df = pd.DataFrame(leads)[
                ["id", "name", "company_name", "interested_service", "lead_score", "lead_category", "status"]
            ].head(8)
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.caption("No leads yet. Launch a call on the **Live AI Sales Agent** page to qualify your first customer.")

    with col_right:
        st.markdown("### Upcoming Confirmed Demos")
        if appts:
            for a in appts[:5]:
                st.markdown(
                    f"""
                    <div class="sp-card">
                        <strong>{a['customer_name']}</strong> ({a['customer_email']})<br/>
                        <span style="color:#2563EB;font-weight:600;">{a['appointment_date']} • {a['appointment_time']}</span><br/>
                        <small style="color:#64748B;">{a['topic']}</small>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
        else:
            st.caption("No confirmed appointments yet.")

    if leads:
        dist = analytics.get("lead_distribution", {})
        st.markdown(
            f"**Pipeline Snapshot:** "
            f"{category_pill('Hot')} {dist.get('Hot', 0)} &nbsp;&nbsp; "
            f"{category_pill('Warm')} {dist.get('Warm', 0)} &nbsp;&nbsp; "
            f"{category_pill('Cold')} {dist.get('Cold', 0)}",
            unsafe_allow_html=True,
        )
