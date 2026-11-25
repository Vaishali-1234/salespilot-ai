"""CRUD operations for Leads, Call Sessions, Messages, Appointments, and Call Summaries."""

from datetime import datetime, timedelta, timezone
import json
from typing import Any, Dict, List, Optional
import uuid

from sqlalchemy import func
from sqlalchemy.orm import Session

from crm.database import Base, engine
from crm.models import Appointment, CallSession, CallSummary, Lead, Message


AVAILABLE_TIME_SLOTS = ["10:00 AM", "11:30 AM", "02:00 PM", "03:30 PM", "05:00 PM"]


def init_db() -> None:
    """Create all SQLite tables if they do not exist."""
    Base.metadata.create_all(bind=engine)


def create_lead(db: Session, **fields: Any) -> Lead:
    lead = Lead(**{k: v for k, v in fields.items() if hasattr(Lead, k)})
    db.add(lead)
    db.commit()
    db.refresh(lead)
    return lead


def get_lead(db: Session, lead_id: int) -> Optional[Lead]:
    return db.query(Lead).filter(Lead.id == lead_id).first()


def search_leads(
    db: Session,
    query: Optional[str] = None,
    category: Optional[str] = None,
    status: Optional[str] = None,
) -> List[Lead]:
    q = db.query(Lead)
    if category and category != "All":
        q = q.filter(Lead.lead_category == category)
    if status and status != "All":
        q = q.filter(Lead.status == status)
    if query:
        like_term = f"%{query.strip()}%"
        q = q.filter(
            (Lead.name.ilike(like_term))
            | (Lead.email.ilike(like_term))
            | (Lead.company_name.ilike(like_term))
            | (Lead.interested_service.ilike(like_term))
            | (Lead.industry.ilike(like_term))
        )
    return q.order_by(Lead.updated_at.desc(), Lead.id.desc()).all()


def update_lead(db: Session, lead_id: int, updates: Dict[str, Any]) -> Optional[Lead]:
    lead = get_lead(db, lead_id)
    if not lead:
        return None
    for key, val in updates.items():
        if hasattr(lead, key) and val is not None and val != "" and str(val).lower() != "unknown":
            setattr(lead, key, val)
    lead.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(lead)
    return lead


def delete_lead(db: Session, lead_id: int) -> bool:
    lead = get_lead(db, lead_id)
    if not lead:
        return False
    db.delete(lead)
    db.commit()
    return True


