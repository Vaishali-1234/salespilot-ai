"""Page 8: Settings & System Diagnostics."""

import streamlit as st

from frontend.api_client import api_client
from frontend.styles import render_hero


def render_settings_page(health: dict) -> None:
    render_hero(
        "Settings & System Configuration",
        "Manage runtime AI credentials, Edge TTS voice selection, and inspect layered architecture diagnostics.",
    )

    llm_stat = health.get("llm_status", {})
    if llm_stat.get("is_demo_mode"):
        st.warning(f"**Current Mode:** {llm_stat.get('message')}")
    else:
        st.success(f"**Current Mode:** {llm_stat.get('message')}")

    with st.form("runtime_settings_form"):
        st.markdown("### Runtime AI & Voice Settings")
        api_key = st.text_input(
            "Google Gemini API Key (stored in backend process memory only for this session; use .env for persistence)",
            type="password",
            placeholder="AIza...",
        )
        voices = [
            "en-US-AriaNeural",
            "en-US-JennyNeural",
            "en-US-GuyNeural",
            "en-IN-NeerjaNeural",
            "en-IN-PrabhatNeural",
            "en-GB-SoniaNeural",
        ]
        current_voice = health.get("edge_tts_voice", "en-US-AriaNeural")
        voice_idx = voices.index(current_voice) if current_voice in voices else 0
        chosen_voice = st.selectbox("Edge TTS Voice", voices, index=voice_idx)

        if st.form_submit_button("Apply Runtime Settings", type="primary"):
            payload_key = api_key.strip() if api_key.strip() else None
            res = api_client.update_config(gemini_api_key=payload_key, edge_tts_voice=chosen_voice)
            st.success(f"Updated! Active LLM: `{res['llm_status']['active_mode']}`, Voice: `{res['edge_tts_voice']}`")
            st.rerun()

    st.markdown("### Live Backend Health Telemetry (`/health`)")
    st.json(health)
