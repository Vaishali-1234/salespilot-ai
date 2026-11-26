"""Page 2: Live AI Sales Agent (Voice + Text + Real-Time CRM & RAG Telemetry)."""

import base64
from typing import Any, Dict, List
import plotly.graph_objects as go
import streamlit as st

from frontend.api_client import api_client
from frontend.styles import category_pill, render_hero


def _render_waveform(active: bool, status_label: str, sub_label: str) -> None:
    wave_cls = "sp-wave" if active else "sp-wave sp-wave-idle"
    bars = "".join(f'<div class="sp-wave-bar" style="height:{12 + (i % 4) * 6}px;"></div>' for i in range(8))
    st.markdown(
        f"""
        <div class="sp-voice-stage">
            <div>
                <div style="font-size:0.78rem;text-transform:uppercase;letter-spacing:0.08em;color:#93C5FD;font-weight:600;">
                    Voice Pipeline • Faster-Whisper STT → Agent Orchestrator → Edge TTS
                </div>
                <div style="font-size:1.12rem;font-weight:700;margin-top:0.2rem;">{status_label}</div>
                <div style="font-size:0.84rem;color:#CBD5E1;">{sub_label}</div>
            </div>
            <div class="{wave_cls}">{bars}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_score_gauge(score: int, category: str) -> None:
    color = "#DC2626" if category == "Hot" else ("#EA580C" if category == "Warm" else "#0284C7")
    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=score,
            domain={"x": [0, 1], "y": [0, 1]},
            title={"text": f"Lead Score ({category})", "font": {"size": 14}},
            gauge={
                "axis": {"range": [0, 100]},
                "bar": {"color": color},
                "steps": [
                    {"range": [0, 40], "color": "#E0F2FE"},
                    {"range": [40, 70], "color": "#FFEDD5"},
                    {"range": [70, 100], "color": "#FEE2E2"},
                ],
            },
        )
    )
    fig.update_layout(
        height=190,
        margin=dict(l=15, r=15, t=35, b=5),
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#0F172A"),
    )
    st.plotly_chart(fig, use_container_width=True)


def _init_voice_state() -> None:
    defaults = {
        "active_session_id": None,
        "active_lead_id": None,
        "chat_transcript": [],
        "latest_profile": {},
        "latest_qualification": {"lead_score": 0, "lead_category": "Cold", "score_reasoning": "Awaiting discovery."},
        "sentiment_history": [],
        "latest_rag_sources": [],
        "latest_tool_events": [],
        "latest_audio_b64": None,
        "latest_summary": None,
        "last_ai_mode": "unknown",
        "last_fallback_reason": None,
        "processed_audio_hashes": set(),
        "mic_counter": 0,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def _handle_turn_response(resp: Dict[str, Any], user_text: str) -> None:
    st.session_state.chat_transcript.append({"role": "user", "content": user_text, "sentiment": resp.get("sentiment")})
    st.session_state.chat_transcript.append(
        {
            "role": "assistant",
            "content": resp["reply"],
            "rag_sources": resp.get("rag_sources", []),
            "tool_events": resp.get("tool_events", []),
        }
    )
    st.session_state.latest_profile = resp.get("lead_profile", {})
    st.session_state.latest_qualification = resp.get("qualification", st.session_state.latest_qualification)
    st.session_state.latest_rag_sources = resp.get("rag_sources", [])
    st.session_state.latest_tool_events = resp.get("tool_events", [])
    st.session_state.latest_audio_b64 = resp.get("audio_b64")
    st.session_state.last_ai_mode = resp.get("ai_mode", "demo_fallback")
    st.session_state.last_fallback_reason = resp.get("fallback_reason")
    if resp.get("sentiment"):
        st.session_state.sentiment_history.append(resp["sentiment"])


def render_voice_agent_page(health: dict) -> None:
    _init_voice_state()
    llm_stat = health.get("llm_status", {})
    is_demo = llm_stat.get("is_demo_mode", True)

    badge = (
        '<span class="sp-pill sp-pill-demo">Demo Fallback Mode (Set GEMINI_API_KEY for Live LLM)</span>'
        if is_demo
        else '<span class="sp-pill sp-pill-live">Live Gemini AI Active</span>'
    )
    render_hero(
        "Live AI Sales Agent — TechNova Solutions",
        "Speak via microphone or chat by text. Real-time RAG, BANT qualification, sentiment tracking & autonomous CRM booking.",
        badge_html=badge,
    )

    # Top Action Bar
    b1, b2, b3, b4 = st.columns([1.4, 1.4, 1.4, 1.8])
    with b1:
        include_audio = st.toggle("Enable Voice Output (Edge TTS)", value=True)
    with b2:
        if st.button("Start New Sales Call", type="primary", use_container_width=True):
            res = api_client.start_session(mode="voice", include_audio=include_audio)
            st.session_state.active_session_id = res["session"]["id"]
            st.session_state.active_lead_id = res["session"]["lead_id"]
            st.session_state.chat_transcript = [{"role": "assistant", "content": res["greeting"], "rag_sources": [], "tool_events": []}]
            st.session_state.latest_profile = res.get("lead", {})
            st.session_state.latest_qualification = {"lead_score": 0, "lead_category": "Cold", "score_reasoning": "New session started."}
            st.session_state.sentiment_history = []
            st.session_state.latest_rag_sources = []
            st.session_state.latest_tool_events = []
            st.session_state.latest_audio_b64 = res.get("audio_b64")
            st.session_state.latest_summary = None
            st.session_state.last_ai_mode = res.get("llm_status", {}).get("active_mode", "demo_fallback")
            st.rerun()
    with b3:
        if st.button(
            "End Call & Save Summary",
            disabled=not st.session_state.active_session_id,
            use_container_width=True,
        ):
            res = api_client.end_session(st.session_state.active_session_id)
            st.session_state.latest_summary = res.get("summary")
            st.success("Call summary generated and saved to CRM!")
    with b4:
        if st.session_state.active_session_id:
            st.caption(f"Session ID: `{st.session_state.active_session_id}` | Lead ID: `#{st.session_state.active_lead_id}`")
        else:
            st.caption("No active session — click **Start New Sales Call**.")

    if not st.session_state.active_session_id:
        _render_waveform(False, "Standby — Ready to Connect", "Click 'Start New Sales Call' above to initialize an isolated CRM & Voice session.")
        return

    is_speaking = bool(st.session_state.latest_audio_b64)
    mode_label = (
        "Active Call — Demo Fallback Mode"
        if st.session_state.last_ai_mode == "demo_fallback"
        else f"Active Call — {st.session_state.last_ai_mode.upper()}"
    )
    _render_waveform(
        True,
        mode_label,
        "Speak into your microphone below or use text chat. Every turn updates RAG, Sentiment, Lead Score, and SQLite CRM.",
    )

    if st.session_state.last_ai_mode == "demo_fallback":
        st.warning(
            f"**Operating in Transparent Demo Fallback Mode**: {st.session_state.last_fallback_reason or 'GEMINI_API_KEY not configured.'} "
            "Responses, extraction, and sentiment are computed locally without faking Gemini API calls."
        )

    left_col, right_col = st.columns([1.45, 1.0], gap="large")

    with left_col:
        # Play latest TTS response if available
        if st.session_state.latest_audio_b64:
            audio_raw = base64.b64decode(st.session_state.latest_audio_b64)
            st.audio(audio_raw, format="audio/mpeg", autoplay=True)

        # Conversation Transcript
        st.markdown("#### Conversation Transcript")
        chat_box = st.container(height=360)
        with chat_box:
            for msg in st.session_state.chat_transcript:
                with st.chat_message(msg["role"]):
                    st.markdown(msg["content"])
                    if msg["role"] == "user" and msg.get("sentiment"):
                        s = msg["sentiment"]
                        st.caption(
                            f"Sentiment: **{s['sentiment']}** | Engagement: **{s['engagement']}** | "
                            f"Intent: **{s['purchase_intent']}** | Urgency: **{s['urgency']}**"
                        )
                    if msg["role"] == "assistant" and msg.get("rag_sources"):
                        srcs = ", ".join({r["source"] for r in msg["rag_sources"]})
                        st.caption(f"Grounded Knowledge Sources: `{srcs}`")

        # Voice Recording Input (Native Streamlit Microphone Widget)
        st.markdown("#### Voice Input (Browser Microphone → Faster-Whisper)")
        mic_key = f"mic_{st.session_state.active_session_id}_{st.session_state.mic_counter}"
        recorded_audio = st.audio_input("Record your voice message", key=mic_key)
        if recorded_audio is not None:
            raw_bytes = recorded_audio.getvalue()
            audio_hash = hash(raw_bytes)
            if audio_hash not in st.session_state.processed_audio_hashes:
                st.session_state.processed_audio_hashes.add(audio_hash)
                with st.spinner("Transcribing audio with Faster-Whisper & generating agent response..."):
                    try:
                        resp = api_client.send_voice(
                            session_id=st.session_state.active_session_id,
                            audio_bytes=raw_bytes,
                            filename="mic_input.wav",
                            include_audio=include_audio,
                        )
                        transcript_text = resp["transcription"]["text"]
                        _handle_turn_response(resp, transcript_text)
                        st.session_state.mic_counter += 1
                        st.rerun()
                    except Exception as exc:
                        st.session_state.mic_counter += 1
                        st.error(f"Voice processing failed: {exc}. You can use text chat fallback below.")

        # Text Chat Fallback + Quick Test Prompts
        user_text = st.chat_input("Or type a customer message (Text Chat Fallback)...")
        if user_text:
            with st.spinner("SalesPilot AI is thinking & updating CRM..."):
                resp = api_client.send_chat(
                    session_id=st.session_state.active_session_id,
                    message=user_text,
                    include_audio=include_audio,
                )
                _handle_turn_response(resp, user_text)
                st.rerun()

        st.markdown("**Quick Demo Prompts (Click to simulate a multi-turn buyer):**")
        qp1, qp2, qp3 = st.columns(3)
        if qp1.button("1. Ask about AI Automation", use_container_width=True):
            r = api_client.send_chat(
                st.session_state.active_session_id,
                "Hi, I'm Ananya Rao, CTO at FinPulse Technologies in FinTech. What AI automation services and pricing plans do you offer?",
                include_audio=include_audio,
            )
            _handle_turn_response(r, "Hi, I'm Ananya Rao, CTO at FinPulse Technologies in FinTech. What AI automation services and pricing plans do you offer?")
            st.rerun()
        if qp2.button("2. Share Budget & Timeline", use_container_width=True):
            msg = "We want to automate customer onboarding with RAG agents. Our budget is $6,500/month and we want to launch next month. My email is ananya@finpulse.io."
            r = api_client.send_chat(st.session_state.active_session_id, msg, include_audio=include_audio)
            _handle_turn_response(r, msg)
            st.rerun()
        if qp3.button("3. Confirm Demo Slot", use_container_width=True):
            msg = "Yes, please confirm and book a technical demo for tomorrow at 11:30 AM."
            r = api_client.send_chat(st.session_state.active_session_id, msg, include_audio=include_audio)
            _handle_turn_response(r, msg)
            st.rerun()

    with right_col:
        qual = st.session_state.latest_qualification
        _render_score_gauge(qual.get("lead_score", 0), qual.get("lead_category", "Cold"))
        st.markdown(
            f"{category_pill(qual.get('lead_category', 'Cold'))} &nbsp; "
            f"<small>{qual.get('score_reasoning', '')}</small>",
            unsafe_allow_html=True,
        )

        st.markdown("#### Extracted CRM Customer Profile")
        prof = st.session_state.latest_profile
        fields = [
            ("Name", prof.get("name")),
            ("Email", prof.get("email")),
            ("Phone", prof.get("phone")),
            ("Company", prof.get("company_name")),
            ("Industry", prof.get("industry")),
            ("Service", prof.get("interested_service")),
            ("Budget", prof.get("budget")),
            ("Timeline", prof.get("purchase_timeline")),
            ("Authority", prof.get("decision_authority")),
            ("Status", prof.get("status")),
        ]
        rows_html = "".join(
            f"<tr><td style='color:#64748B;padding:3px 8px;font-size:0.82rem;'>{lbl}</td>"
            f"<td style='font-weight:600;padding:3px 8px;font-size:0.82rem;'>{val or '<span style=\"color:#94A3B8;font-weight:400;\">Unknown</span>'}</td></tr>"
            for lbl, val in fields
        )
        st.markdown(f"<div class='sp-card'><table style='width:100%;'>{rows_html}</table></div>", unsafe_allow_html=True)

        if st.session_state.sentiment_history:
            st.markdown("#### Sentiment Trajectory")
            sent_map = {"Negative": -1, "Neutral": 0, "Positive": 1}
            y_vals = [sent_map.get(s["sentiment"], 0) for s in st.session_state.sentiment_history]
            fig = go.Figure(
                go.Scatter(
                    x=list(range(1, len(y_vals) + 1)),
                    y=y_vals,
                    mode="lines+markers",
                    line=dict(color="#2563EB", width=3),
                    marker=dict(size=9),
                )
            )
            fig.update_yaxes(tickvals=[-1, 0, 1], ticktext=["Negative", "Neutral", "Positive"], range=[-1.3, 1.3], color="#0F172A")
            fig.update_xaxes(title="Turn", dtick=1, color="#0F172A")
            fig.update_layout(
                height=165,
                margin=dict(l=10, r=10, t=10, b=25),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="#FFFFFF",
                font=dict(color="#0F172A"),
            )
            st.plotly_chart(fig, use_container_width=True)

        with st.expander("Agent Tool Execution & RAG Citations", expanded=False):
            if st.session_state.latest_tool_events:
                st.json(st.session_state.latest_tool_events)
            else:
                st.caption("No tool invocations yet in this session.")

    if st.session_state.latest_summary:
        st.markdown("### Generated Post-Call CRM Summary")
        sm = st.session_state.latest_summary
        st.success(
            f"**Summary:** {sm['summary_text']}\n\n"
            f"- **Requirements:** {sm['customer_requirements']}\n"
            f"- **Services Discussed:** {sm['services_discussed']}\n"
            f"- **Objections:** {sm['customer_objections']}\n"
            f"- **Qualification:** {sm['lead_qualification']} | **Sentiment:** {sm['overall_sentiment']}\n"
            f"- **Appointment:** {sm['appointment_status']}\n"
            f"- **Recommended Next Action:** {sm['recommended_next_action']}"
        )
