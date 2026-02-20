from __future__ import annotations

import re
from typing import Any, Dict, List

_ACK_START_RE = re.compile(
    r"^(?:got it|okay|ok|sure|absolutely|understood|no problem|happy to help|sounds good)\b",
    re.IGNORECASE,
)
_ACTION_WORDS = {
    "do",
    "run",
    "fix",
    "update",
    "check",
    "create",
    "remove",
    "review",
    "write",
    "set",
    "use",
    "apply",
    "open",
    "build",
    "test",
}
_WARM_REASSURANCE_RE = re.compile(
    r"(?:you're not stuck|you are not stuck|you're on track|you are on track|i can keep this practical)",
    re.IGNORECASE,
)
_DEFAULT_WARM_REASSURANCE = "You are not stuck; I can keep this practical and brief."


def _split_sentences(text: str) -> List[str]:
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [part.strip() for part in parts if part.strip()]


def _looks_like_ack(sentence: str) -> bool:
    if not _ACK_START_RE.match(sentence):
        return False
    words = re.findall(r"[a-z0-9']+", sentence.lower())
    if any(word in _ACTION_WORDS for word in words):
        return False
    return len(words) <= 14


def _apply_banter_budget(text: str, budget: int) -> str:
    sentences = _split_sentences(text)
    if not sentences:
        return text.strip()
    if budget < 0:
        budget = 0

    kept: List[str] = []
    ack_count = 0
    index = 0
    while index < len(sentences):
        sentence = sentences[index]
        if _looks_like_ack(sentence):
            if ack_count < budget:
                kept.append(sentence)
            ack_count += 1
            index += 1
            continue
        break

    kept.extend(sentences[index:])
    if not kept:
        kept = sentences[:1]
    return " ".join(kept).strip()


def _enforce_question_cap(text: str, cap: int) -> str:
    if cap < 0:
        cap = 0
    out: List[str] = []
    seen = 0
    for ch in text:
        if ch == "?":
            seen += 1
            if seen > cap:
                out.append(".")
            else:
                out.append(ch)
        else:
            out.append(ch)
    return "".join(out)


def _truncate_to_boundary(text: str, limit: int) -> tuple[str, bool]:
    if limit <= 0 or len(text) <= limit:
        return text, False
    clipped = text[:limit]
    boundary = max(clipped.rfind(". "), clipped.rfind("! "), clipped.rfind("? "), clipped.rfind("\n"))
    if boundary >= int(limit * 0.55):
        clipped = clipped[: boundary + 1]
    return clipped.rstrip(), True


def _ensure_warm_reassurance(text: str) -> str:
    if _WARM_REASSURANCE_RE.search(text):
        return text
    if text.endswith((".", "!", "?")):
        return f"{text}\n\n{_DEFAULT_WARM_REASSURANCE}"
    return f"{text}. \n\n{_DEFAULT_WARM_REASSURANCE}"


def _maybe_bulletize(text: str, mode: str) -> str:
    if mode not in {"focused", "neutral"}:
        return text
    if "\n-" in text or "\n1." in text or "\n*" in text:
        return text
    sentences = _split_sentences(text)
    if len(sentences) < 3:
        return text
    head = sentences[0]
    bullets = [f"- {sentence}" for sentence in sentences[1:4]]
    return f"{head}\n" + "\n".join(bullets)


def shape_response(text: str, policy: Dict[str, Any]) -> str:
    cleaned = str(text or "").strip()
    if not cleaned:
        return cleaned

    original_sentence_count = len(_split_sentences(cleaned))
    mode = str(policy.get("mode") or "neutral")
    banter_budget = int(policy.get("banter_budget") or 0)
    question_cap = int(policy.get("one_question_max") or 1)
    max_chars = int(policy.get("max_chars") or 900)
    detail_requested = bool(policy.get("detail_requested"))
    offer_details_prompt = bool(policy.get("offer_details_prompt", True))
    reassurance_sentence = bool(policy.get("reassurance_sentence"))

    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    cleaned = _apply_banter_budget(cleaned, banter_budget)
    cleaned = _enforce_question_cap(cleaned, question_cap)
    cleaned = _maybe_bulletize(cleaned, mode)
    if mode == "warm" and reassurance_sentence:
        cleaned = _ensure_warm_reassurance(cleaned)

    if not detail_requested:
        cleaned, truncated = _truncate_to_boundary(cleaned, max_chars)
        should_offer_details = truncated or original_sentence_count > 4
        if should_offer_details and offer_details_prompt and "Want details?" not in cleaned:
            if cleaned.count("?") >= question_cap:
                cleaned = f"{cleaned}\n\nWant details, say the word."
            else:
                cleaned = f"{cleaned}\n\nWant details?"

    return cleaned.strip()
