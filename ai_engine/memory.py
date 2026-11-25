"""Session-isolated contextual memory and structured customer detail extraction."""

import logging
import re
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from ai_engine.llm import llm_client
from crm.operations import get_lead, get_session, get_session_messages, serialize_lead

logger = logging.getLogger(__name__)


def build_session_context(db: Session, session_id: str, max_turns: int = 12) -> Dict[str, Any]:
    """Load strictly session-isolated conversation history and lead profile from SQLite."""
    session = get_session(db, session_id)
    if not session:
        raise ValueError(f"Unknown session_id: {session_id}")

    lead = get_lead(db, session.lead_id)
    messages = get_session_messages(db, session_id)
    recent = messages[-max_turns:]

    transcript_lines = []
    for m in recent:
        speaker = "Customer" if m.role == "user" else "SalesPilot AI"
        transcript_lines.append(f"{speaker}: {m.content}")

    profile = serialize_lead(lead) if lead else {}
    return {
        "session_id": session.id,
        "lead_id": session.lead_id,
        "profile": profile,
        "history": [{"role": m.role, "content": m.content, "sentiment": m.sentiment} for m in messages],
        "formatted_history": "\n".join(transcript_lines),
    }


def _regex_extract_customer_details(message: str) -> Dict[str, Optional[str]]:
    """Deterministic fallback extractor that never hallucinates missing fields."""
    text = message.strip()
    lower = text.lower()
    extracted: Dict[str, Optional[str]] = {
        "name": None,
        "email": None,
        "phone": None,
        "company_name": None,
        "industry": None,
        "interested_service": None,
        "budget": None,
        "business_requirement": None,
        "purchase_timeline": None,
        "decision_authority": None,
    }

    # Email
    email_match = re.search(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b", text)
    if email_match:
        extracted["email"] = email_match.group(0)

    # Phone number (supports +91, US, 10+ digit formats)
    phone_match = re.search(r"(?:\+?\d{1,3}[\s.-]?)?(?:\(?\d{3,5}\)?[\s.-]?)?\d{3,5}[\s.-]?\d{4,5}", text)
    if phone_match:
        digits = re.sub(r"\D", "", phone_match.group(0))
        if 10 <= len(digits) <= 15:
            extracted["phone"] = phone_match.group(0).strip()

    # Name
    name_patterns = [
        r"(?:my name is|i am|i'm|this is)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)",
        r"(?:call me)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)",
    ]
    non_names = {
        "interested", "looking", "calling", "from", "the", "a", "an", "here",
        "sure", "ready", "happy", "trying", "building", "running", "CTO", "CEO",
    }
    for pat in name_patterns:
        m = re.search(pat, text, flags=re.IGNORECASE)
        if m:
            candidate = m.group(1).strip()
            first_word = candidate.split()[0].lower()
            if first_word not in non_names and len(candidate) >= 2:
                extracted["name"] = candidate.title()
                break

    # Company name
    comp_match = re.search(
        r"(?:from|at|with|company is|work at|representing)\s+([A-Z][A-Za-z0-9&\-\s]{1,40}?)(?:,|\.|;|\band\b|\bwe\b|\blooking\b|$)",
        text,
    )
    if comp_match:
        cand = comp_match.group(1).strip()
        if cand.lower() not in {"technova", "technova solutions", "india", "bengaluru"} and len(cand) >= 2:
            extracted["company_name"] = cand

    # Industry
    industries = {
        "fintech": "FinTech",
        "finance": "FinTech",
        "banking": "Banking & Financial Services",
        "healthcare": "Healthcare",
        "medical": "Healthcare",
        "retail": "Retail & E-Commerce",
        "ecommerce": "Retail & E-Commerce",
        "e-commerce": "Retail & E-Commerce",
        "logistics": "Logistics & Supply Chain",
        "supply chain": "Logistics & Supply Chain",
        "saas": "SaaS & Technology",
        "software": "Software & Technology",
        "education": "EdTech",
        "edtech": "EdTech",
        "manufacturing": "Manufacturing",
        "real estate": "Real Estate",
    }
    for key, label in industries.items():
        if key in lower:
            extracted["industry"] = label
            break

    # Interested service
    if any(k in lower for k in ["ai automation", "voice agent", "chatbot", "rag", "agent", "llm", "automate", "automation"]):
        extracted["interested_service"] = "AI Automation & Autonomous Agents"
    elif any(k in lower for k in ["cloud", "aws", "gcp", "azure", "devops", "kubernetes", "migration"]):
        extracted["interested_service"] = "Cloud Services & DevOps"
    elif any(k in lower for k in ["business intelligence", "bi ", "dashboard", "analytics", "data warehouse", "etl", "snowflake", "bigquery"]):
        extracted["interested_service"] = "Business Intelligence & Data Engineering"
    elif any(k in lower for k in ["custom software", "web app", "mobile app", "software development", "crm integration", "api"]):
        extracted["interested_service"] = "Custom Software Development"

    # Budget
    budget_match = re.search(
        r"(?:[\$₹€£]\s?\d[\d,]*(?:\.\d+)?(?:\s?[kKmMlL]|(?:\s?(?:k|thousand|million|lakh|lakhs|crore|crores|usd|inr|per month|/mo|monthly)))?)"
        r"|(?:\d[\d,]*(?:\.\d+)?\s?(?:k|usd|inr|dollars|rupees|lakh|lakhs)(?:\s?(?:per month|/mo|monthly|budget))?)",
        text,
        flags=re.IGNORECASE,
    )
    if budget_match:
        extracted["budget"] = budget_match.group(0).strip()

    # Purchase timeline
    timeline_patterns = [
        (r"\b(immediate|immediately|asap|this week|right away|urgent)\b", "Immediate (Within 2 weeks)"),
        (r"\b(this month|within a month|next 30 days|2 to 4 weeks|few weeks)\b", "Within 1 month"),
        (r"\b(next month|next quarter|q[1-4]|1 to 3 months|couple of months)\b", "1-3 months"),
        (r"\b(3 to 6 months|later this year|half year)\b", "3-6 months"),
        (r"\b(just exploring|no rush|next year|evaluating)\b", "Exploratory / 6+ months"),
    ]
    for pat, label in timeline_patterns:
        if re.search(pat, lower):
            extracted["purchase_timeline"] = label
            break

    # Decision authority
    authority_patterns = [
        (r"\b(ceo|cto|cfo|coo|founder|co-founder|vp|vice president|director|head of|owner|decision maker|i decide|final say|my approval)\b", "Decision Maker"),
        (r"\b(manager|lead|architect|team lead|evaluating for|recommend to|check with my)\b", "Influencer / Technical Evaluator"),
    ]
    for pat, label in authority_patterns:
        if re.search(pat, lower):
            extracted["decision_authority"] = label
            break

    # Business requirement summary
    req_triggers = ["need", "want", "looking for", "automate", "reduce", "build", "integrate", "migrate", "problem", "challenge", "help with"]
    if any(t in lower for t in req_triggers) and len(text.split()) >= 5:
        extracted["business_requirement"] = text[:300]

    return extracted


def extract_customer_details(
    message: str,
    existing_profile: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Extract customer attributes without inventing missing values (null when unknown)."""
    regex_data = _regex_extract_customer_details(message)

    system_prompt = (
        "You are a strict CRM entity extraction engine. Extract ONLY facts explicitly stated "
        "in the customer's message. NEVER guess, infer, or invent missing fields — return null "
        "for any field not explicitly mentioned. Return a JSON object with exact keys: "
        "name, email, phone, company_name, industry, interested_service, budget, "
        "business_requirement, purchase_timeline, decision_authority."
    )
    user_prompt = (
        f"Existing known profile (do not repeat unless newly updated): {existing_profile or {}}\n\n"
        f"Latest customer message:\n{message}"
    )

    llm_data = llm_client.generate_json(system_prompt=system_prompt, user_prompt=user_prompt)
    mode = "gemini" if llm_data is not None else "demo_fallback"

    merged: Dict[str, Any] = {}
    keys = [
        "name",
        "email",
        "phone",
        "company_name",
        "industry",
        "interested_service",
        "budget",
        "business_requirement",
        "purchase_timeline",
        "decision_authority",
    ]
    for k in keys:
        val = None
        if llm_data and llm_data.get(k) not in (None, "", "null", "unknown", "Unknown", "N/A"):
            val = str(llm_data[k]).strip()
        elif regex_data.get(k):
            val = regex_data[k]
        merged[k] = val

    return {
        "extracted": merged,
        "mode": mode,
    }
