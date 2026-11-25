"""Transparent BANT-based lead scoring and Hot/Warm/Cold qualification engine."""

import re
from typing import Any, Dict, List, Optional


def _score_budget(budget: Optional[str]) -> tuple[int, str]:
    if not budget:
        return 0, "Budget not disclosed yet (0/25)"
    lower = budget.lower()
    if any(k in lower for k in ["15,000", "15000", "15k", "20k", "50k", "100k", "enterprise", "6,500", "6500", "5,000", "5000", "10,000", "10000", "lakh", "crore"]):
        return 25, f"Strong budget readiness ({budget}) aligned with Growth/Enterprise plans (25/25)"
    if re.search(r"\d", lower):
        return 18, f"Budget specified ({budget}) — aligned with Starter/Discovery tier (18/25)"
    return 10, f"Budget mentioned ({budget}), exact figure pending confirmation (10/25)"


def _score_timeline(timeline: Optional[str], urgency: str) -> tuple[int, str]:
    if timeline:
        lower = timeline.lower()
        if any(k in lower for k in ["immediate", "asap", "week", "1 month", "this month", "urgent"]):
            return 25, f"Urgent timeline ({timeline}) (25/25)"
        if any(k in lower for k in ["1-3", "next month", "quarter", "q1", "q2", "q3", "q4"]):
            return 18, f"Near-term implementation timeline ({timeline}) (18/25)"
        if "3-6" in lower:
            return 12, f"Medium-term timeline ({timeline}) (12/25)"
        return 5, f"Early exploratory timeline ({timeline}) (5/25)"
    if urgency == "High":
        return 20, "High urgency detected in conversation (20/25)"
    return 4, "Purchase timeline unknown (4/25)"


def _score_authority(authority: Optional[str]) -> tuple[int, str]:
    if not authority:
        return 4, "Decision-making authority unknown (4/20)"
    lower = authority.lower()
    if any(k in lower for k in ["decision maker", "ceo", "cto", "cfo", "founder", "vp", "director", "owner", "head"]):
        return 20, f"Confirmed primary decision maker ({authority}) (20/20)"
    if any(k in lower for k in ["influencer", "manager", "evaluator", "lead", "architect"]):
        return 13, f"Technical evaluator / influencer ({authority}) (13/20)"
    return 6, f"Authority role noted ({authority}) (6/20)"


def _score_intent_and_need(
    interested_service: Optional[str],
    business_requirement: Optional[str],
    purchase_intent: str,
    sentiment: str,
    has_contact: bool,
) -> tuple[int, str]:
    pts = 0
    notes: List[str] = []
    if interested_service:
        pts += 10
        notes.append(f"service interest ({interested_service})")
    if business_requirement:
        pts += 10
        notes.append("clear business requirement")
    if purchase_intent == "High":
        pts += 7
        notes.append("high purchase intent")
    elif purchase_intent == "Medium":
        pts += 4
        notes.append("moderate purchase intent")
    if has_contact:
        pts += 3
        notes.append("contact details shared")
    if sentiment == "Negative":
        pts = max(0, pts - 4)
        notes.append("negative sentiment penalty")

    pts = min(30, pts)
    reason = f"Intent & need clarity: {', '.join(notes) if notes else 'minimal signals yet'} ({pts}/30)"
    return pts, reason


def qualify_lead_profile(
    profile: Dict[str, Any],
    purchase_intent: str = "Low",
    urgency: str = "Low",
    sentiment: str = "Neutral",
) -> Dict[str, Any]:
    """Compute a transparent 0-100 lead score, Hot/Warm/Cold tier, and explanation."""
    has_contact = bool(profile.get("email") or profile.get("phone"))
    intent_pts, intent_reason = _score_intent_and_need(
        interested_service=profile.get("interested_service"),
        business_requirement=profile.get("business_requirement"),
        purchase_intent=purchase_intent,
        sentiment=sentiment,
        has_contact=has_contact,
    )
    budget_pts, budget_reason = _score_budget(profile.get("budget"))
    timeline_pts, timeline_reason = _score_timeline(profile.get("purchase_timeline"), urgency)
    auth_pts, auth_reason = _score_authority(profile.get("decision_authority"))

    total_score = max(0, min(100, intent_pts + budget_pts + timeline_pts + auth_pts))

    if total_score >= 70:
        category = "Hot"
    elif total_score >= 40:
        category = "Warm"
    else:
        category = "Cold"

    service = profile.get("interested_service") or "AI Automation & Autonomous Agents"
    if total_score >= 70:
        recommended_plan = "Growth Transformation Plan ($6,500/mo) or Enterprise Custom Suite"
    elif total_score >= 40:
        recommended_plan = "Starter Automation Package ($2,500/mo) or 14-day Pilot PoC"
    else:
        recommended_plan = "Free 30-min Technical Discovery Call / Architecture Audit ($1,500)"

    reasoning = (
        f"Lead classified as {category} ({total_score}/100). "
        f"Breakdown — {intent_reason}; {budget_reason}; {timeline_reason}; {auth_reason}."
    )

    return {
        "lead_score": total_score,
        "lead_category": category,
        "score_reasoning": reasoning,
        "recommended_service": service,
        "recommended_plan": recommended_plan,
        "breakdown": {
            "intent_and_need": intent_pts,
            "budget_readiness": budget_pts,
            "timeline_urgency": timeline_pts,
            "decision_authority": auth_pts,
        },
    }
