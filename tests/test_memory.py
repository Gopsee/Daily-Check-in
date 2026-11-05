from datetime import date

import pytest
from pydantic import ValidationError
from starlette.testclient import TestClient

from app.agent.agent import build_agent
from app.memory import MAX_MEMORIES, MemoryStore, recent
from app.models import AgentOutput, Checkin
from app.store.memory import InMemoryStore
from app.web.server import create_app

TODAY = date(2026, 11, 5)


@pytest.fixture
def memory(tmp_path):
    return MemoryStore(tmp_path)


def test_profile_round_trip_and_list_cleanup(memory):
    memory.update_profile("u", {
        "preferred_name": "Dave",
        "age_group": "teen",
        "what_helps": [" music ", "Music", "walks", ""],
        "trusted_people": ["Sam", "Mom"],
        "emergency_contact": {"name": "Mom", "phone": "+1 (555) 010-2030"},
    })
    p = memory.profile("u")
    assert (p.preferred_name, p.age_group, p.what_helps, p.trusted_people) == ("Dave", "teen", ["music", "walks"], ["Sam", "Mom"])
    assert p.emergency_contact.phone == "+1 (555) 010-2030"


def test_rejects_a_phone_that_is_not_a_phone(memory):
    with pytest.raises(ValidationError):
        memory.update_profile("u", {"emergency_contact": {"name": "Mom", "phone": "call me maybe"}})


def test_empty_emergency_contact_is_cleared(memory):
    memory.update_profile("u", {"emergency_contact": {"name": "", "phone": ""}})
    assert memory.profile("u").emergency_contact is None


def test_saving_the_profile_keeps_memories(memory):
    memory.remember("u", "Sam is their closest friend", TODAY)
    memory.update_profile("u", {"preferred_name": "Dave"})
    assert [m.text for m in memory.profile("u").memories] == ["Sam is their closest friend"]


def test_remember_saves_and_dedupes(memory):
    assert memory.remember("u", "Exams start in December", TODAY) == "Saved."
    assert memory.remember("u", "exams start in december", TODAY) == "Already remembered."
    assert len(memory.profile("u").memories) == 1


@pytest.mark.parametrize(
    "fact",
    [
        "Mom's number is 555 010 2030",
        "Said they want to kill themselves",
        "Thinks everyone would be better off without them",
        "Wishes they wasn't around anymore",
        "Has been hurting themselves",
    ],
)
def test_never_remembers_phone_numbers_or_crisis_details(memory, fact):
    assert memory.remember("u", fact, TODAY).startswith("Not saved")
    assert memory.profile("u").memories == []


def test_keeps_only_the_newest_memories(memory):
    for i in range(MAX_MEMORIES + 3):
        memory.remember("u", f"Fact number {chr(65 + i)}", TODAY)
    texts = [m.text for m in memory.profile("u").memories]
    assert len(texts) == MAX_MEMORIES and texts[-1] == f"Fact number {chr(65 + MAX_MEMORIES + 2)}"


def test_remember_tool_saves_at_most_two_facts_per_conversation(memory):
    remember = memory.remember_tool("u", TODAY)
    results = [remember(fact=f) for f in ["Sam is a friend", "Likes music", "Has a dog"]]
    assert results[:2] == ["Saved.", "Saved."] and results[2].startswith("Not saved")


def test_forget_one_and_forget_everything(memory, tmp_path):
    memory.remember("u", "Sam is a friend", TODAY)
    memory.remember("u", "Likes music", TODAY)
    assert memory.forget("u", 0) and [m.text for m in memory.profile("u").memories] == ["Likes music"]
    assert not memory.forget("u", 5)
    memory.session_manager("u")
    session_dir = tmp_path / "sessions" / f"session_{memory.session_id('u')}"
    assert session_dir.exists()
    memory.forget_everything("u")
    assert memory.profile("u").memories == [] and not session_dir.exists()


def test_context_for_the_model_never_includes_the_emergency_contact(memory):
    memory.update_profile("u", {
        "preferred_name": "Dave", "trusted_people": ["Sam"],
        "emergency_contact": {"name": "Aunt Priya", "phone": "555 010 2030"},
    })
    memory.remember("u", "Exams start in December", TODAY)
    context = memory.context("u", TODAY)
    assert "Dave" in context and "Sam" in context and "Exams start in December" in context
    assert "Priya" not in context and "555" not in context


def test_recent_trims_to_a_clean_starting_point():
    messages = [
        {"role": "user", "content": [{"text": "day 1"}]},
        {"role": "assistant", "content": [{"toolUse": {"name": "x"}}]},
        {"role": "user", "content": [{"toolResult": {}}]},
        {"role": "assistant", "content": [{"text": "reply 1"}]},
        {"role": "user", "content": [{"text": "day 2"}]},
        {"role": "assistant", "content": [{"text": "reply 2"}]},
    ]
    assert recent(messages, 4) == messages[-2:]
    assert recent(messages, 0) == []


def test_check_in_agent_uses_a_session_only_with_memory(memory):
    checkin = Checkin(user_id="u", mood=3, note="ok", day=TODAY)
    memory.update_profile("u", {"preferred_name": "Dave"})
    with_memory = build_agent(InMemoryStore(), checkin, memory=memory)
    assert with_memory.agent_id == "checkin"
    assert "Dave" in with_memory.system_prompt and "remember" in with_memory.tool_names
    without = build_agent(InMemoryStore(), checkin)
    assert "remember" not in without.tool_names and "<profile>" not in without.system_prompt


def test_profile_api_and_crisis_contact_in_the_page(memory):
    def fake_agent(store, checkin):
        return AgentOutput(reflection="ok", risk_level="low", risk_reason="r")

    client = TestClient(create_app(run_agent=fake_agent, classify=None, memory=memory))
    saved = client.post("/api/profile", json={
        "preferred_name": "Dave", "age_group": "teen", "what_helps": ["music"], "trusted_people": ["Sam"],
        "emergency_contact": {"name": "Mom", "phone": "555 010 2030"},
    })
    assert saved.status_code == 200 and saved.json()["profile"]["preferred_name"] == "Dave"
    assert "555 010 2030" in client.get("/").text  # inlined so the crisis screen works offline
    bad = client.post("/api/profile", json={"emergency_contact": {"name": "Mom", "phone": "nope"}})
    assert bad.status_code == 422 and "phone" in bad.json()["error"]
    memory.remember("demo-user", "Sam is a friend", TODAY)
    assert client.post("/api/memories/forget", json={"index": 0}).json()["memories"] == []
    assert client.post("/api/memories/forget-all").status_code == 200
