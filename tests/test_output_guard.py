from types import SimpleNamespace

import pytest

from app.agent.guard import OutputGuard, violations
from app.models import AgentOutput


@pytest.mark.parametrize(
    "text, expected",
    [
        ("Please call 988 tonight.", ["phone_number"]),
        ("You can reach them on 1-800-891-4416.", ["phone_number"]),
        ("Tele-MANAS is there for you.", ["helpline_name"]),
        ("The Crisis Text Line can help.", ["helpline_name"]),
        ("Maybe ask your doctor about sertraline.", ["medication"]),
        ("Try 3 mg of melatonin before bed.", ["medication"]),
        ("It sounds like you have depression.", ["diagnosis"]),
        ("This could be an anxiety disorder.", ["diagnosis"]),
        ("You’re depressed, and that's okay.", ["diagnosis"]),
    ],
)
def test_flags_unsafe_reflections(text, expected):
    assert violations(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "Thanks for checking in. 7.5 hours of sleep is a good start.",
        "A 10 minute walk can help. Support is there 24/7.",
        "It sounds like the last few days have been heavy, and you've felt anxious and alone.",
        "Feeling low after a hard week makes sense. Be gentle with yourself today.",
    ],
)
def test_lets_ordinary_reflections_through(text):
    assert violations(text) == []


def event_with(output):
    return SimpleNamespace(result=SimpleNamespace(structured_output=output))


def test_replaces_unsafe_reflection_and_keeps_risk():
    output = AgentOutput(reflection="Call 988 now.", risk_level="high", risk_reason="passive ideation", coping_id="x")
    OutputGuard(replacement="standard message").check(event_with(output))
    assert output.reflection == "standard message"
    assert (output.risk_level, output.risk_reason, output.coping_id) == ("high", "passive ideation", "x")


def test_leaves_clean_reflection_alone():
    output = AgentOutput(reflection="Glad the walk helped.", risk_level="low", risk_reason="none")
    OutputGuard(replacement="standard message").check(event_with(output))
    assert output.reflection == "Glad the walk helped."


def test_ignores_failed_calls():
    OutputGuard(replacement="standard message").check(SimpleNamespace(result=None))
