from datetime import date, timedelta

import pytest
from starlette.testclient import TestClient

from app.agent.steering import problems
from app.agent.tools import make_tools
from app.demo import USER_ID
from app.demo_profiles import load_demo_profile
from app.health import DailyHealth, body_json, body_layer, signals_for_agent, simulate, summarize
from app.memory import MemoryStore
from app.models import AgentOutput, Checkin, RiskLevel
from app.service import submit_checkin
from app.store.memory import InMemoryStore
from app.web.server import create_app

TODAY = date(2026, 11, 5)
USUAL = {"sleep": 8.0, "steps": 9000, "exercise": 40, "rhr": 62, "hrv": 60}


def days(sleep_recent=8.0, steps_recent=9000, recent_days=7, missing=0.0, **usual):
    spec = {"usual": {**USUAL, **usual}, "recent": {**USUAL, "sleep": sleep_recent, "steps": steps_recent}, "recent_days": recent_days, "missing": missing}
    return simulate(spec, TODAY, seed=1)


def findings(rows, expected=frozenset()):
    return body_layer(summarize(rows, TODAY), expected)


def test_steady_week_flags_nothing():
    assert findings(days()) == []


def test_short_nights_or_a_sleep_drop_are_flagged():
    reasons = [f.reason for f in findings(days(sleep_recent=4.4))]
    assert len(reasons) == 1 and ("under 5 hours" in reasons[0] or "down from your usual" in reasons[0])


def test_a_big_drop_in_steps_is_flagged_against_their_own_usual():
    (finding,) = findings(days(steps_recent=3500))
    assert "Steps down" in finding.reason and finding.source == "body"


def test_low_steps_are_fine_when_that_is_their_usual():
    assert findings(days(steps_recent=2500, steps=2600)) == []


def test_body_signals_never_go_above_elevated():
    assert all(f.level == RiskLevel.ELEVATED for f in findings(days(sleep_recent=3.0, steps_recent=500)))


def test_expected_changes_are_not_warning_signs():
    rows = days(sleep_recent=4.0, steps_recent=2000)
    assert findings(rows, frozenset({"new_baby"})) == []
    only_steps = findings(rows, frozenset({"shift_work"}))
    assert [f.reason.split()[0] for f in only_steps] == ["Steps"]


def test_missing_days_are_skipped_not_read_as_inactivity():
    rows = [r for r in days(steps_recent=9000) if (TODAY - r.day).days > 3]  # watch off for the last 4 days
    summary = summarize(rows, TODAY)
    assert summary.trends["steps"].recent_days == 3 and not summary.trends["steps"].enough
    assert findings(rows) == []


def test_heart_rate_never_produces_a_finding():
    rows = [r.model_copy(update={"resting_hr": 95, "hrv_ms": 15}) if (TODAY - r.day).days < 7 else r for r in days()]
    assert findings(rows) == []


def test_body_signals_can_raise_risk_but_never_lower_it():
    store = InMemoryStore()
    store.save_health("u", days(sleep_recent=4.0, steps_recent=2500))
    fake = lambda s, c: AgentOutput(reflection="ok", risk_level="low", risk_reason="r")
    calm = submit_checkin(store, Checkin(user_id="u", mood=4, day=TODAY), run_agent=fake)
    assert calm.final_risk == RiskLevel.ELEVATED and not calm.show_crisis
    assert any(f.source == "body" for f in calm.findings)
    crisis = submit_checkin(store, Checkin(user_id="u", mood=1, note="I want to kill myself", day=TODAY), run_agent=fake)
    assert crisis.final_risk == RiskLevel.IMMINENT


def test_the_agent_tool_gets_weekly_summaries_not_raw_days():
    store = InMemoryStore()
    store.save_health("u", days(sleep_recent=5.0))
    tool = next(t for t in make_tools(store, "u", TODAY, frozenset({"travel"})) if t.tool_name == "get_body_signals")
    out = tool()
    assert out["available"] and set(out["sleep_hours"]) == {"this_week", "usual", "unit"}
    assert out["expected_because_of"] == ["travel"]
    assert "day" not in str(out) or "a day" in str(out)  # no per-day rows or dates
    assert TODAY.isoformat() not in str(out)


def test_no_data_means_no_signals():
    assert signals_for_agent(summarize([], TODAY))["available"] is False
    assert body_json(summarize([], TODAY))["available"] is False


@pytest.mark.parametrize("text", ["Your heart rate shows you're anxious.", "Your HRV suggests stress.", "This could be sleep apnea."])
def test_steering_catches_medical_claims(text):
    assert "medical_claim" in problems(text)


def test_steering_allows_gentle_mentions():
    assert problems("You've been sleeping a lot less this week, which can make everything feel heavier.") == []


@pytest.mark.parametrize(
    "key, noticed",
    [("dave", True), ("maya", False), ("jordan", False), ("priya", False), ("robert", True)],
)
def test_demo_people_tell_the_intended_story(key, noticed, tmp_path):
    memory, store = MemoryStore(tmp_path), InMemoryStore()
    load_demo_profile(key, memory, store, TODAY)
    expected = frozenset(memory.profile(USER_ID).health_context)
    view = body_json(summarize(store.get_health(USER_ID, 35, TODAY), TODAY), expected)
    assert view["available"] and bool(view["noticed"]) == noticed
    if key == "priya":
        assert view["expected"] == ["a new baby"]


def test_profile_api_carries_the_body_view(tmp_path):
    fake = lambda s, c: AgentOutput(reflection="ok", risk_level="low", risk_reason="r")
    client = TestClient(create_app(run_agent=fake, classify=None, memory=MemoryStore(tmp_path)))
    body = client.post("/api/demo/profile?key=dave").json()["body"]
    assert body["available"] and body["noticed"] and body["last_night_sleep"] is not None
    saved = client.post("/api/profile", json={"preferred_name": "Dave", "health_context": ["travel"]}).json()
    assert saved["body"]["noticed"] == []  # travel explains both the sleep and the steps
    assert client.post("/api/profile", json={"health_context": ["moon_phase"]}).status_code == 422


def test_sleep_rows_are_one_per_day():
    store = InMemoryStore()
    store.save_health("u", [DailyHealth(day=TODAY, sleep_hours=6.0), DailyHealth(day=TODAY, sleep_hours=7.5)])
    assert [r.sleep_hours for r in store.get_health("u", 35, TODAY)] == [7.5]