def create_session(
    db: Session,
    lead_id: Optional[int] = None,
    mode: str = "voice",
    ai_mode: str = "demo_fallback",
) -> CallSession:
    """Create a new isolated call session and associated Lead record if omitted."""
    if lead_id is None:
        lead = create_lead(db, status="New")
        lead_id = lead.id
    session_id = f"sp-{uuid.uuid4().hex[:10]}"
    session = CallSession(
        id=session_id,
        lead_id=lead_id,
        status="active",
        mode=mode,
        ai_mode=ai_mode,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def get_session(db: Session, session_id: str) -> Optional[CallSession]:
    return db.query(CallSession).filter(CallSession.id == session_id).first()


def list_sessions(db: Session) -> List[CallSession]:
    return db.query(CallSession).order_by(CallSession.started_at.desc()).all()


def add_message(
    db: Session,
    session_id: str,
    role: str,
    content: str,
    sentiment: str = "Neutral",
    engagement: str = "Medium",
    purchase_intent: str = "Low",
    urgency: str = "Low",
    objections: Optional[List[str]] = None,
    rag_sources: Optional[List[Dict[str, Any]]] = None,
    tool_events: Optional[List[Dict[str, Any]]] = None,
    latency_ms: float = 0.0,
) -> Message:
    msg = Message(
        session_id=session_id,
        role=role,
        content=content,
        sentiment=sentiment,
        engagement=engagement,
        purchase_intent=purchase_intent,
        urgency=urgency,
        objections=json.dumps(objections or [], ensure_ascii=False),
        rag_sources=json.dumps(rag_sources or [], ensure_ascii=False),
        tool_events=json.dumps(tool_events or [], ensure_ascii=False),
        latency_ms=latency_ms,
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return msg


def get_session_messages(db: Session, session_id: str) -> List[Message]:
    return (
        db.query(Message)
        .filter(Message.session_id == session_id)
        .order_by(Message.id.asc())
        .all()
    )


def get_available_slots(db: Session, target_date: Optional[str] = None) -> Dict[str, Any]:
    """Return available and booked consultation slots for a date (defaults to tomorrow)."""
    date_str = target_date or (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    booked_rows = (
        db.query(Appointment.appointment_time)
        .filter(Appointment.appointment_date == date_str, Appointment.status == "Confirmed")
        .all()
    )
    booked = {row[0] for row in booked_rows}
    available = [slot for slot in AVAILABLE_TIME_SLOTS if slot not in booked]
    return {
        "date": date_str,
        "available_slots": available,
        "booked_slots": sorted(booked),
    }


def book_appointment_record(
    db: Session,
    lead_id: int,
    customer_name: str,
    customer_email: str,
    appointment_date: str,
    appointment_time: str,
    topic: str = "TechNova Solutions Technical Discovery Demo",
    session_id: Optional[str] = None,
    confirmed_by_customer: bool = True,
) -> Dict[str, Any]:
    """Book an appointment after checking customer confirmation and double-booking rules."""
    if not confirmed_by_customer:
        return {
            "success": False,
            "error": "Customer confirmation is required before creating an appointment.",
        }
    if not customer_name or not customer_email or "@" not in customer_email:
        return {
            "success": False,
            "error": "Valid customer name and email are required to book an appointment.",
        }

    existing = (
        db.query(Appointment)
        .filter(
            Appointment.appointment_date == appointment_date,
            Appointment.appointment_time == appointment_time,
            Appointment.status == "Confirmed",
        )
        .first()
    )
    if existing:
        return {
            "success": False,
            "error": f"Slot {appointment_time} on {appointment_date} is already booked. Please pick another slot.",
        }

    appt = Appointment(
        lead_id=lead_id,
        session_id=session_id,
        customer_name=customer_name.strip(),
        customer_email=customer_email.strip(),
        appointment_date=appointment_date.strip(),
        appointment_time=appointment_time.strip(),
        topic=topic,
        status="Confirmed",
        confirmed_by_customer=True,
    )
    db.add(appt)

    lead = get_lead(db, lead_id)
    if lead:
        lead.name = lead.name or customer_name.strip()
        lead.email = lead.email or customer_email.strip()
        lead.status = "Demo Scheduled"
        lead.updated_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(appt)
    return {"success": True, "appointment": serialize_appointment(appt)}


def list_appointments(db: Session, status: Optional[str] = None) -> List[Appointment]:
    q = db.query(Appointment)
    if status and status != "All":
        q = q.filter(Appointment.status == status)
    return q.order_by(Appointment.appointment_date.asc(), Appointment.appointment_time.asc()).all()


def cancel_appointment(db: Session, appointment_id: int) -> Optional[Appointment]:
    appt = db.query(Appointment).filter(Appointment.id == appointment_id).first()
    if not appt:
        return None
    appt.status = "Cancelled"
    db.commit()
    db.refresh(appt)
    return appt


def save_call_summary(db: Session, session_id: str, lead_id: int, data: Dict[str, Any]) -> CallSummary:
    existing = db.query(CallSummary).filter(CallSummary.session_id == session_id).first()
    if existing:
        for k, v in data.items():
            if hasattr(existing, k):
                setattr(existing, k, v)
        db.commit()
        db.refresh(existing)
        return existing

    summary = CallSummary(session_id=session_id, lead_id=lead_id, **data)
    db.add(summary)
    session = get_session(db, session_id)
    if session:
        session.status = "completed"
        session.ended_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(summary)
    return summary


def get_analytics_metrics(db: Session) -> Dict[str, Any]:
    """Compute real-time business intelligence metrics directly from SQLite tables."""
    total_calls = db.query(func.count(CallSession.id)).scalar() or 0
    total_leads = db.query(func.count(Lead.id)).scalar() or 0
    booked_appts = (
        db.query(func.count(Appointment.id))
        .filter(Appointment.status == "Confirmed")
        .scalar()
        or 0
    )

    leads = db.query(Lead).all()
    category_counts = {"Hot": 0, "Warm": 0, "Cold": 0}
    sentiment_counts = {"Positive": 0, "Neutral": 0, "Negative": 0}
    service_counts: Dict[str, int] = {}

    for lead in leads:
        cat = lead.lead_category if lead.lead_category in category_counts else "Cold"
        category_counts[cat] += 1
        sent = lead.overall_sentiment if lead.overall_sentiment in sentiment_counts else "Neutral"
        sentiment_counts[sent] += 1
        svc = (lead.interested_service or "Unspecified").strip()
        service_counts[svc] = service_counts.get(svc, 0) + 1

    # Also compute turn-level sentiment counts from user messages
    user_msgs = db.query(Message).filter(Message.role == "user").all()
    turn_sentiment_counts = {"Positive": 0, "Neutral": 0, "Negative": 0}
    for m in user_msgs:
        s = m.sentiment if m.sentiment in turn_sentiment_counts else "Neutral"
        turn_sentiment_counts[s] += 1

    conversion_rate = round((booked_appts / total_leads) * 100, 1) if total_leads > 0 else 0.0

    # Daily and weekly call activity grouped by date / ISO week
    sessions = db.query(CallSession).all()
    daily_activity: Dict[str, int] = {}
    weekly_activity: Dict[str, int] = {}
    for sess in sessions:
        dt = sess.started_at or datetime.now(timezone.utc)
        dt_str = dt.strftime("%Y-%m-%d")
        wk_str = dt.strftime("%Y-W%W")
        daily_activity[dt_str] = daily_activity.get(dt_str, 0) + 1
        weekly_activity[wk_str] = weekly_activity.get(wk_str, 0) + 1

    avg_score = round(sum(l.lead_score for l in leads) / len(leads), 1) if leads else 0.0

    return {
        "total_calls": total_calls,
        "total_leads": total_leads,
        "appointments_booked": booked_appts,
        "lead_conversion_rate": conversion_rate,
        "average_lead_score": avg_score,
        "lead_distribution": category_counts,
        "sentiment_distribution": turn_sentiment_counts if user_msgs else sentiment_counts,
        "service_demand": service_counts,
        "daily_call_activity": [{"date": k, "calls": v} for k, v in sorted(daily_activity.items())],
        "weekly_call_activity": [{"week": k, "calls": v} for k, v in sorted(weekly_activity.items())],
    }


def list_call_summaries(db: Session) -> List[CallSummary]:
    return db.query(CallSummary).order_by(CallSummary.created_at.desc()).all()


def get_call_summary(db: Session, session_id: str) -> Optional[CallSummary]:
    return db.query(CallSummary).filter(CallSummary.session_id == session_id).first()


def serialize_session(sess: CallSession) -> Dict[str, Any]:
    return {
        "id": sess.id,
        "lead_id": sess.lead_id,
        "status": sess.status,
        "mode": sess.mode,
        "ai_mode": sess.ai_mode,
        "started_at": sess.started_at.isoformat() if sess.started_at else None,
        "ended_at": sess.ended_at.isoformat() if sess.ended_at else None,
    }


def serialize_message(msg: Message) -> Dict[str, Any]:
    return {
        "id": msg.id,
        "session_id": msg.session_id,
        "role": msg.role,
        "content": msg.content,
        "sentiment": msg.sentiment,
        "engagement": msg.engagement,
        "purchase_intent": msg.purchase_intent,
        "urgency": msg.urgency,
        "objections": json.loads(msg.objections or "[]"),
        "rag_sources": json.loads(msg.rag_sources or "[]"),
        "tool_events": json.loads(msg.tool_events or "[]"),
        "latency_ms": msg.latency_ms,
        "created_at": msg.created_at.isoformat() if msg.created_at else None,
    }


def serialize_lead(lead: Lead) -> Dict[str, Any]:
    return {
        "id": lead.id,
        "name": lead.name,
        "email": lead.email,
        "phone": lead.phone,
        "company_name": lead.company_name,
        "industry": lead.industry,
        "interested_service": lead.interested_service,
        "budget": lead.budget,
        "business_requirement": lead.business_requirement,
        "purchase_timeline": lead.purchase_timeline,
        "decision_authority": lead.decision_authority,
        "lead_score": lead.lead_score,
        "lead_category": lead.lead_category,
        "score_reasoning": lead.score_reasoning,
        "status": lead.status,
        "overall_sentiment": lead.overall_sentiment,
        "created_at": lead.created_at.isoformat() if lead.created_at else None,
        "updated_at": lead.updated_at.isoformat() if lead.updated_at else None,
    }


def serialize_appointment(appt: Appointment) -> Dict[str, Any]:
    return {
        "id": appt.id,
        "lead_id": appt.lead_id,
        "session_id": appt.session_id,
        "customer_name": appt.customer_name,
        "customer_email": appt.customer_email,
        "appointment_date": appt.appointment_date,
        "appointment_time": appt.appointment_time,
        "topic": appt.topic,
        "status": appt.status,
        "confirmed_by_customer": appt.confirmed_by_customer,
        "created_at": appt.created_at.isoformat() if appt.created_at else None,
    }


def serialize_summary(summary: CallSummary) -> Dict[str, Any]:
    return {
        "id": summary.id,
        "session_id": summary.session_id,
        "lead_id": summary.lead_id,
        "summary_text": summary.summary_text,
        "customer_requirements": summary.customer_requirements,
        "services_discussed": summary.services_discussed,
        "customer_objections": summary.customer_objections,
        "overall_sentiment": summary.overall_sentiment,
        "lead_qualification": summary.lead_qualification,
        "recommended_next_action": summary.recommended_next_action,
        "appointment_status": summary.appointment_status,
        "created_at": summary.created_at.isoformat() if summary.created_at else None,
    }
