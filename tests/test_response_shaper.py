from __future__ import annotations

from backend.core.response_shaper import shape_response


def test_focused_mode_removes_banter_and_caps_questions():
    text = "Got it. Sure thing. I will do that now? Want me to start with the API? Any preference?"
    policy = {
        "mode": "focused",
        "banter_budget": 0,
        "one_question_max": 1,
        "max_chars": 900,
        "detail_requested": False,
        "offer_details_prompt": True,
        "reassurance_sentence": False,
    }
    shaped = shape_response(text, policy)
    assert not shaped.lower().startswith("got it.")
    assert shaped.count("?") <= 1


def test_one_screen_cap_adds_details_offer():
    text = " ".join(["This is a long response sentence." for _ in range(80)])
    policy = {
        "mode": "neutral",
        "banter_budget": 1,
        "one_question_max": 1,
        "max_chars": 160,
        "detail_requested": False,
        "offer_details_prompt": True,
        "reassurance_sentence": False,
    }
    shaped = shape_response(text, policy)
    assert "Want details" in shaped


def test_warm_mode_adds_reassurance_sentence():
    text = "Action plan: update env vars. Then restart the service."
    policy = {
        "mode": "warm",
        "banter_budget": 1,
        "one_question_max": 1,
        "max_chars": 900,
        "detail_requested": False,
        "offer_details_prompt": True,
        "reassurance_sentence": True,
    }
    shaped = shape_response(text, policy)
    assert "You are not stuck; I can keep this practical and brief." in shaped
