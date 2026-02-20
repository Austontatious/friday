from __future__ import annotations

from backend.core.interaction_policy import build_interaction_policy, render_policy_block


def test_explicit_brief_override_forces_focused_mode():
    policy = build_interaction_policy(
        prompt="Be brief and just do it.",
        recent_turns=[],
    )
    assert policy["mode"] == "focused"
    assert policy["mode_source"] == "override"
    assert policy["banter_budget"] == 0


def test_playful_mode_requires_env_opt_in(monkeypatch):
    monkeypatch.delenv("FRIDAY_INTERACTION_PLAYFUL_ENABLED", raising=False)
    policy = build_interaction_policy(prompt="Be playful.", recent_turns=[])
    assert policy["mode"] != "playful"

    monkeypatch.setenv("FRIDAY_INTERACTION_PLAYFUL_ENABLED", "1")
    policy = build_interaction_policy(prompt="Be playful.", recent_turns=[])
    assert policy["mode"] == "playful"
    assert policy["mode_source"] == "override"


def test_rule_inference_uses_urgency_caps_and_corrections():
    recent_turns = [
        {"role": "user", "content": "That is not it."},
        {"role": "assistant", "content": "Retrying."},
        {"role": "user", "content": "Read what I said."},
    ]
    policy = build_interaction_policy(
        prompt="FIX THIS NOW",
        recent_turns=recent_turns,
        tool_failure_loop_count=1,
    )
    assert policy["mode"] == "focused"
    assert policy["signals"]["focused_score"] >= 3


def test_no_banter_override_sets_budget_to_zero():
    recent_turns = [{"role": "user", "content": "Be human."}]
    policy = build_interaction_policy(
        prompt="No banter.",
        recent_turns=recent_turns,
    )
    assert policy["banter_budget"] == 0


def test_policy_block_includes_mode_and_limits():
    policy = build_interaction_policy(prompt="status", recent_turns=[])
    block = render_policy_block(policy)
    assert "<INTERACTION_POLICY>" in block
    assert f"mode={policy['mode']}" in block
    assert "question_cap=1" in block
