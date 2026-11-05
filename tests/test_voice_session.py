import asyncio
import base64

from app.agent.prompts import VOICE_CRISIS_NOTE, VOICE_GREETING
from app.models import UtteranceRisk
from app.voice.session import VoiceSession


class FakeAgent:
    def __init__(self, events=()):
        self.events = list(events)
        self.sent = []
        self.started = self.stopped = False

    async def start(self):
        self.started = True

    async def send(self, data):
        self.sent.append(data)

    async def receive(self):
        for event in self.events:
            yield event

    async def stop(self):
        self.stopped = True

    @property
    def texts(self):
        return [s for s in self.sent if isinstance(s, str)]


def user_line(text):
    return {"type": "bidi_transcript_block", "role": "user", "content_id": "u1", "transcript": text}


def run(agent, classify=None, typed=None):
    """Start a session, replay the agent's events, then return what reached the browser."""
    sent_json, sent_audio = [], []

    async def send_json(message):
        sent_json.append(message)

    async def send_audio(pcm):
        sent_audio.append(pcm)

    async def main():
        session = VoiceSession(agent, send_json, send_audio, classify)
        await session.start()
        if typed:
            await session.on_text(typed)
        await session.pump()
        await session.stop()

    asyncio.run(main())
    return sent_json, sent_audio


def risks(sent_json):
    return [m for m in sent_json if m["type"] == "risk"]


def test_greets_on_start_and_stops_cleanly():
    agent = FakeAgent()
    sent_json, _ = run(agent)
    assert agent.started and agent.stopped
    assert agent.texts == [VOICE_GREETING]
    assert sent_json[0]["type"] == "ready"


def test_explicit_phrase_opens_crisis_and_tells_the_voice_agent():
    agent = FakeAgent([user_line("Honestly I want to kill myself")])
    sent_json, _ = run(agent)
    [risk] = risks(sent_json)
    assert risk["show_crisis"] and risk["level"] == "imminent"
    assert VOICE_CRISIS_NOTE in agent.texts


def test_risk_check_catches_indirect_wording_the_rules_miss():
    def classify(text, earlier):
        return UtteranceRisk(risk_level="high", risk_reason="Talks about giving belongings away")

    agent = FakeAgent([user_line("I've started giving my things away")])
    sent_json, _ = run(agent, classify)
    [risk] = risks(sent_json)
    assert risk["show_crisis"] and risk["reasons"] == ["Talks about giving belongings away"]


def test_failed_risk_check_does_not_break_the_conversation():
    def classify(text, earlier):
        raise TimeoutError("bedrock timed out")

    agent = FakeAgent([user_line("Work was fine today"), {"type": "bidi_response_stop", "response_id": "r1"}])
    sent_json, _ = run(agent, classify)
    assert risks(sent_json) == []
    assert sent_json[-1] == {"type": "turn_end"}


def test_risk_only_goes_up_within_a_conversation():
    levels = iter(["elevated", "low", "elevated"])

    def classify(text, earlier):
        return UtteranceRisk(risk_level=next(levels), risk_reason="r")

    agent = FakeAgent([user_line("I feel stuck"), user_line("It's fine"), user_line("Still stuck")])
    sent_json, _ = run(agent, classify)
    assert [r["level"] for r in risks(sent_json)] == ["elevated"]


def test_typed_text_is_risk_checked_and_sent_to_the_agent():
    agent = FakeAgent()
    sent_json, _ = run(agent, typed="I want to end my life")
    assert "I want to end my life" in agent.texts
    assert risks(sent_json)[0]["show_crisis"]


def test_audio_reaches_the_browser_as_raw_pcm():
    pcm = b"\x01\x02\x03\x04"
    agent = FakeAgent([{"type": "bidi_audio_delta", "audio": base64.b64encode(pcm).decode(), "content_id": "a1"}])
    _, sent_audio = run(agent)
    assert sent_audio == [pcm]


def test_risk_check_gets_earlier_lines_as_context():
    seen = []

    def classify(text, earlier):
        seen.append((text, earlier))
        return UtteranceRisk(risk_level="low", risk_reason="r")

    agent = FakeAgent([user_line("First"), user_line("Second")])
    run(agent, classify)
    assert sorted(seen) == [("First", []), ("Second", ["First"])]
