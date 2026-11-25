"""Customer sentiment, engagement, purchase intent, urgency, and objection analysis."""

from typing import Any, Dict, List

from ai_engine.llm import llm_client

POSITIVE_WORDS = {
    "great", "awesome", "love", "excellent", "interested", "perfect", "sounds good",
    "yes", "definitely", "excited", "helpful", "impressive", "book", "schedule",
    "demo", "proceed", "happy", "amazing", "works", "sure",
}
NEGATIVE_WORDS = {
    "expensive", "too much", "costly", "slow", "bad", "concern", "worried",
    "not sure", "no", "cancel", "problem", "issue", "hate", "disappointed",
    "delay", "complicated", "competitor", "waste", "unhappy",
}
HIGH_INTENT_PHRASES = [
    "book a demo", "schedule", "appointment", "meeting", "pricing", "quote",
    "proposal", "sign up", "get started", "pilot", "poc", "when can we start",
    "budget is", "ready to", "need this", "looking to implement",
]
URGENCY_PHRASES = [
    "asap", "urgent", "immediately", "this week", "this month", "right away",
    "soon", "deadline", "quickly",
]
OBJECTION_PATTERNS = {
    "Pricing / Budget concern": ["expensive", "too high", "costly", "out of budget", "cheaper", "discount"],
    "Data Privacy / Security concern": ["privacy", "security", "gdpr", "dpdp", "confidential", "train on our data"],
    "Integration Complexity": ["legacy", "integrate", "sap", "erp", "difficult to connect", "existing system"],
    "Timeline / Bandwidth concern": ["no time", "too busy", "long onboarding", "takes too long"],
}


def _heuristic_sentiment(message: str) -> Dict[str, Any]:
    lower = message.lower()
    pos_hits = sum(1 for w in POSITIVE_WORDS if w in lower)
    neg_hits = sum(1 for w in NEGATIVE_WORDS if w in lower)

    if pos_hits > neg_hits:
        sentiment = "Positive"
    elif neg_hits > pos_hits:
        sentiment = "Negative"
    else:
        sentiment = "Neutral"

    word_count = len(message.split())
    if word_count >= 18 or any(p in lower for p in HIGH_INTENT_PHRASES):
        engagement = "High"
    elif word_count >= 6:
        engagement = "Medium"
    else:
        engagement = "Low"

    if any(p in lower for p in HIGH_INTENT_PHRASES):
        purchase_intent = "High"
    elif any(k in lower for k in ["tell me more", "how does", "services", "features", "can you", "integrate"]):
        purchase_intent = "Medium"
    else:
        purchase_intent = "Low"

    if any(p in lower for p in URGENCY_PHRASES):
        urgency = "High"
    elif any(k in lower for k in ["next month", "quarter", "soon", "planning"]):
        urgency = "Medium"
    else:
        urgency = "Low"

    objections: List[str] = []
    for label, triggers in OBJECTION_PATTERNS.items():
        if any(t in lower for t in triggers):
            objections.append(label)

    satisfaction = "High" if sentiment == "Positive" else ("Low" if sentiment == "Negative" else "Medium")

    return {
        "sentiment": sentiment,
        "engagement": engagement,
        "purchase_intent": purchase_intent,
        "urgency": urgency,
        "customer_satisfaction": satisfaction,
        "objections": objections,
        "mode": "demo_fallback",
    }


def analyse_customer_sentiment(message: str) -> Dict[str, Any]:
    """Analyze sentiment, engagement, purchase intent, urgency, satisfaction, and objections."""
    fallback = _heuristic_sentiment(message)

    system_prompt = (
        "You are a B2B sales conversation analyst. Analyze the customer message and return "
        "a JSON object with exact keys:\n"
        "- sentiment: 'Positive' | 'Neutral' | 'Negative'\n"
        "- engagement: 'High' | 'Medium' | 'Low'\n"
        "- purchase_intent: 'High' | 'Medium' | 'Low'\n"
        "- urgency: 'High' | 'Medium' | 'Low'\n"
        "- customer_satisfaction: 'High' | 'Medium' | 'Low'\n"
        "- objections: list of concise objection strings (empty list [] if none)"
    )
    llm_res = llm_client.generate_json(system_prompt=system_prompt, user_prompt=message)
    if not llm_res:
        return fallback

    valid_sent = {"Positive", "Neutral", "Negative"}
    valid_lvl = {"High", "Medium", "Low"}

    return {
        "sentiment": llm_res.get("sentiment") if llm_res.get("sentiment") in valid_sent else fallback["sentiment"],
        "engagement": llm_res.get("engagement") if llm_res.get("engagement") in valid_lvl else fallback["engagement"],
        "purchase_intent": llm_res.get("purchase_intent") if llm_res.get("purchase_intent") in valid_lvl else fallback["purchase_intent"],
        "urgency": llm_res.get("urgency") if llm_res.get("urgency") in valid_lvl else fallback["urgency"],
        "customer_satisfaction": llm_res.get("customer_satisfaction") if llm_res.get("customer_satisfaction") in valid_lvl else fallback["customer_satisfaction"],
        "objections": llm_res.get("objections") if isinstance(llm_res.get("objections"), list) else fallback["objections"],
        "mode": "gemini",
    }
