from __future__ import annotations

import os
import re
from typing import Any, Dict, Iterable, List, Optional

_ALLOWED_MODES = {"focused", "neutral", "warm", "playful"}
_V1_ALLOWED_MODES = {"focused", "neutral", "warm"}

_URGENCY_WORDS = {
    "now",
    "asap",
    "urgent",
    "immediately",
    "quick",
    "quickly",
    "right",
    "today",
}

_PROFANITY = {
    "fuck",
    "fucking",
    "shit",
    "damn",
    "bitch",
    "asshole",
    "wtf",
}

_IMPERATIVE_STARTS = {
    "do",
    "fix",
    "write",
    "show",
    "run",
    "make",
    "update",
    "check",
    "open",
    "start",
    "stop",
    "send",
    "build",
    "test",
    "summarize",
    "explain",
    "answer",
    "list",
    "refactor",
}

_WARM_WORDS = {
    "thanks",
    "thank",
    "appreciate",
    "please",
}

_CORRECTION_RE = re.compile(
    r"(?:\bthat(?:'s| is) not it\b|\bnot what i asked\b|\bread what i said\b|\byou ignored\b|\bstop\b|\bwrong\b)",
    re.IGNORECASE,
)

_OVERRIDE_FOCUSED_RE = re.compile(
    r"(?:\bbe brief\b|\bbe concise\b|\bbrief mode\b|\bno fluff\b|\bjust do it\b|\bjust do this\b)",
    re.IGNORECASE,
)
_OVERRIDE_WARM_RE = re.compile(
    r"(?:\bbe human\b|\bmore human\b|\btalk like a human\b|\bbe warm\b|\bwarmer tone\b)",
    re.IGNORECASE,
)
_OVERRIDE_NEUTRAL_RE = re.compile(
    r"(?:\bbe neutral\b|\bneutral tone\b)",
    re.IGNORECASE,
)
_OVERRIDE_PLAYFUL_RE = re.compile(
    r"(?:\bbe playful\b|\bplayful mode\b|\bjoke around\b|\byou can joke\b)",
    re.IGNORECASE,
)
_OVERRIDE_NO_BANTER_RE = re.compile(
    r"(?:\bno banter\b|\bstop banter\b|\bno jokes\b|\bcut banter\b)",
    re.IGNORECASE,
)
_OVERRIDE_ALLOW_BANTER_RE = re.compile(
    r"(?:\bbanter is ok\b|\bbanter's ok\b|\bjokes are ok\b|\byou can banter\b)",
    re.IGNORECASE,
)


def _env_bool(key: str, default: str = "0") -> bool:
    return os.getenv(key, default).strip().lower() in {"1", "true", "yes", "on"}


def _env_int(key: str, default: int) -> int:
    raw = os.getenv(key)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value > 0 else default


def _tokens(text: str) -> List[str]:
    return re.findall(r"[a-z0-9']+", text.lower())


def _is_short_imperative(text: str) -> bool:
    compact = " ".join(text.strip().split())
    if not compact:
        return False
    if "?" in compact:
        return False
    words = _tokens(compact)
    if not words or len(words) > 7:
        return False
    return words[0] in _IMPERATIVE_STARTS


def _caps_ratio(text: str) -> float:
    letters = [ch for ch in text if ch.isalpha()]
    if len(letters) < 8:
        return 0.0
    upper = sum(1 for ch in letters if ch.isupper())
    return upper / float(len(letters))


def _iter_user_texts(recent_turns: Iterable[Dict[str, Any]], current_prompt: str) -> List[str]:
    texts: List[str] = []
    for turn in recent_turns:
        if not isinstance(turn, dict):
            continue
        if str(turn.get("role") or "").lower() != "user":
            continue
        content = str(turn.get("content") or "").strip()
        if content:
            texts.append(content)
    current = str(current_prompt or "").strip()
    if current:
        texts.append(current)
    return texts


def _resolve_overrides(user_texts: List[str], playful_enabled: bool) -> Dict[str, Any]:
    mode_override: Optional[str] = None
    mode_override_phrase = ""
    no_banter = False
    for text in user_texts:
        if _OVERRIDE_FOCUSED_RE.search(text):
            mode_override = "focused"
            mode_override_phrase = "be brief"
        if _OVERRIDE_WARM_RE.search(text):
            mode_override = "warm"
            mode_override_phrase = "be human"
        if _OVERRIDE_NEUTRAL_RE.search(text):
            mode_override = "neutral"
            mode_override_phrase = "be neutral"
        if playful_enabled and _OVERRIDE_PLAYFUL_RE.search(text):
            mode_override = "playful"
            mode_override_phrase = "be playful"
        if _OVERRIDE_NO_BANTER_RE.search(text):
            no_banter = True
        if _OVERRIDE_ALLOW_BANTER_RE.search(text):
            no_banter = False
    return {
        "mode_override": mode_override,
        "mode_override_phrase": mode_override_phrase,
        "no_banter_override": no_banter,
    }


def _count_corrections(user_texts: List[str]) -> int:
    return sum(1 for text in user_texts[-6:] if _CORRECTION_RE.search(text))


