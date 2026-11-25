"""Page 7: Business Intelligence Analytics Dashboard (Plotly + SQLite)."""

import pandas as pd
import plotly.express as px
import streamlit as st

from frontend.api_client import api_client
from frontend.styles import render_hero, render_kpi_card


def render_analytics_page() -> None:
    render_hero(
        "Business Intelligence & Sales Analytics",
        "All KPIs and Plotly visualizations are computed live from SQLite CRM, Call, Sentiment, and Appointment records.",
    )

    metrics = api_client.get_analytics()

    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        render_kpi_card("Total Calls", str(metrics.get("total_calls", 0)))
    with c2:
        render_kpi_card("Total Leads", str(metrics.get("total_leads", 0)))
    with c3:
        render_kpi_card("Booked Demos", str(metrics.get("appointments_booked", 0)))
    with c4:
        render_kpi_card("Conversion Rate", f"{metrics.get('lead_conversion_rate', 0.0)}%")
    with c5:
        render_kpi_card("Avg Lead Score", f"{metrics.get('average_lead_score', 0.0)}/100")

    r1c1, r1c2 = st.columns(2)
    with r1c1:
        st.markdown("#### Lead Qualification Distribution (Hot / Warm / Cold)")
        dist = metrics.get("lead_distribution", {})
        df_dist = pd.DataFrame({"Category": list(dist.keys()), "Count": list(dist.values())})
        fig = px.pie(
            df_dist,
            names="Category",
            values="Count",
            hole=0.45,
            color="Category",
            color_discrete_map={"Hot": "#DC2626", "Warm": "#F97316", "Cold": "#0284C7"},
        )
        fig.update_layout(height=320, margin=dict(l=10, r=10, t=10, b=10))
        st.plotly_chart(fig, use_container_width=True)

    with r1c2:
        st.markdown("#### Customer Sentiment Distribution")
        sdist = metrics.get("sentiment_distribution", {})
        df_sent = pd.DataFrame({"Sentiment": list(sdist.keys()), "Count": list(sdist.values())})
        fig2 = px.bar(
            df_sent,
            x="Sentiment",
            y="Count",
            color="Sentiment",
            color_discrete_map={"Positive": "#16A34A", "Neutral": "#64748B", "Negative": "#DC2626"},
        )
        fig2.update_layout(height=320, margin=dict(l=10, r=10, t=10, b=10), showlegend=False)
        st.plotly_chart(fig2, use_container_width=True)

    r2c1, r2c2 = st.columns(2)
    with r2c1:
        st.markdown("#### Most Requested TechNova Services")
        svc = metrics.get("service_demand", {})
        if svc:
            df_svc = pd.DataFrame({"Service": list(svc.keys()), "Leads": list(svc.values())})
            fig3 = px.bar(df_svc, x="Leads", y="Service", orientation="h", color_discrete_sequence=["#2563EB"])
            fig3.update_layout(height=320, margin=dict(l=10, r=10, t=10, b=10))
            st.plotly_chart(fig3, use_container_width=True)
        else:
            st.caption("No service demand records yet.")

    with r2c2:
        st.markdown("#### Daily & Weekly Call Activity")
        tab_d, tab_w = st.tabs(["Daily Activity", "Weekly Activity"])
        with tab_d:
            daily = metrics.get("daily_call_activity", [])
            if daily:
                fig4 = px.line(pd.DataFrame(daily), x="date", y="calls", markers=True, color_discrete_sequence=["#1D4ED8"])
                fig4.update_layout(height=280, margin=dict(l=10, r=10, t=10, b=10))
                st.plotly_chart(fig4, use_container_width=True)
            else:
                st.caption("No call sessions recorded yet.")
        with tab_w:
            weekly = metrics.get("weekly_call_activity", [])
            if weekly:
                fig5 = px.bar(pd.DataFrame(weekly), x="week", y="calls", color_discrete_sequence=["#0F172A"])
                fig5.update_layout(height=280, margin=dict(l=10, r=10, t=10, b=10))
                st.plotly_chart(fig5, use_container_width=True)
            else:
                st.caption("No weekly call activity yet.")
