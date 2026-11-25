"""FastAPI REST API routes for Voice Agent, CRM, RAG, Appointments, and Analytics."""

import base64
import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from ai_engine.agent import GREETING_MESSAGE, sales_agent
from ai_engine.llm import llm_client
from backend.config import settings
from backend.schemas.api_schemas import (
    AppointmentCreateRequest,
    ChatTurnRequest,
    KnowledgeAddRequest,
    KnowledgeQueryRequest,
    LeadUpdateRequest,
    RuntimeConfigRequest,
    SessionCreateRequest,
    TTSRequest,
)
from crm.database import get_db
from crm.operations import (
    add_message,
    book_appointment_record,
    cancel_appointment,
    create_session,
    delete_lead,
    get_analytics_metrics,
    get_available_slots,
    get_call_summary,
    get_lead,
    get_session,
    get_session_messages,
    list_appointments,
    list_call_summaries,
    list_sessions,
    search_leads,
    serialize_appointment,
    serialize_lead,
    serialize_message,
    serialize_session,
    serialize_summary,
    update_lead,
)
from rag.embeddings import embedding_engine
from rag.retriever import default_retriever
from voice.speech_to_text import stt_engine
from voice.text_to_speech import tts_engine

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["SalesPilot AI"])


def _maybe_synthesize_b64(text: str, include_audio: bool) -> Dict[str, Any]:
    if not include_audio:
        return {"audio_b64": None, "tts_mode": "disabled", "tts_error": None}
    res = tts_engine.synthesize_sync(text)
    if res["success"] and res["audio_bytes"]:
        return {
            "audio_b64": base64.b64encode(res["audio_bytes"]).decode("ascii"),
            "tts_mode": res["mode"],
            "tts_error": None,
        }
    return {
        "audio_b64": None,
        "tts_mode": res["mode"],
        "tts_error": res.get("error"),
    }


# ------------------------------------------------------------------
# Conversation Sessions & Voice/Text Agent
# ------------------------------------------------------------------
@router.post("/sessions")
async def start_session(payload: SessionCreateRequest, db: Session = Depends(get_db)):
    llm_stat = llm_client.get_status()
    session = create_session(
        db,
        lead_id=payload.lead_id,
        mode=payload.mode,
        ai_mode=llm_stat["active_mode"],
    )
    add_message(db=db, session_id=session.id, role="assistant", content=GREETING_MESSAGE)
    audio_info = _maybe_synthesize_b64(GREETING_MESSAGE, payload.include_audio)
    lead = get_lead(db, session.lead_id)
    return {
        "session": serialize_session(session),
        "lead": serialize_lead(lead) if lead else None,
        "greeting": GREETING_MESSAGE,
        "llm_status": llm_stat,
        **audio_info,
    }


@router.get("/sessions")
def get_sessions(db: Session = Depends(get_db)):
    sessions = list_sessions(db)
    items = []
    for s in sessions:
        lead = get_lead(db, s.lead_id)
        summary = get_call_summary(db, s.id)
        msgs = get_session_messages(db, s.id)
        items.append(
            {
                **serialize_session(s),
                "message_count": len(msgs),
                "lead_name": lead.name if lead else None,
                "lead_company": lead.company_name if lead else None,
                "lead_category": lead.lead_category if lead else "Cold",
                "lead_score": lead.lead_score if lead else 0,
                "has_summary": summary is not None,
            }
        )
    return {"sessions": items}