def _infer_mode(
    current_prompt: str,
    *,
    correction_count: int,
    tool_failure_loop_count: int,
    default_mode: str,
) -> Dict[str, Any]:
    lowered = current_prompt.lower()
    toks = _tokens(current_prompt)
    urgency_hits = sum(tok in _URGENCY_WORDS for tok in toks)
    profanity_hits = sum(tok in _PROFANITY for tok in toks)
    caps_ratio = _caps_ratio(current_prompt)
    caps_hit = caps_ratio >= 0.45
    short_imperative_hit = _is_short_imperative(current_prompt)

    focused_score = 0
    if urgency_hits:
        focused_score += 2
    if profanity_hits:
        focused_score += 2
    if caps_hit:
        focused_score += 2
    if short_imperative_hit:
        focused_score += 2
    if correction_count >= 2:
        focused_score += 2
    if tool_failure_loop_count >= 2:
        focused_score += 2
    elif tool_failure_loop_count == 1:
        focused_score += 1

    warm_hits = sum(tok in _WARM_WORDS for tok in toks)
    warm_score = 0
    if warm_hits:
        warm_score += 2
    if ("please" in lowered or "thanks" in lowered) and focused_score == 0:
        warm_score += 1

    inferred_mode = default_mode
    if focused_score >= 3 and focused_score >= warm_score + 1:
        inferred_mode = "focused"
    elif warm_score >= 2 and focused_score < 3:
        inferred_mode = "warm"
    elif default_mode in _V1_ALLOWED_MODES:
        inferred_mode = default_mode
    else:
        inferred_mode = "neutral"

    return {
        "mode": inferred_mode,
        "signals": {
            "urgency_hits": urgency_hits,
            "profanity_hits": profanity_hits,
            "caps_ratio": round(caps_ratio, 3),
            "caps_hit": caps_hit,
            "short_imperative_hit": short_imperative_hit,
            "correction_count": correction_count,
            "tool_failure_loop_count": tool_failure_loop_count,
            "focused_score": focused_score,
            "warm_score": warm_score,
        },
    }


def _mode_spec(mode: str, no_banter_override: bool) -> Dict[str, Any]:
    if mode == "focused":
        banter_budget = 0
        response_shape = "action_then_next_step"
        reassurance_sentence = False
    elif mode == "warm":
        banter_budget = 1
        response_shape = "action_then_reassurance"
        reassurance_sentence = True
    elif mode == "playful":
        banter_budget = 1
        response_shape = "summary_then_options"
        reassurance_sentence = False
    else:
        banter_budget = 1
        response_shape = "summary_then_options"
        reassurance_sentence = False

    if no_banter_override:
        banter_budget = 0

    return {
        "banter_budget": banter_budget,
        "response_shape": response_shape,
        "reassurance_sentence": reassurance_sentence,
    }


def _sanitize_default_mode(raw: str) -> str:
    value = (raw or "").strip().lower()
    if value in _V1_ALLOWED_MODES:
        return value
    return "neutral"


def build_interaction_policy(
    *,
    prompt: str,
    recent_turns: Iterable[Dict[str, Any]],
    tool_failure_loop_count: int = 0,
) -> Dict[str, Any]:
    playful_enabled = _env_bool("FRIDAY_INTERACTION_PLAYFUL_ENABLED", "0")
    default_mode = _sanitize_default_mode(os.getenv("FRIDAY_INTERACTION_DEFAULT_MODE", "neutral"))
    max_chars = _env_int("FRIDAY_INTERACTION_ONE_SCREEN_CHARS", 900)

    user_texts = _iter_user_texts(recent_turns, prompt)
    overrides = _resolve_overrides(user_texts, playful_enabled)
    correction_count = _count_corrections(user_texts)
    detail_requested = bool(
        re.search(
            r"(?:\bdetail\b|\bdetails\b|\bexplain\b|\bdeep dive\b|\bwalk me through\b|\bwhy\b)",
            prompt,
            re.IGNORECASE,
        )
    )
    inferred = _infer_mode(
        prompt,
        correction_count=correction_count,
        tool_failure_loop_count=tool_failure_loop_count,
        default_mode=default_mode,
    )

    mode = inferred["mode"]
    mode_source = "inferred"
    explicit_override = ""
    mode_override = overrides["mode_override"]
    if isinstance(mode_override, str) and mode_override in _ALLOWED_MODES:
        mode = mode_override
        mode_source = "override"
        explicit_override = str(overrides["mode_override_phrase"] or "")

    if mode == "playful" and not playful_enabled:
        mode = "neutral"
        mode_source = "default"
        explicit_override = ""

    spec = _mode_spec(mode, bool(overrides["no_banter_override"]))
    return {
        "mode": mode,
        "mode_source": mode_source,
        "explicit_override": explicit_override,
        "banter_budget": spec["banter_budget"],
        "one_question_max": 1,
        "max_chars": max_chars,
        "response_shape": spec["response_shape"],
        "reassurance_sentence": spec["reassurance_sentence"],
        "detail_requested": detail_requested,
        "offer_details_prompt": True,
        "certainty_policy": "assert_on_verified_outputs_else_state_assumptions",
        "memory_policy": "apply_memory_silently_and_confirm_once_if_behavior_changes",
        "signals": inferred["signals"],
    }


def render_policy_block(policy: Dict[str, Any]) -> str:
    mode = str(policy.get("mode") or "neutral")
    source = str(policy.get("mode_source") or "inferred")
    banter_budget = int(policy.get("banter_budget") or 0)
    question_cap = int(policy.get("one_question_max") or 1)
    max_chars = int(policy.get("max_chars") or 900)
    response_shape = str(policy.get("response_shape") or "summary_then_options")
    return (
        "<INTERACTION_POLICY>\n"
        f"mode={mode}\n"
        f"mode_source={source}\n"
        f"response_shape={response_shape}\n"
        f"banter_budget_sentences={banter_budget}\n"
        f"question_cap={question_cap}\n"
        f"one_screen_max_chars={max_chars}\n"
        "rules:\n"
        "- Ask at most one question unless blocked.\n"
        "- Prefer bullets over long paragraphs.\n"
        "- If uncertain, state assumptions briefly and continue.\n"
        "- Use blame-free recovery language on failures.\n"
        "- Use memory only when it reduces user work.\n"
        "</INTERACTION_POLICY>"
    )
