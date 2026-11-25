"""Page 6: Call History & Post-Call Summaries."""

import streamlit as st

from frontend.api_client import api_client
from frontend.styles import category_pill, render_hero


def render_call_history_page() -> None:
    render_hero(
        "Call History & Executive Summaries",
        "Review recorded voice/chat call sessions, turn-level sentiment telemetry, and CRM summaries.",
    )

    sessions = api_client.list_sessions().get("sessions", [])
    summaries = {s["session_id"]: s for s in api_client.list_summaries().get("summaries", [])}

    if not sessions:
        st.info("No call sessions recorded yet. Start a conversation on the Live AI Sales Agent page.")
        return

    for sess in sessions:
        sid = sess["id"]
        lead_lbl = sess.get("lead_name") or "Unknown Prospect"
        comp_lbl = sess.get("lead_company") or "Unknown Company"
        cat = sess.get("lead_category", "Cold")
        score = sess.get("lead_score", 0)
        summary = summaries.get(sid)

        header = (
            f"Session `{sid}` • {lead_lbl} ({comp_lbl}) • {cat} ({score}/100) • "
            f"{sess['message_count']} msgs • Status: `{sess['status']}`"
        )
        with st.expander(header):
            st.markdown(
                f"{category_pill(cat)} &nbsp; **Mode:** `{sess['mode']}` &nbsp; **AI Engine:** `{sess['ai_mode']}`",
                unsafe_allow_html=True,
            )
            if summary:
                st.success(
                    f"**Call Summary:** {summary['summary_text']}\n\n"
                    f"- **Requirements:** {summary['customer_requirements']}\n"
                    f"- **Services Discussed:** {summary['services_discussed']}\n"
                    f"- **Objections:** {summary['customer_objections']}\n"
                    f"- **Appointment:** {summary['appointment_status']}\n"
                    f"- **Next Action:** {summary['recommended_next_action']}"
                )
            else:
                if st.button("Generate Call Summary Now", key=f"sum_{sid}"):
                    api_client.end_session(sid)
                    st.rerun()

            detail = api_client.get_session(sid)
            st.markdown("**Full Transcript**")
            for m in detail.get("messages", []):
                role_lbl = "Customer" if m["role"] == "user" else "SalesPilot AI"
                st.markdown(f"**{role_lbl}:** {m['content']}")
                if m["role"] == "user":
                    st.caption(
                        f"Sentiment: {m['sentiment']} | Engagement: {m['engagement']} | "
                        f"Intent: {m['purchase_intent']} | Urgency: {m['urgency']}"
                    )
