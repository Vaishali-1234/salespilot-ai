"""Unit tests for Lead Qualification, Sentiment Analysis, RAG, CRM, Appointments, Memory, and Summarizer."""

from datetime import datetime, timedelta

from ai_engine.agent import sales_agent
from ai_engine.lead_qualification import qualify_lead_profile
from ai_engine.memory import build_session_context, extract_customer_details
from ai_engine.sentiment import analyse_customer_sentiment
from ai_engine.summarizer import generate_and_save_call_summary
from crm.operations import (
    add_message,
    book_appointment_record,
    cancel_appointment,
    create_lead,
    create_session,
    get_available_slots,
    search_leads,
    update_lead,
)
from rag.retriever import KnowledgeRetriever


def test_lead_qualification_hot_warm_cold():
    hot = qualify_lead_profile(
        {
            "interested_service": "AI Automation & Autonomous Agents",
            "business_requirement": "Automate customer onboarding and CRM sync",
            "budget": "$6,500/month",
            "purchase_timeline": "Within 1 month",
            "decision_authority": "Decision Maker",
            "email": "cto@acme.io",
        },
        purchase_intent="High",
        urgency="High",
        sentiment="Positive",
    )
    assert hot["lead_category"] == "Hot"
    assert hot["lead_score"] >= 70
    assert "Hot" in hot["score_reasoning"]

    warm = qualify_lead_profile(
        {
            "interested_service": "Cloud Services & DevOps",
            "business_requirement": "Migrate legacy workloads to AWS",
            "budget": "$2,500/month",
            "purchase_timeline": "3-6 months",
        },
        purchase_intent="Medium",
        urgency="Low",
        sentiment="Neutral",
    )
    assert warm["lead_category"] == "Warm"
    assert 40 <= warm["lead_score"] < 70

    cold = qualify_lead_profile({}, purchase_intent="Low", urgency="Low", sentiment="Neutral")
    assert cold["lead_category"] == "Cold"
    assert cold["lead_score"] < 40


def test_extraction_never_invents_missing_fields():
    res = extract_customer_details("Hi, I just want to know what services you offer.")
    ext = res["extracted"]
    assert ext["name"] is None
    assert ext["email"] is None
    assert ext["phone"] is None
    assert ext["budget"] is None


def test_sentiment_analysis_and_objections():
    pos = analyse_customer_sentiment(
        "This sounds awesome! We definitely want to schedule a demo ASAP for next week."
    )
    assert pos["sentiment"] == "Positive"
    assert pos["purchase_intent"] == "High"
    assert pos["urgency"] == "High"

    neg = analyse_customer_sentiment(
        "This is too expensive and I am worried about GDPR data privacy and security."
    )
    assert neg["sentiment"] == "Negative"
    assert any("Pricing" in o for o in neg["objections"])
    assert any("Privacy" in o or "Security" in o for o in neg["objections"])


def test_rag_retrieval_and_anti_hallucination(tmp_path):
    retriever = KnowledgeRetriever(index_dir=tmp_path / "faiss_idx")
    build_info = retriever.ensure_ready(force_rebuild=True)
    assert build_info["chunks"] > 0

    hit = retriever.retrieve_company_information("What are TechNova pricing plans?")
    assert hit["found"] is True
    assert len(hit["results"]) >= 1
    assert any("pricing" in src for src in hit["sources"])

    miss = retriever.retrieve_company_information("zxqpwv completely unrelated quantum banana recipe", min_score=0.55)
    assert miss["found"] is False
    assert miss["results"] == []


def test_crm_crud_and_session_isolation(db_session):
    lead1 = create_lead(db_session, name="Aarav Mehta", company_name="FinPulse", interested_service="AI Automation")
    update_lead(db_session, lead1.id, {"lead_score": 82, "lead_category": "Hot", "status": "Qualified"})

    found = search_leads(db_session, query="FinPulse", category="Hot")
    assert len(found) == 1
    assert found[0].name == "Aarav Mehta"

    s1 = create_session(db_session, lead_id=lead1.id)
    lead2 = create_lead(db_session, name="Maya Lin", company_name="MediCore")
    s2 = create_session(db_session, lead_id=lead2.id)

    add_message(db_session, s1.id, "user", "Our budget is $15,000 per month at FinPulse.")
    add_message(db_session, s2.id, "user", "We need HIPAA healthcare analytics at MediCore.")

    ctx1 = build_session_context(db_session, s1.id)
    ctx2 = build_session_context(db_session, s2.id)

    assert "FinPulse" in ctx1["formatted_history"]
    assert "MediCore" not in ctx1["formatted_history"]
    assert "MediCore" in ctx2["formatted_history"]
    assert "FinPulse" not in ctx2["formatted_history"]


def test_appointment_booking_and_double_booking_prevention(db_session):
    lead1 = create_lead(db_session, name="Rohan Verma", email="rohan@example.com")
    lead2 = create_lead(db_session, name="Priya Nair", email="priya@example.com")
    date_str = (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d")

    # Unconfirmed booking must be rejected
    unconfirmed = book_appointment_record(
        db_session,
        lead_id=lead1.id,
        customer_name="Rohan Verma",
        customer_email="rohan@example.com",
        appointment_date=date_str,
        appointment_time="10:00 AM",
        confirmed_by_customer=False,
    )
    assert unconfirmed["success"] is False

    # Confirmed booking succeeds
    ok = book_appointment_record(
        db_session,
        lead_id=lead1.id,
        customer_name="Rohan Verma",
        customer_email="rohan@example.com",
        appointment_date=date_str,
        appointment_time="10:00 AM",
        confirmed_by_customer=True,
    )
    assert ok["success"] is True

    # Double booking same date & time must fail
    dup = book_appointment_record(
        db_session,
        lead_id=lead2.id,
        customer_name="Priya Nair",
        customer_email="priya@example.com",
        appointment_date=date_str,
        appointment_time="10:00 AM",
        confirmed_by_customer=True,
    )
    assert dup["success"] is False
    assert "already booked" in dup["error"].lower()

    # Cancelling frees the slot
    cancel_appointment(db_session, ok["appointment"]["id"])
    avail = get_available_slots(db_session, target_date=date_str)
    assert "10:00 AM" in avail["available_slots"]


def test_call_summarisation(db_session):
    lead = create_lead(
        db_session,
        name="Vikram Seth",
        company_name="LogiChain",
        interested_service="AI Automation & Autonomous Agents",
        lead_score=78,
        lead_category="Hot",
        overall_sentiment="Positive",
    )
    sess = create_session(db_session, lead_id=lead.id)
    add_message(db_session, sess.id, "user", "We want AI automation for logistics.", sentiment="Positive")
    add_message(db_session, sess.id, "assistant", "We offer Growth Plan at $6,500/month.")

    summary = generate_and_save_call_summary(db_session, sess.id)
    assert "Vikram Seth" in summary["summary_text"]
    assert summary["lead_qualification"] == "Hot (78/100)"
