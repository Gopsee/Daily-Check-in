from datetime import date, timedelta

import pytest
from pydantic import ValidationError
from starlette.testclient import TestClient

from app.agent.steering import problems
from app.cycle import Cycle, describe, status
from app.memory import MemoryStore
from app.models import AgentOutput
from app.web.server import create_app

TODAY = date(2026, 11, 5)


def cycle(days_ago, length=28, period_length=5, tracking=True):
    return Cycle(tracking=tracking, last_start=TODAY - timedelta(days=days_ago), length=length, period_length=period_length)


@pytest.mark.parametrize(
    "days_ago, phase, cycle_day, until_next",
    [
        (0, "period", 1, 28),        # started today
        (4, "period", 5, 24),        # last day of a 5-day period
        (5, "other", 6, 23),
        (20, "other", 21, 8),
        (21, "premenstrual", 22, 7),  # the week before the next period
        (27, "premenstrual", 28, 1),
        (28, "period", 1, 28),       # next cycle, projected forward
        (49, "premenstrual", 22, 7),
    ],
)
def test_phase_from_last_start(days_ago, phase, cycle_day, until_next):
    s = status(cycle(days_ago), TODAY)
    assert (s.phase, s.cycle_day, s.days_until_next) == (phase, cycle_day, until_next)


def test_no_status_when_not_tracking_or_too_old():
    assert status(cycle(3, tracking=False), TODAY) is None
    assert status(cycle(3 * 28 + 1), TODAY) is None
    assert status(Cycle(tracking=True), TODAY) is None


def test_validation_rejects_future_dates_and_odd_lengths():
    with pytest.raises(ValidationError):
        Cycle(tracking=True, last_start=date.today() + timedelta(days=1))
    with pytest.raises(ValidationError):
        Cycle(length=15)
    with pytest.raises(ValidationError):
        Cycle(period_length=12)


def test_describe_gives_the_phase_never_dates():
    assert describe(status(cycle(1), TODAY)) == "on their period (about day 2)"
    assert describe(status(cycle(25), TODAY)) == "in the days before their period (expected in about 3 days)"
    assert describe(status(cycle(10), TODAY)) is None


def test_model_context_has_gender_and_phase_but_no_cycle_dates(tmp_path):
    memory = MemoryStore(tmp_path)
    start = TODAY - timedelta(days=25)
    memory.update_profile("u", {"gender": "female", "cycle": {"tracking": True, "last_start": start.isoformat(), "length": 28, "period_length": 5}})
    context = memory.context("u", TODAY)
    assert "Gender: female" in context
    assert "in the days before their period" in context
    assert "never rate risk lower because of it" in context
    assert start.isoformat() not in context and "28" not in context


def test_no_cycle_rules_when_not_in_a_relevant_phase(tmp_path):
    memory = MemoryStore(tmp_path)
    memory.update_profile("u", {"gender": "female", "cycle": {"tracking": True, "last_start": (TODAY - timedelta(days=10)).isoformat()}})
    context = memory.context("u", TODAY)
    assert "Period cycle" not in context and "Cycle:" not in context


def test_cycle_tracking_is_not_locked_to_gender(tmp_path):
    memory = MemoryStore(tmp_path)
    memory.update_profile("u", {"gender": "other", "cycle": {"tracking": True, "last_start": (TODAY - timedelta(days=1)).isoformat()}})
    assert "on their period" in memory.context("u", TODAY)


@pytest.mark.parametrize("text", ["It's probably just your hormones.", "That's just PMS.", "This could be PMDD."])
def test_steering_catches_dismissing_feelings_as_hormones(text):
    assert problems(text)


def test_steering_allows_gentle_cycle_framing():
    assert problems("Some people find the days before their period harder. Be gentle with yourself.") == []


def test_profile_api_saves_gender_and_cycle(tmp_path):
    def fake_agent(store, checkin):
        return AgentOutput(reflection="ok", risk_level="low", risk_reason="r")

    client = TestClient(create_app(run_agent=fake_agent, classify=None, memory=MemoryStore(tmp_path)))
    body = {"gender": "female", "cycle": {"tracking": True, "last_start": "2026-10-20", "length": 30, "period_length": 4}}
    saved = client.post("/api/profile", json=body).json()["profile"]
    assert saved["gender"] == "female" and saved["cycle"]["length"] == 30
    bad = client.post("/api/profile", json={"cycle": {"tracking": True, "length": 60}})
    assert bad.status_code == 422 and "21 to 45" in bad.json()["error"]


def test_gender_options_and_older_values(tmp_path):
    memory = MemoryStore(tmp_path)
    for value in ("male", "female", "other"):
        assert memory.update_profile("u", {"gender": value}).gender == value
    with pytest.raises(ValidationError):
        memory.update_profile("u", {"gender": "unknown"})
    # Profiles saved with the earlier options still load, as "other".
    (tmp_path / "profiles" / "old.json").write_text('{"gender": "non_binary"}')
    assert memory.profile("old").gender == "other"


def test_no_cycle_tracking_for_a_male_profile(tmp_path):
    memory = MemoryStore(tmp_path)
    start = (TODAY - timedelta(days=1)).isoformat()
    p = memory.update_profile("u", {"gender": "male", "cycle": {"tracking": True, "last_start": start}})
    assert p.cycle.tracking is False
    assert "Period cycle" not in memory.context("u", TODAY)
