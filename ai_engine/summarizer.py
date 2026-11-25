"""Post-call structured summarizer persisted directly to the SQLite CRM."""

import json
from typing import Any, Dict, List

from sqlalchemy.orm import Session

from ai_engine.llm import llm_client
from crm.models import Appointment
from crm.operations import (
    get_lead,
    get_session,
    get_session_messages,
    save_call_summary,
    serialize_summary,
)


def generate_and_save_call_summary(db: Session, session_id: str) -> Dict[str, Any]:
    """Generate a structured post-call executive summary and persist it to SQLite."""
    session = get_session(db, session_id)
    if not session:
        raise ValueError(f"Session '{session_id}' not found.")

    lead = get_lead(db, session.lead_id)
    messages = get_session_messages(db, session_id)
    appt = (
        db.query(Appointment)
        .filter(Appointment.session_id == session_id)
        .order_by(Appointment.id.desc())
        .first()
    )

    transcript = "\n".join(
        f"{'Customer' if m.role == 'user' else 'SalesPilot AI'}: {m.content}" for m in messages
    )

    all_objections: List[str] = []
    sentiments: List[str] = []
    for m in messages:
        if m.role == "user":
            sentiments.append(m.sentiment)
            try:
                objs = json.loads(m.objections or "[]")
                for o in objs:
                    if o not in all_objections:
                        all_objections.append(o)
            except Exception:
                pass

    overall_sentiment = lead.overall_sentiment if lead else (sentiments[-1] if sentiments else "Neutral")
    qual_str = f"{lead.lead_category} ({lead.lead_score}/100)" if lead else "Cold (0/100)"
    appt_status = (
        f"{appt.status} ({appt.appointment_date} at {appt.appointment_time})"
        if appt
        else "Not Booked"
    )

    fallback_summary = {
        "summary_text": (
            f"Discovery conversation with {lead.name or 'prospective customer'} "
            f"({lead.company_name or 'Company unknown'}) regarding "
            f"{lead.interested_service or 'TechNova Solutions offerings'}. "
            f"Lead qualified as {qual_str} with {overall_sentiment} sentiment."
        ),
        "customer_requirements": (lead.business_requirement if lead and lead.business_requirement else "Requirements still being scoped."),
        "services_discussed": (lead.interested_service if lead and lead.interested_service else "General TechNova AI & Cloud Portfolio"),
        "customer_objections": ", ".join(all_objections) if all_objections else "None raised",
        "overall_sentiment": overall_sentiment,
        "lead_qualification": qual_str,
        "recommended_next_action": (
            f"Prepare tailored technical demo for {appt.appointment_date} at {appt.appointment_time}."
            if appt and appt.status == "Confirmed"
            else "Follow up with tailored proposal & schedule 30-minute discovery demo."
        ),
        "appointment_status": appt_status,
    }

    if transcript.strip():
        system_prompt = (
            "You are a B2B Sales Operations analyst. Summarize this sales call accurately using "
            "ONLY facts present in the transcript. Return JSON with exact keys: "
            "summary_text, customer_requirements, services_discussed, customer_objections, "
            "recommended_next_action."
        )
        user_prompt = (
            f"Lead Qualification: {qual_str}\n"
            f"Appointment Status: {appt_status}\n"
            f"Transcript:\n{transcript}"
        )
        llm_json = llm_client.generate_json(system_prompt=system_prompt, user_prompt=user_prompt)
        if llm_json:
            for k in [
                "summary_text",
                "customer_requirements",
                "services_discussed",
                "customer_objections",
                "recommended_next_action",
            ]:
                if llm_json.get(k):
                    fallback_summary[k] = str(llm_json[k]).strip()

    saved = save_call_summary(db, session_id=session_id, lead_id=session.lead_id, data=fallback_summary)
    return serialize_summary(saved)
