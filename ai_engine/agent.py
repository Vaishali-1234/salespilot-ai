"""Modular tool-using AI Sales Agent orchestrator for TechNova Solutions."""

from datetime import datetime, timedelta
import logging
import re
import time
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from ai_engine.lead_qualification import qualify_lead_profile
from ai_engine.llm import llm_client
from ai_engine.memory import build_session_context, extract_customer_details
from ai_engine.sentiment import analyse_customer_sentiment
from ai_engine.summarizer import generate_and_save_call_summary
from crm.operations import (
    AVAILABLE_TIME_SLOTS,
    add_message,
    book_appointment_record,
    get_available_slots,
    get_lead,
    get_session,
    search_leads,
    serialize_lead,
    update_lead,
)
from rag.retriever import KnowledgeRetriever, default_retriever

logger = logging.getLogger(__name__)


GREETING_MESSAGE = (
    "Hello! Welcome to TechNova Solutions. I'm SalesPilot AI, your autonomous AI sales "
    "consultant. We help businesses scale with AI Automation & Autonomous Agents, Cloud "
    "Modernization, Custom Software Development, and Business Intelligence. "
    "What business challenge or project are you exploring today?"
)


class SalesPilotAgent:
    """Autonomous tool-orchestrating AI sales representative."""

    def __init__(self, retriever: Optional[KnowledgeRetriever] = None) -> None:
        self.retriever = retriever or default_retriever

    # ------------------------------------------------------------------
    # Explicit Agent Tool Interface (Section 5 of architecture spec)
    # ------------------------------------------------------------------
    def retrieve_company_information(self, query: str, top_k: int = 4) -> Dict[str, Any]:
        return self.retriever.retrieve_company_information(query=query, top_k=top_k)

    def extract_customer_details(self, message: str, existing_profile: Dict[str, Any]) -> Dict[str, Any]:
        return extract_customer_details(message=message, existing_profile=existing_profile)

    def qualify_lead(
        self,
        profile: Dict[str, Any],
        purchase_intent: str = "Low",
        urgency: str = "Low",
        sentiment: str = "Neutral",
    ) -> Dict[str, Any]:
        return qualify_lead_profile(
            profile=profile,
            purchase_intent=purchase_intent,
            urgency=urgency,
            sentiment=sentiment,
        )

    def analyse_sentiment(self, message: str) -> Dict[str, Any]:
        return analyse_customer_sentiment(message=message)

    def search_crm(self, db: Session, query: str) -> List[Dict[str, Any]]:
        return [serialize_lead(l) for l in search_leads(db, query=query)]

    def create_or_update_lead(self, db: Session, lead_id: int, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        lead = update_lead(db, lead_id=lead_id, updates=updates)
        return serialize_lead(lead) if lead else None

    def check_appointment_availability(self, db: Session, target_date: Optional[str] = None) -> Dict[str, Any]:
        return get_available_slots(db, target_date=target_date)

    def book_appointment(
        self,
        db: Session,
        lead_id: int,
        session_id: str,
        customer_name: str,
        customer_email: str,
        appointment_date: str,
        appointment_time: str,
        confirmed_by_customer: bool = False,
        topic: str = "TechNova Solutions Technical Discovery Demo",
    ) -> Dict[str, Any]:
        return book_appointment_record(
            db=db,
            lead_id=lead_id,
            session_id=session_id,
            customer_name=customer_name,
            customer_email=customer_email,
            appointment_date=appointment_date,
            appointment_time=appointment_time,
            confirmed_by_customer=confirmed_by_customer,
            topic=topic,
        )

    def generate_call_summary(self, db: Session, session_id: str) -> Dict[str, Any]:
        return generate_and_save_call_summary(db, session_id=session_id)

    # ------------------------------------------------------------------
    # Intent & Slot Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _is_company_knowledge_query(message: str) -> bool:
        lower = message.lower()
        kb_keywords = [
            "technova", "service", "services", "offer", "product", "pricing", "price",
            "cost", "plan", "package", "starter", "growth", "enterprise", "ai automation",
            "agent", "rag", "cloud", "aws", "gcp", "azure", "devops", "bi", "dashboard",
            "custom software", "faq", "security", "gdpr", "dpdp", "soc 2", "iso", "sla",
            "support", "refund", "cancel", "discount", "poc", "pilot", "timeline", "how fast",
            "integrate", "salesforce", "hubspot", "zoho", "sap", "scale", "100,000",
            "hardware", "chip", "cryptocurrency", "bitcoin", "do you sell", "do you offer",
        ]
        return any(k in lower for k in kb_keywords) or "?" in message

    @staticmethod
    def _is_booking_intent(message: str, history: List[Dict[str, Any]]) -> bool:
        lower = message.lower()
        booking_words = [
            "book", "schedule", "appointment", "meeting", "demo", "consultation",
            "call with", "slot", "available", "availability", "calendar", "tomorrow",
            "confirm",
        ]
        if any(w in lower for w in booking_words):
            return True
        # Check if user is replying to an agent slot proposal with a time/yes
        if history:
            last_assistant = next(
                (h["content"].lower() for h in reversed(history) if h["role"] == "assistant"),
                "",
            )
            if "available slots" in last_assistant or "confirm" in last_assistant and "slot" in last_assistant:
                if any(t in lower for t in ["am", "pm", "10:00", "11:30", "02:00", "2:00", "03:30", "3:30", "05:00", "5:00", "yes", "confirm", "sure"]):
                    return True
        return False

    @staticmethod
    def _parse_date_and_time(message: str) -> tuple[Optional[str], Optional[str]]:
        lower = message.lower()
        parsed_date: Optional[str] = None
        iso_match = re.search(r"\b(20\d{2}-\d{2}-\d{2})\b", message)
        if iso_match:
            parsed_date = iso_match.group(1)
        elif "today" in lower:
            parsed_date = datetime.now().strftime("%Y-%m-%d")
        elif "tomorrow" in lower:
            parsed_date = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        elif "day after tomorrow" in lower:
            parsed_date = (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d")

        parsed_time: Optional[str] = None
        slot_aliases = {
            "10:00 am": "10:00 AM", "10 am": "10:00 AM", "10:00": "10:00 AM",
            "11:30 am": "11:30 AM", "11:30": "11:30 AM",
            "02:00 pm": "02:00 PM", "2:00 pm": "02:00 PM", "2 pm": "02:00 PM", "14:00": "02:00 PM",
            "03:30 pm": "03:30 PM", "3:30 pm": "03:30 PM", "15:30": "03:30 PM",
            "05:00 pm": "05:00 PM", "5:00 pm": "05:00 PM", "5 pm": "05:00 PM", "17:00": "05:00 PM",
        }
        for alias, canonical in slot_aliases.items():
            if alias in lower:
                parsed_time = canonical
                break
        return parsed_date, parsed_time

    @staticmethod
    def _is_explicit_confirmation(message: str) -> bool:
        lower = message.lower()
        return any(
            phrase in lower
            for phrase in [
                "yes", "confirm", "book it", "go ahead", "please book",
                "lock it in", "sounds good", "that works", "perfect",
            ]
        )

    # ------------------------------------------------------------------
    # Main Conversational Turn Execution
    # ------------------------------------------------------------------
    def process_turn(
        self,
        db: Session,
        session_id: str,
        user_message: str,
    ) -> Dict[str, Any]:
        """Execute a complete autonomous agent turn: memory, sentiment, RAG, qualification, booking, and CRM sync."""
        t0 = time.perf_counter()
        session = get_session(db, session_id)
        if not session:
            raise ValueError(f"Session '{session_id}' not found.")

        context = build_session_context(db, session_id)
        profile = context["profile"]
        tool_events: List[Dict[str, Any]] = []

        # 1. Sentiment & Intent Analysis
        sentiment_res = self.analyse_sentiment(user_message)
        tool_events.append({"tool": "analyse_sentiment", "status": "ok", "result": sentiment_res})

        # 2. Extract Customer Details (never invents missing values)
        extraction_res = self.extract_customer_details(user_message, existing_profile=profile)
        extracted_fields = {
            k: v for k, v in extraction_res["extracted"].items() if v is not None
        }
        tool_events.append({"tool": "extract_customer_details", "status": "ok", "fields": extracted_fields})

        if extracted_fields:
            updated_profile = self.create_or_update_lead(db, session.lead_id, extracted_fields) or profile
        else:
            updated_profile = profile

        # 3. Qualify Lead & Persist Score to CRM
        qual_res = self.qualify_lead(
            profile=updated_profile,
            purchase_intent=sentiment_res["purchase_intent"],
            urgency=sentiment_res["urgency"],
            sentiment=sentiment_res["sentiment"],
        )
        lead_updates = {
            "lead_score": qual_res["lead_score"],
            "lead_category": qual_res["lead_category"],
            "score_reasoning": qual_res["score_reasoning"],
            "overall_sentiment": sentiment_res["sentiment"],
        }
        if updated_profile.get("status") == "New" and qual_res["lead_score"] >= 40:
            lead_updates["status"] = "Qualified"
        updated_profile = self.create_or_update_lead(db, session.lead_id, lead_updates) or updated_profile
        tool_events.append({"tool": "qualify_lead", "status": "ok", "result": qual_res})
        tool_events.append({"tool": "create_or_update_lead", "status": "ok", "lead_id": session.lead_id})

        # 4. RAG Knowledge Retrieval
        rag_res: Dict[str, Any] = {"found": False, "results": [], "sources": [], "context_text": ""}
        if self._is_company_knowledge_query(user_message):
            rag_res = self.retrieve_company_information(user_message, top_k=4)
            tool_events.append(
                {
                    "tool": "retrieve_company_information",
                    "status": "ok",
                    "found": rag_res["found"],
                    "sources": rag_res["sources"],
                }
            )

        # 5. Appointment Availability & Confirmation-Gated Booking
        booking_outcome: Optional[Dict[str, Any]] = None
        availability_info: Optional[Dict[str, Any]] = None
        if self._is_booking_intent(user_message, context["history"]):
            req_date, req_time = self._parse_date_and_time(user_message)
            target_date = req_date or (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
            availability_info = self.check_appointment_availability(db, target_date=target_date)
            tool_events.append(
                {
                    "tool": "check_appointment_availability",
                    "status": "ok",
                    "date": availability_info["date"],
                    "available_slots": availability_info["available_slots"],
                }
            )

            cust_name = updated_profile.get("name")
            cust_email = updated_profile.get("email")
            explicit_confirm = self._is_explicit_confirmation(user_message)

            if req_time and explicit_confirm and cust_name and cust_email:
                booking_outcome = self.book_appointment(
                    db=db,
                    lead_id=session.lead_id,
                    session_id=session_id,
                    customer_name=cust_name,
                    customer_email=cust_email,
                    appointment_date=target_date,
                    appointment_time=req_time,
                    confirmed_by_customer=True,
                )
                tool_events.append({"tool": "book_appointment", "status": "executed", "result": booking_outcome})
                updated_profile = serialize_lead(get_lead(db, session.lead_id))
            else:
                tool_events.append(
                    {
                        "tool": "book_appointment",
                        "status": "awaiting_confirmation",
                        "missing": [
                            k
                            for k, v in {
                                "customer_name": cust_name,
                                "customer_email": cust_email,
                                "time_slot": req_time,
                                "explicit_confirmation": explicit_confirm,
                            }.items()
                            if not v
                        ],
                    }
                )

        # 6. Persist User Message Turn
        add_message(
            db=db,
            session_id=session_id,
            role="user",
            content=user_message,
            sentiment=sentiment_res["sentiment"],
            engagement=sentiment_res["engagement"],
            purchase_intent=sentiment_res["purchase_intent"],
            urgency=sentiment_res["urgency"],
            objections=sentiment_res["objections"],
        )

        # 7. Generate Grounded Sales Response (Gemini primary, honest demo fallback)
        reply_text, ai_mode, fallback_reason = self._compose_reply(
            user_message=user_message,
            context=context,
            profile=updated_profile,
            qual_res=qual_res,
            sentiment_res=sentiment_res,
            rag_res=rag_res,
            availability_info=availability_info,
            booking_outcome=booking_outcome,
        )

        # Update session ai_mode transparently
        session.ai_mode = ai_mode
        db.commit()

        latency_ms = round((time.perf_counter() - t0) * 1000, 1)
        add_message(
            db=db,
            session_id=session_id,
            role="assistant",
            content=reply_text,
            rag_sources=rag_res.get("results", []),
            tool_events=tool_events,
            latency_ms=latency_ms,
        )

        return {
            "session_id": session_id,
            "lead_id": session.lead_id,
            "reply": reply_text,
            "ai_mode": ai_mode,
            "fallback_reason": fallback_reason,
            "sentiment": sentiment_res,
            "qualification": qual_res,
            "lead_profile": updated_profile,
            "rag_sources": rag_res.get("results", []),
            "tool_events": tool_events,
            "appointment": booking_outcome.get("appointment") if booking_outcome and booking_outcome.get("success") else None,
            "latency_ms": latency_ms,
        }

    def _compose_reply(
        self,
        user_message: str,
        context: Dict[str, Any],
        profile: Dict[str, Any],
        qual_res: Dict[str, Any],
        sentiment_res: Dict[str, Any],
        rag_res: Dict[str, Any],
        availability_info: Optional[Dict[str, Any]],
        booking_outcome: Optional[Dict[str, Any]],
    ) -> tuple[str, str, Optional[str]]:
        system_prompt = (
            "You are SalesPilot AI, a warm, consultative senior sales representative at TechNova Solutions. "
            "Speak naturally in concise paragraphs (2-4 sentences plus bullet points only when helpful) so "
            "it sounds great when spoken aloud via Text-to-Speech.\n"
            "STRICT RULES:\n"
            "1. Only state TechNova facts, prices, SLAs, and policies present in the RETRIEVED KNOWLEDGE.\n"
            "2. If RETRIEVED KNOWLEDGE is empty for a factual company question, explicitly state: "
            "'I don't have sufficient information in our knowledge base on that specific detail, "
            "but I can connect you with our Solutions Architect to clarify.' Never hallucinate.\n"
            "3. When citing retrieved knowledge, mention the source filename naturally or as [Source: filename].\n"
            "4. If BOOKING OUTCOME succeeded, confirm the exact date, time, name, and email.\n"
            "5. If AVAILABILITY INFO is shown and booking hasn't completed, present available slots and ask "
            "for confirmation along with any missing name/email.\n"
            "6. Gently guide discovery toward understanding requirements, budget, timeline, or decision authority."
        )

        kb_block = (
            rag_res["context_text"]
            if rag_res.get("found")
            else "NO RELEVANT KNOWLEDGE CHUNKS FOUND."
        )
        prompt = (
            f"KNOWN CUSTOMER PROFILE: {profile}\n"
            f"LEAD QUALIFICATION: {qual_res['lead_category']} ({qual_res['lead_score']}/100) | Recommended: {qual_res['recommended_plan']}\n"
            f"CUSTOMER SENTIMENT: {sentiment_res}\n"
            f"RETRIEVED KNOWLEDGE:\n{kb_block}\n\n"
            f"AVAILABILITY INFO: {availability_info}\n"
            f"BOOKING OUTCOME: {booking_outcome}\n\n"
            f"RECENT CONVERSATION:\n{context['formatted_history']}\n\n"
            f"LATEST CUSTOMER MESSAGE:\n{user_message}"
        )

        llm_resp = llm_client.generate_text(system_prompt=system_prompt, user_prompt=prompt)
        if llm_resp.mode != "demo_fallback" and llm_resp.text:
            return llm_resp.text, llm_resp.mode, None

        # Deterministic, honest Demo Fallback response builder
        reply = self._build_demo_fallback_reply(
            user_message=user_message,
            profile=profile,
            qual_res=qual_res,
            rag_res=rag_res,
            availability_info=availability_info,
            booking_outcome=booking_outcome,
        )
        return reply, "demo_fallback", llm_resp.fallback_reason

    @staticmethod
    def _build_demo_fallback_reply(
        user_message: str,
        profile: Dict[str, Any],
        qual_res: Dict[str, Any],
        rag_res: Dict[str, Any],
        availability_info: Optional[Dict[str, Any]],
        booking_outcome: Optional[Dict[str, Any]],
    ) -> str:
        name_prefix = f"{profile['name']}, " if profile.get("name") else ""

        # Case 1: Appointment booking completed or failed
        if booking_outcome is not None:
            if booking_outcome.get("success"):
                appt = booking_outcome["appointment"]
                return (
                    f"Wonderful, {appt['customer_name']}! Your consultation with TechNova Solutions "
                    f"is confirmed for {appt['appointment_date']} at {appt['appointment_time']}. "
                    f"A calendar confirmation has been logged for {appt['customer_email']}. "
                    f"Is there anything specific you'd like our Solutions Architect to prepare?"
                )
            return (
                f"I couldn't finalize that slot just yet: {booking_outcome.get('error')} "
                f"Would you like to choose another available time?"
            )

        # Case 2: Booking intent — awaiting confirmation or details
        if availability_info is not None:
            slots = ", ".join(availability_info["available_slots"]) or "No slots left on this date"
            missing_parts = []
            if not profile.get("name"):
                missing_parts.append("your full name")
            if not profile.get("email"):
                missing_parts.append("your email address")
            missing_str = (
                f" Please also share {' and '.join(missing_parts)} so I can confirm the invite."
                if missing_parts
                else f" Please reply with 'confirm' and your preferred time slot (for {profile['name']} at {profile['email']}) to lock it in."
            )
            return (
                f"I'd be happy to schedule a 30-minute discovery demo with our Solutions Architect! "
                f"For {availability_info['date']}, our available slots are: {slots}.{missing_str}"
            )

        # Case 3: RAG response
        if rag_res.get("results"):
            top = rag_res["results"][0]
            sources = ", ".join(rag_res["sources"])
            snippet = top["content"].replace("\n", " ").strip()
            if len(snippet) > 360:
                snippet = snippet[:357].rsplit(" ", 1)[0] + "..."
            follow_up = ""
            if not profile.get("budget"):
                follow_up = " What approximate monthly budget or timeline are you targeting for this initiative?"
            elif not profile.get("email"):
                follow_up = f" Based on your needs, our {qual_res['recommended_plan']} fits well — would you like to schedule a quick 30-minute discovery call?"
            return f"{name_prefix}here is what TechNova Solutions offers based on our documentation: {snippet} [Source: {sources}].{follow_up}"

        # Case 4: Unanswerable factual question -> explicit insufficient info
        if "?" in user_message and any(
            w in user_message.lower()
            for w in ["hardware", "chip", "crypto", "bitcoin", "quantum", "salary", "ceo", "wifi", "address", "stock"]
        ):
            return (
                "I do not have sufficient information in our TechNova Solutions knowledge base to answer that accurately. "
                "I can, however, share details on our AI Automation, Cloud Services, Custom Software, or BI solutions, "
                "or schedule a call with a Solutions Architect."
            )

        # Case 5: Discovery dialogue
        if not profile.get("interested_service"):
            return (
                f"Thanks for sharing, {name_prefix}I'd love to understand your goals better. "
                "Which area are you primarily focused on: AI Automation & Voice/RAG Agents, Cloud Modernization, "
                "Custom Software Development, or Business Intelligence?"
            )
        if not profile.get("budget") or not profile.get("purchase_timeline"):
            return (
                f"That sounds like a great fit for our {profile['interested_service']} team. "
                "To recommend the right engagement model — Starter ($2,500/mo), Growth ($6,500/mo), or Enterprise — "
                "what timeline and budget range are you working with?"
            )
        return (
            f"Thank you, {name_prefix}I've noted your requirements for {profile['interested_service']}. "
            f"Our {qual_res['recommended_plan']} aligns well with your goals. "
            "Would you like me to check available slots for a 30-minute technical demo?"
        )


sales_agent = SalesPilotAgent()
