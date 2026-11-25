"""SQLAlchemy ORM models for CRM Leads, Call Sessions, Messages, Appointments, and Summaries."""

from datetime import datetime, timezone
from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from crm.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Lead(Base):
    """Customer & lead qualification record persisted in SQLite CRM."""

    __tablename__ = "leads"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(120), nullable=True)
    email = Column(String(160), nullable=True, index=True)
    phone = Column(String(50), nullable=True)
    company_name = Column(String(160), nullable=True)
    industry = Column(String(120), nullable=True)
    interested_service = Column(String(160), nullable=True)
    budget = Column(String(120), nullable=True)
    business_requirement = Column(Text, nullable=True)
    purchase_timeline = Column(String(120), nullable=True)
    decision_authority = Column(String(120), nullable=True)

    lead_score = Column(Integer, default=0)
    lead_category = Column(String(32), default="Cold")  # Hot | Warm | Cold
    score_reasoning = Column(Text, default="")
    status = Column(String(40), default="New")  # New | Qualified | Demo Scheduled | Closed Won | Lost
    overall_sentiment = Column(String(32), default="Neutral")

    created_at = Column(DateTime(timezone=True), default=utc_now)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    sessions = relationship("CallSession", back_populates="lead", cascade="all, delete-orphan")
    appointments = relationship("Appointment", back_populates="lead", cascade="all, delete-orphan")


class CallSession(Base):
    """Isolated voice/chat conversation session linked to a single Lead."""

    __tablename__ = "call_sessions"

    id = Column(String(64), primary_key=True, index=True)
    lead_id = Column(Integer, ForeignKey("leads.id"), nullable=False)
    status = Column(String(32), default="active")  # active | completed
    mode = Column(String(32), default="voice")  # voice | text
    ai_mode = Column(String(64), default="demo")  # gemini | openai | demo_fallback
    started_at = Column(DateTime(timezone=True), default=utc_now)
    ended_at = Column(DateTime(timezone=True), nullable=True)

    lead = relationship("Lead", back_populates="sessions")
    messages = relationship(
        "Message",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="Message.id",
    )
    summary = relationship(
        "CallSummary",
        back_populates="session",
        uselist=False,
        cascade="all, delete-orphan",
    )


class Message(Base):
    """Turn-level conversation transcript, sentiment telemetry, and RAG citations."""

    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(64), ForeignKey("call_sessions.id"), nullable=False, index=True)
    role = Column(String(24), nullable=False)  # user | assistant | system
    content = Column(Text, nullable=False)
    sentiment = Column(String(32), default="Neutral")
    engagement = Column(String(32), default="Medium")
    purchase_intent = Column(String(32), default="Low")
    urgency = Column(String(32), default="Low")
    objections = Column(Text, default="[]")
    rag_sources = Column(Text, default="[]")
    tool_events = Column(Text, default="[]")
    latency_ms = Column(Float, default=0.0)
    created_at = Column(DateTime(timezone=True), default=utc_now)

    session = relationship("CallSession", back_populates="messages")


class Appointment(Base):
    """Confirmed or cancelled consultation appointments with double-booking prevention."""

    __tablename__ = "appointments"

    id = Column(Integer, primary_key=True, index=True)
    lead_id = Column(Integer, ForeignKey("leads.id"), nullable=False)
    session_id = Column(String(64), nullable=True)
    customer_name = Column(String(120), nullable=False)
    customer_email = Column(String(160), nullable=False)
    appointment_date = Column(String(20), nullable=False, index=True)  # YYYY-MM-DD
    appointment_time = Column(String(20), nullable=False, index=True)  # e.g., 11:30 AM
    topic = Column(String(240), default="TechNova Solutions Technical Discovery Demo")
    status = Column(String(32), default="Confirmed")  # Confirmed | Cancelled
    confirmed_by_customer = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)

    lead = relationship("Lead", back_populates="appointments")


class CallSummary(Base):
    """Structured post-call summary saved directly to the CRM."""

    __tablename__ = "call_summaries"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(64), ForeignKey("call_sessions.id"), unique=True, nullable=False)
    lead_id = Column(Integer, ForeignKey("leads.id"), nullable=False)
    summary_text = Column(Text, nullable=False)
    customer_requirements = Column(Text, default="")
    services_discussed = Column(Text, default="")
    customer_objections = Column(Text, default="")
    overall_sentiment = Column(String(32), default="Neutral")
    lead_qualification = Column(String(64), default="Cold (0/100)")
    recommended_next_action = Column(Text, default="")
    appointment_status = Column(String(64), default="Not Booked")
    created_at = Column(DateTime(timezone=True), default=utc_now)

    session = relationship("CallSession", back_populates="summary")
