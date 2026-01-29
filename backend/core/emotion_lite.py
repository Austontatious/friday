from __future__ import annotations

import os
import re
from typing import Dict

_POSITIVE = {
    "good",
    "great",
    "awesome",
    "amazing",
    "love",
    "thanks",
    "thank",
    "nice",
    "happy",
    "appreciate",
}

_NEGATIVE = {
    "bad",
    "terrible",
    "awful",
    "hate",
    "angry",
    "frustrated",
    "annoyed",
    "upset",
    "sad",
    "worst",
}

_URGENT = {
    "urgent",
    "asap",
    "immediately",
    "now",
    "soon",
    "today",
    "quickly",
}

_CONFUSION = {
    "confused",
    "confusing",
    "unclear",
    "unsure",
    "not sure",
    "dont understand",
    "do not understand",
    "what do you mean",
    "huh",
    "why",
    "how",
    "what",
}


def enabled() -> bool:
    return os.getenv("FRIDAY_EMOTION_LITE_ENABLED", "0").lower() in {"1", "true", "yes", "on"}


def analyze(text: str) -> Dict[str, str]:
    lowered = text.lower()
    tokens = re.findall(r"[a-z0-9']+", lowered)

    pos_hits = sum(token in _POSITIVE for token in tokens)
    neg_hits = sum(token in _NEGATIVE for token in tokens)

    sentiment = "neutral"
    if pos_hits > neg_hits:
        sentiment = "positive"
    elif neg_hits > pos_hits:
        sentiment = "negative"

    urgent_hits = sum(token in _URGENT for token in tokens)
    urgency = "low"
    if urgent_hits >= 2:
        urgency = "high"
    elif urgent_hits == 1:
        urgency = "medium"

    confusion = "low"
    if any(phrase in lowered for phrase in _CONFUSION) or "?" in text:
        confusion = "medium"
    if "?" in text and any(phrase in lowered for phrase in _CONFUSION):
        confusion = "high"

    arousal = "low"
    if "!" in text or urgency == "high":
        arousal = "high"
    elif urgency == "medium" or confusion == "high":
        arousal = "medium"

    return {
        "sentiment": sentiment,
        "arousal": arousal,
        "confusion": confusion,
        "urgency": urgency,
    }