@router.get("/sessions/{session_id}")
def get_session_detail(session_id: str, db: Session = Depends(get_db)):
    session = get_session(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    lead = get_lead(db, session.lead_id)
    msgs = get_session_messages(db, session_id)
    summary = get_call_summary(db, session_id)
    return {
        "session": serialize_session(session),
        "lead": serialize_lead(lead) if lead else None,
        "messages": [serialize_message(m) for m in msgs],
        "summary": serialize_summary(summary) if summary else None,
    }


@router.post("/sessions/{session_id}/chat")
def chat_turn(session_id: str, payload: ChatTurnRequest, db: Session = Depends(get_db)):
    session = get_session(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    result = sales_agent.process_turn(db=db, session_id=session_id, user_message=payload.message)
    audio_info = _maybe_synthesize_b64(result["reply"], payload.include_audio)
    return {**result, **audio_info}


@router.post("/sessions/{session_id}/voice")
async def voice_turn(
    session_id: str,
    audio: UploadFile = File(...),
    include_audio: bool = Form(True),
    db: Session = Depends(get_db),
):
    session = get_session(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    raw_bytes = await audio.read()
    stt_res = stt_engine.transcribe_bytes(raw_bytes, filename=audio.filename or "recording.wav")
    if not stt_res["success"]:
        raise HTTPException(status_code=422, detail=stt_res["error"] or "Speech transcription failed")

    agent_res = sales_agent.process_turn(db=db, session_id=session_id, user_message=stt_res["text"])
    audio_info = _maybe_synthesize_b64(agent_res["reply"], include_audio)
    return {
        "transcription": stt_res,
        **agent_res,
        **audio_info,
    }


@router.post("/sessions/{session_id}/end")
def end_session(session_id: str, db: Session = Depends(get_db)):
    session = get_session(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    summary = sales_agent.generate_call_summary(db=db, session_id=session_id)
    return {"summary": summary}


@router.post("/tts")
def synthesize_tts(payload: TTSRequest):
    res = tts_engine.synthesize_sync(payload.text, voice=payload.voice)
    if not res["success"]:
        return {"success": False, "mode": res["mode"], "audio_b64": None, "error": res["error"]}
    return {
        "success": True,
        "mode": res["mode"],
        "audio_b64": base64.b64encode(res["audio_bytes"]).decode("ascii"),
        "mime_type": res["mime_type"],
        "voice": res["voice"],
    }


# ------------------------------------------------------------------
# CRM Lead Management
# ------------------------------------------------------------------
@router.get("/leads")
def get_leads(
    q: Optional[str] = Query(default=None),
    category: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
):
    leads = search_leads(db, query=q, category=category, status=status)
    return {"leads": [serialize_lead(l) for l in leads]}


@router.get("/leads/{lead_id}")
def get_lead_detail(lead_id: int, db: Session = Depends(get_db)):
    lead = get_lead(db, lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    return {
        "lead": serialize_lead(lead),
        "sessions": [serialize_session(s) for s in lead.sessions],
        "appointments": [serialize_appointment(a) for a in lead.appointments],
    }


@router.patch("/leads/{lead_id}")
def patch_lead(lead_id: int, payload: LeadUpdateRequest, db: Session = Depends(get_db)):
    updates = {k: v for k, v in payload.model_dump().items() if v is not None}
    lead = update_lead(db, lead_id=lead_id, updates=updates)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    return {"lead": serialize_lead(lead)}


@router.delete("/leads/{lead_id}")
def remove_lead(lead_id: int, db: Session = Depends(get_db)):
    if not delete_lead(db, lead_id):
        raise HTTPException(status_code=404, detail="Lead not found")
    return {"deleted": True, "lead_id": lead_id}


# ------------------------------------------------------------------
# Appointment Management
# ------------------------------------------------------------------
@router.get("/appointments")
def get_all_appointments(status: Optional[str] = Query(default=None), db: Session = Depends(get_db)):
    appts = list_appointments(db, status=status)
    return {"appointments": [serialize_appointment(a) for a in appts]}


@router.get("/appointments/availability")
def check_availability(date: Optional[str] = Query(default=None), db: Session = Depends(get_db)):
    return get_available_slots(db, target_date=date)


@router.post("/appointments")
def create_appointment(payload: AppointmentCreateRequest, db: Session = Depends(get_db)):
    if not get_lead(db, payload.lead_id):
        raise HTTPException(status_code=404, detail="Lead not found")
    res = book_appointment_record(
        db=db,
        lead_id=payload.lead_id,
        session_id=payload.session_id,
        customer_name=payload.customer_name,
        customer_email=payload.customer_email,
        appointment_date=payload.appointment_date,
        appointment_time=payload.appointment_time,
        topic=payload.topic,
        confirmed_by_customer=payload.confirmed_by_customer,
    )
    if not res["success"]:
        raise HTTPException(status_code=409, detail=res["error"])
    return res


@router.post("/appointments/{appointment_id}/cancel")
def cancel_appt(appointment_id: int, db: Session = Depends(get_db)):
    appt = cancel_appointment(db, appointment_id)
    if not appt:
        raise HTTPException(status_code=404, detail="Appointment not found")
    return {"appointment": serialize_appointment(appt)}


# ------------------------------------------------------------------
# Knowledge Base (RAG)
# ------------------------------------------------------------------
@router.get("/knowledge")
def get_knowledge_base():
    docs = default_retriever.list_documents()
    return {
        "documents": docs,
        "total_chunks": len(default_retriever.store.chunks),
        "embedding_mode": embedding_engine.mode,
    }


@router.post("/knowledge")
def add_knowledge_document(payload: KnowledgeAddRequest):
    return default_retriever.add_document(payload.filename, payload.content)


@router.post("/knowledge/query")
def query_knowledge_base(payload: KnowledgeQueryRequest):
    return default_retriever.retrieve_company_information(payload.query, top_k=payload.top_k)


# ------------------------------------------------------------------
# Analytics, Summaries & Runtime Settings
# ------------------------------------------------------------------
@router.get("/analytics")
def get_analytics(db: Session = Depends(get_db)):
    return get_analytics_metrics(db)


@router.get("/calls/summaries")
def get_summaries(db: Session = Depends(get_db)):
    summaries = list_call_summaries(db)
    return {"summaries": [serialize_summary(s) for s in summaries]}


@router.post("/settings/config")
def update_runtime_config(payload: RuntimeConfigRequest):
    if payload.gemini_api_key is not None:
        llm_client.set_runtime_api_key(payload.gemini_api_key)
    if payload.edge_tts_voice:
        tts_engine.voice = payload.edge_tts_voice
    return {
        "llm_status": llm_client.get_status(),
        "edge_tts_voice": tts_engine.voice,
    }
