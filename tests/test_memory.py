from __future__ import annotations

from backend.memory.provider import extract_memory_candidates, render_system_memory_block


def test_render_system_memory_block_is_capped(monkeypatch):
    monkeypatch.setenv("FRIDAY_MEMORY_MAX_INJECT_CARDS", "2")
    monkeypatch.setenv("FRIDAY_MEMORY_MAX_INJECT_BULLETS", "1")
    monkeypatch.setenv("FRIDAY_MEMORY_MAX_INJECT_CHARS", "180")
    monkeypatch.setenv("FRIDAY_MEMORY_MAX_INJECT_TOKENS", "45")

    cards = [
        {"title": "Profile", "card_type": "fact", "bullets": ["Loves black coffee", "Secondary detail"]},
        {"title": "Preferences", "card_type": "preference", "bullets": ["Prefers concise replies"]},
        {"title": "Tasks", "card_type": "task", "bullets": ["This card should be dropped"]},
    ]

    block = render_system_memory_block(cards, max_cards=8, max_bullets=3)

    assert block.startswith("<SYSTEM_MEMORY>")
    assert block.endswith("</SYSTEM_MEMORY>")
    assert block.count("\n- ") <= 2
    assert len(block) <= 180


def test_extract_memory_candidates_flags_sensitive_contact_info():
    text = "Call me Nova. My email is nova@example.com and my number is (555) 222-1111."
    candidates = extract_memory_candidates(text, "ent_test", source_id="device:test")
    by_kind = {item.get("kind"): item for item in candidates}

    assert "fact" in by_kind
    assert "email" in by_kind
    assert "phone" in by_kind
    assert by_kind["email"].get("policy", {}).get("requires_confirmation") is True
    assert by_kind["phone"].get("policy", {}).get("requires_confirmation") is True
