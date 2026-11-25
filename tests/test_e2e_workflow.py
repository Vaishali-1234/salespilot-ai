"""End-to-end workflow test covering the full 19-step sales journey through FastAPI endpoints."""

import asyncio
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.main import health_check
from backend.routes.api import (
    chat_turn,
    end_session,
    get_all_appointments,
    get_analytics,
    get_leads,
    start_session,
)
from backend.schemas.api_schemas import ChatTurnRequest, SessionCreateRequest
from crm.database import Base
from rag.retriever import default_retriever


def test_complete_end_to_end_sales_workflow(tmp_path):
    db_file = tmp_path / "e2e_salespilot.db"
    engine = create_engine(f"sqlite:///{db_file.as_posix()}", connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    default_retriever.ensure_ready(force_rebuild=False)

    db = TestingSessionLocal()
    try:
        # 0. Health check
        health = health_check()
        assert health["status"] == "ok"
        assert health["total_kb_chunks"] > 0

        # 1-2. Start session & receive TechNova greeting
        # Note: call coroutine directly via manual loop or sync wrapper without socketpair if needed
        coro = start_session(SessionCreateRequest(mode="text", include_audio=False), db=db)
        try:
            start_data = coro.send(None)
        except StopIteration as stop:
            start_data = stop.value

        session_id = start_data["session"]["id"]
        assert "TechNova Solutions" in start_data["greeting"]

        # 3-7. Ask about AI automation services -> triggers RAG & extraction
        d1 = chat_turn(
            session_id=session_id,
            payload=ChatTurnRequest(
                message="Hi, I'm Ananya Rao, CTO at FinPulse Technologies in FinTech. What AI automation services and pricing plans do you offer?",
                include_audio=False,
            ),
            db=db,
        )
        assert d1["lead_profile"]["name"] == "Ananya Rao"
        assert d1["lead_profile"]["industry"] == "FinTech"
        assert len(d1["rag_sources"]) >= 1

        # 8-11. Share budget, timeline, email -> qualifies lead as Hot
        d2 = chat_turn(
            session_id=session_id,
            payload=ChatTurnRequest(
                message="We need to automate customer onboarding with RAG agents. Our budget is $6,500/month, launch next month, email is ananya@finpulse.io.",
                include_audio=False,
            ),
            db=db,
        )
        assert d2["qualification"]["lead_category"] == "Hot"
        assert d2["qualification"]["lead_score"] >= 70
        assert d2["lead_profile"]["email"] == "ananya@finpulse.io"

        # 12-16. Express interest & confirm appointment slot
        tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        d3 = chat_turn(
            session_id=session_id,
            payload=ChatTurnRequest(
                message=f"Yes, please confirm and book a technical demo for {tomorrow} at 11:30 AM.",
                include_audio=False,
            ),
            db=db,
        )
        assert d3["appointment"] is not None
        assert d3["appointment"]["status"] == "Confirmed"
        assert d3["appointment"]["appointment_time"] == "11:30 AM"
        assert d3["lead_profile"]["status"] == "Demo Scheduled"

        # Verify CRM & Appointment records persisted
        leads = get_leads(q="FinPulse", category="Hot", status=None, db=db)["leads"]
        assert len(leads) == 1
        appts = get_all_appointments(status="Confirmed", db=db)["appointments"]
        assert len(appts) == 1

        # 17-18. End call & generate summary
        summary = end_session(session_id=session_id, db=db)["summary"]
        assert "Ananya Rao" in summary["summary_text"]
        assert "Confirmed" in summary["appointment_status"]

        # 19. Analytics dashboard reflects real DB records
        analytics = get_analytics(db=db)
        assert analytics["total_calls"] == 1
        assert analytics["total_leads"] == 1
        assert analytics["appointments_booked"] == 1
        assert analytics["lead_conversion_rate"] == 100.0
        assert analytics["lead_distribution"]["Hot"] == 1
    finally:
        db.close()
        engine.dispose()
