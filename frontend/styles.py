"""Shared SaaS CSS styling (dark navy & white theme with subtle blue accents) and animated waveform."""

import streamlit as st


def inject_custom_css() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

        html, body, [class*="css"] {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
        }

        /* Main light canvas with dark navy sidebar */
        .stApp {
            background-color: #F8FAFC;
            color: #0F172A;
        }

        [data-testid="stSidebar"] {
            background: linear-gradient(180deg, #0A1124 0%, #0F172A 100%);
            border-right: 1px solid #1E293B;
        }
        [data-testid="stSidebar"] * {
            color: #E2E8F0 !important;
        }
        [data-testid="stSidebar"] .stRadio label:hover {
            color: #60A5FA !important;
        }

        /* Top Hero / Header Banner */
        .sp-hero {
            background: linear-gradient(135deg, #0B1224 0%, #162447 65%, #1D4ED8 100%);
            color: #FFFFFF;
            padding: 1.35rem 1.75rem;
            border-radius: 14px;
            margin-bottom: 1.25rem;
            box-shadow: 0 10px 25px -5px rgba(15, 23, 42, 0.22);
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 1rem;
        }
        .sp-hero h1 {
            margin: 0;
            font-size: 1.55rem;
            font-weight: 700;
            color: #FFFFFF;
            letter-spacing: -0.02em;
        }
        .sp-hero p {
            margin: 0.25rem 0 0 0;
            font-size: 0.92rem;
            color: #CBD5E1;
        }

        /* SaaS Metric Cards */
        .sp-card {
            background: #FFFFFF;
            border: 1px solid #E2E8F0;
            border-radius: 12px;
            padding: 1.1rem 1.25rem;
            box-shadow: 0 1px 3px rgba(15, 23, 42, 0.05);
            margin-bottom: 0.75rem;
        }
        .sp-kpi-label {
            font-size: 0.78rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: #64748B;
            margin-bottom: 0.35rem;
        }
        .sp-kpi-value {
            font-size: 1.85rem;
            font-weight: 700;
            color: #0F172A;
            line-height: 1.15;
        }
        .sp-kpi-sub {
            font-size: 0.8rem;
            color: #3B82F6;
            margin-top: 0.3rem;
            font-weight: 500;
        }

        /* Status Pills */
        .sp-pill {
            display: inline-block;
            padding: 0.25rem 0.7rem;
            border-radius: 999px;
            font-size: 0.76rem;
            font-weight: 600;
            letter-spacing: 0.02em;
        }
        .sp-pill-live { background: #DCFCE7; color: #166534; border: 1px solid #86EFAC; }
        .sp-pill-demo { background: #FEF3C7; color: #92400E; border: 1px solid #FDE68A; }
        .sp-pill-hot  { background: #FEE2E2; color: #991B1B; border: 1px solid #FCA5A5; }
        .sp-pill-warm { background: #FFEDD5; color: #9A3412; border: 1px solid #FDBA74; }
        .sp-pill-cold { background: #E0F2FE; color: #075985; border: 1px solid #7DD3FC; }
        .sp-pill-blue { background: #DBEAFE; color: #1E40AF; border: 1px solid #93C5FD; }

        /* Animated Voice Waveform */
        .sp-voice-stage {
            background: linear-gradient(135deg, #0B1224 0%, #13203E 100%);
            border: 1px solid #1E3A8A;
            border-radius: 14px;
            padding: 1.15rem 1.4rem;
            color: #FFFFFF;
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 1rem;
        }
        .sp-wave {
            display: flex;
            align-items: center;
            gap: 5px;
            height: 36px;
        }
        .sp-wave-bar {
            width: 5px;
            background: linear-gradient(180deg, #60A5FA, #2563EB);
            border-radius: 4px;
            animation: spWave 1.15s ease-in-out infinite;
        }
        .sp-wave-bar:nth-child(2) { animation-delay: 0.12s; }
        .sp-wave-bar:nth-child(3) { animation-delay: 0.24s; }
        .sp-wave-bar:nth-child(4) { animation-delay: 0.36s; }
        .sp-wave-bar:nth-child(5) { animation-delay: 0.48s; }
        .sp-wave-bar:nth-child(6) { animation-delay: 0.60s; }
        .sp-wave-bar:nth-child(7) { animation-delay: 0.72s; }
        .sp-wave-bar:nth-child(8) { animation-delay: 0.84s; }
        .sp-wave-idle .sp-wave-bar {
            animation: none;
            height: 8px !important;
            opacity: 0.45;
        }
        @keyframes spWave {
            0%, 100% { height: 8px; opacity: 0.55; }
            50% { height: 34px; opacity: 1.0; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_hero(title: str, subtitle: str, badge_html: str = "") -> None:
    st.markdown(
        f"""
        <div class="sp-hero">
            <div>
                <h1>{title}</h1>
                <p>{subtitle}</p>
            </div>
            <div>{badge_html}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_kpi_card(label: str, value: str, sub: str = "") -> None:
    sub_html = f'<div class="sp-kpi-sub">{sub}</div>' if sub else ""
    st.markdown(
        f"""
        <div class="sp-card">
            <div class="sp-kpi-label">{label}</div>
            <div class="sp-kpi-value">{value}</div>
            {sub_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def category_pill(category: str) -> str:
    cls = {
        "Hot": "sp-pill-hot",
        "Warm": "sp-pill-warm",
        "Cold": "sp-pill-cold",
    }.get(category, "sp-pill-blue")
    return f'<span class="sp-pill {cls}">{category}</span>'
