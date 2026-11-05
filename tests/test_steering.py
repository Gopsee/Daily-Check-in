import asyncio

import pytest
from strands.vended_plugins.steering import Guide, Proceed

from app.agent.steering import MAX_REWRITES, ReplySteering, problems
from app.models import AgentOutput


def draft_message(reflection, risk="low", reason="none"):
    """A model response carrying the structured-output tool call, as Strands passes it to steering."""
    tool_input = {"reflection": reflection, "risk_level": risk, "risk_reason": reason, "signals": [], "coping_id": "x"}
    return {"role": "assistant", "content": [{"toolUse": {"toolUseId": "t1", "name": "AgentOutput", "input": tool_input}}]}


def steer(handler, message):
    return asyncio.run(handler.steer_after_model(agent=None, message=message, stop_reason="tool_use"))


@pytest.mark.parametrize(
    "text, expected",
    [
        ("You should see a therapist about this.", "treatment_advice"),
        ("I suggest talking to a counsellor at school.", "treatment_advice"),
        ("Consider getting an evaluation.", "treatment_advice"),
        ("It's important to talk to a professional for a proper understanding.", "treatment_advice"),
        ("Maybe speak with a mental health professional.", "treatment_advice"),
        ("The solution is to ignore them.", "quick_fix"),
        ("Just stop worrying about it.", "quick_fix"),
        ("Try to think positive!", "quick_fix"),
        ("It sounds like you have depression.", "diagnosis"),
        ("You're wondering if what you're feeling might be depression.", "diagnosis_hint"),
        ("These could be signs of anxiety.", "diagnosis_hint"),
    ],
)
def test_flags_diagnosis_treatment_and_quick_fixes(text, expected):
    assert expected in problems(text)


@pytest.mark.parametrize(
    "text",
    [
        "That sounds really painful, and it makes sense you feel alone right now.",
        "Being laughed at in class is hard. You reached out today, and that matters.",
        "A slow breath might help you feel a little steadier tonight.",
    ],
)
def test_lets_supportive_reflections_through(text):
    assert problems(text) == []


def test_guides_a_rewrite_with_the_specific_rule():
    action = steer(ReplySteering(), draft_message("You might have depression; you should see a therapist."))
    assert isinstance(action, Guide)
    assert "diagnosis" in action.reason and "professional" in action.reason and "available in the app" in action.reason


def test_proceeds_on_a_supportive_reflection():
    assert isinstance(steer(ReplySteering(), draft_message("That sounds hard. Thanks for telling me.")), Proceed)


def test_proceeds_when_there_is_no_reflection():
    message = {"role": "assistant", "content": [{"text": "Let me look at your history."}]}
    assert isinstance(steer(ReplySteering(), message), Proceed)


def test_stops_after_the_rewrite_limit_and_leaves_it_to_the_guard():
    handler = ReplySteering()
    bad = draft_message("Just stop worrying.")
    for _ in range(MAX_REWRITES):
        assert isinstance(steer(handler, bad), Guide)
    assert isinstance(steer(handler, bad), Proceed)


def test_a_rewrite_can_never_lower_risk():
    handler = ReplySteering()
    steer(handler, draft_message("You should see a doctor.", risk="high", reason="passive ideation"))
    rewritten = AgentOutput(reflection="That sounds heavy.", risk_level="low", risk_reason="none")
    kept = handler.keep_risk(rewritten)
    assert (kept.risk_level, kept.risk_reason) == ("high", "passive ideation")
    assert kept.reflection == "That sounds heavy."


def test_a_rewrite_can_still_raise_risk():
    handler = ReplySteering()
    steer(handler, draft_message("You should see a doctor.", risk="low"))
    rewritten = AgentOutput(reflection="That sounds heavy.", risk_level="high", risk_reason="r")
    assert handler.keep_risk(rewritten).risk_level == "high"
