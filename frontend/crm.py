"""Page 3: CRM / Lead Management."""

import pandas as pd
import streamlit as st

from frontend.api_client import api_client
from frontend.styles import category_pill, render_hero


def render_crm_page() -> None:
    render_hero(
        "CRM & Lead Management",
        "Search, filter, inspect transcripts, and manage B2B sales pipeline leads in SQLite.",
    )

    f1, f2, f3 = st.columns([2, 1, 1])
    query = f1.text_input("Search leads by name, email, company, service, or industry", "")
    category = f2.selectbox("Lead Category", ["All", "Hot", "Warm", "Cold"])
    status_filter = f3.selectbox("Lead Status", ["All", "New", "Qualified", "Demo Scheduled", "Closed Won", "Lost"])

    leads = api_client.list_leads(query=query, category=category, status=status_filter).get("leads", [])
    if not leads:
        st.info("No matching leads found in CRM.")
        return

    df = pd.DataFrame(leads)[
        ["id", "name", "email", "company_name", "interested_service", "budget", "lead_score", "lead_category", "status", "overall_sentiment"]
    ]
    st.dataframe(df, use_container_width=True, hide_index=True)

    st.markdown("### Lead Inspector & Status Update")
    lead_options = {f"#{l['id']} — {l['name'] or 'Unnamed'} ({l['company_name'] or 'Unknown Co'}) [{l['lead_category']}]": l["id"] for l in leads}
    selected_label = st.selectbox("Select a lead to inspect", list(lead_options.keys()))
    selected_id = lead_options[selected_label]

    detail = api_client.get_lead_detail(selected_id)
    lead = detail["lead"]

    c_info, c_edit = st.columns([1.4, 1.0])
    with c_info:
        st.markdown(
            f"**Category:** {category_pill(lead['lead_category'])} &nbsp; **Score:** `{lead['lead_score']}/100` &nbsp; **Sentiment:** `{lead['overall_sentiment']}`",
            unsafe_allow_html=True,
        )
        st.caption(lead.get("score_reasoning") or "")
        st.json(
            {
                "name": lead.get("name"),
                "email": lead.get("email"),
                "phone": lead.get("phone"),
                "company_name": lead.get("company_name"),
                "industry": lead.get("industry"),
                "interested_service": lead.get("interested_service"),
                "budget": lead.get("budget"),
                "purchase_timeline": lead.get("purchase_timeline"),
                "decision_authority": lead.get("decision_authority"),
                "business_requirement": lead.get("business_requirement"),
            }
        )

    with c_edit:
        with st.form(f"edit_lead_{selected_id}"):
            new_status = st.selectbox(
                "Update Pipeline Status",
                ["New", "Qualified", "Demo Scheduled", "Closed Won", "Lost"],
                index=["New", "Qualified", "Demo Scheduled", "Closed Won", "Lost"].index(lead["status"])
                if lead["status"] in ["New", "Qualified", "Demo Scheduled", "Closed Won", "Lost"]
                else 0,
            )
            new_service = st.text_input("Interested Service", value=lead.get("interested_service") or "")
            new_budget = st.text_input("Budget", value=lead.get("budget") or "")
            submitted = st.form_submit_button("Save CRM Changes", type="primary")
            if submitted:
                api_client.update_lead(
                    selected_id,
                    {"status": new_status, "interested_service": new_service or None, "budget": new_budget or None},
                )
                st.success("Lead updated in SQLite CRM!")
                st.rerun()

        if detail["appointments"]:
            st.markdown("**Linked Appointments**")
            for a in detail["appointments"]:
                st.write(f"- {a['appointment_date']} {a['appointment_time']} — `{a['status']}`")

    if detail["sessions"]:
        st.markdown("#### Conversation History")
        for s in detail["sessions"]:
            sess_data = api_client.get_session(s["id"])
            with st.expander(f"Session `{s['id']}` ({s['status']}, mode: {s['ai_mode']})"):
                for m in sess_data["messages"]:
                    st.markdown(f"**{'Customer' if m['role']=='user' else 'SalesPilot AI'}:** {m['content']}")
