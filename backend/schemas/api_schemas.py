"""Pydantic schemas for FastAPI request and response validation."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class SessionCreateRequest(BaseModel):
    mode: str = Field(default="voice", pattern="^(voice|text)$")
    lead_id: Optional[int] = None
    include_audio: bool = True


class ChatTurnRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    include_audio: bool = True


class TTSRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=3000)
    voice: Optional[str] = None


class LeadUpdateRequest(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    company_name: Optional[str] = None
    industry: Optional[str] = None
    interested_service: Optional[str] = None
    budget: Optional[str] = None
    business_requirement: Optional[str] = None
    purchase_timeline: Optional[str] = None
    decision_authority: Optional[str] = None
    status: Optional[str] = None


class AppointmentCreateRequest(BaseModel):
    lead_id: int
    session_id: Optional[str] = None
    customer_name: str = Field(..., min_length=2, max_length=120)
    customer_email: str = Field(..., min_length=5, max_length=160)
    appointment_date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    appointment_time: str = Field(..., min_length=4, max_length=20)
    topic: str = Field(default="TechNova Solutions Technical Discovery Demo", max_length=240)
    confirmed_by_customer: bool = True


class KnowledgeAddRequest(BaseModel):
    filename: str = Field(..., min_length=3, max_length=100)
    content: str = Field(..., min_length=10)


class KnowledgeQueryRequest(BaseModel):
    query: str = Field(..., min_length=2, max_length=500)
    top_k: int = Field(default=4, ge=1, le=10)


class RuntimeConfigRequest(BaseModel):
    gemini_api_key: Optional[str] = None
    edge_tts_voice: Optional[str] = None


class HealthResponse(BaseModel):
    status: str
    app_name: str
    llm_status: Dict[str, Any]
    embedding_mode: str
    total_kb_chunks: int
    whisper_model: str
    edge_tts_voice: str
