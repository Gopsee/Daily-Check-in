from datetime import date, timedelta

import pytest
from starlette.testclient import TestClient

from app.cycle import status
from app.demo import USER_ID
from app.demo_profiles import DEMO_PROFILES, load_demo_profile
from app.memory import MemoryStore
from app.models import AgentOutput
from app.store.memory import InMemoryStore
from app.web.server import create_app

TODAY = date(2026, 11, 5)


def test_five_people_mixing_gender_and_age():
    profiles = [d["profile"] for d in DEMO_PROFILES.values()]
    assert len(profiles) == 5
    assert {p["gender"] for p in profiles} == {"male", "female"}
    assert {p["age_group"] for p in profiles} == {"teen", "young_adult", "adult", "older_adult"}


@pytest.mark.parametrize("key", DEMO_PROFILES)
def test_each_person_loads_completely(key, tmp_path):
    memory, store = MemoryStore(tmp_path), InMemoryStore()
    scenario = load_demo_profile(key, memory, store, TODAY)
    p = memory.profile(USER_ID)
    demo = DEMO_PROFILES[key]
    assert p.preferred_name == demo["profile"]["preferred_name"]
    assert p.emergency_contact.phone == demo["profile"]["emergency_contact"]["phone"]
    assert "555-01" in p.emergency_contact.phone  # fictional range only
    # every memory passes the same filters as an agent-saved one
    assert [m.text for m in p.memories] == [text for _, text in demo["memories"]]
    assert scenario == demo["scenario"]
    assert bool(store.get_history(USER_ID, 30, TODAY)) == (scenario != "empty")


def test_maya_is_in_the_days_before_her_period(tmp_path):
    memory = MemoryStore(tmp_path)
    load_demo_profile("maya", memory, InMemoryStore(), TODAY)
    assert status(memory.profile(USER_ID).cycle, TODAY).phase == "premenstrual"


def test_switching_people_replaces_everything(tmp_path):
    memory, store = MemoryStore(tmp_path), InMemoryStore()
    load_demo_profile("dave", memory, store, TODAY)
    memory.session_manager(USER_ID)
    session_dir = tmp_path / "sessions" / f"session_{memory.session_id(USER_ID)}"
    assert session_dir.exists()
    load_demo_profile("robert", memory, store, TODAY)
    p = memory.profile(USER_ID)
    assert p.preferred_name == "Robert" and p.gender == "male" and not p.cycle.tracking
    assert all("Dave" not in m.text for m in p.memories)
    assert not session_dir.exists()  # Dave's conversation is gone
    assert store.get_history(USER_ID, 30, TODAY) == []


def test_demo_profile_endpoint(tmp_path):
    def fake_agent(store, checkin):
        return AgentOutput(reflection="ok", risk_level="low", risk_reason="r")

    client = TestClient(create_app(run_agent=fake_agent, classify=None, memory=MemoryStore(tmp_path)))
    assert '"demo_profiles"' in client.get("/").text
    loaded = client.post("/api/demo/profile?key=priya").json()
    assert loaded["profile"]["preferred_name"] == "Priya" and loaded["label"] == "Priya, 34"
    assert client.post("/api/demo/profile?key=nobody").status_code == 422


def test_start_up_with_a_demo_person(tmp_path):
    memory = MemoryStore(tmp_path)
    create_app(run_agent=lambda s, c: None, classify=None, memory=memory, demo_profile="jordan")
    assert memory.profile(USER_ID).preferred_name == "Jordan"


def test_cycle_start_is_relative_to_today(tmp_path):
    memory = MemoryStore(tmp_path)
    load_demo_profile("maya", memory, InMemoryStore(), TODAY)
    assert memory.profile(USER_ID).cycle.last_start == TODAY - timedelta(days=24)
