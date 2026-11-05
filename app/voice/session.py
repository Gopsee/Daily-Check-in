"""Bridges one browser connection to one Nova Sonic voice agent, with a live risk check on every line.

The voice model speaks its replies directly, so nothing can filter its audio before it plays.
Safety therefore works on what the person says: each finished line goes through the same
English phrase rules as a check-in at once, and through a Nova Pro risk check in the background.
The higher level wins, and high or imminent opens the crisis screen.
"""

import asyncio
import base64
import logging
from collections.abc import Awaitable, Callable

from app.agent.prompts import VOICE_CRISIS_NOTE, VOICE_GREETING
from app.models import RiskFinding, RiskLevel, UtteranceRisk
from app.risk.engine import combine, keyword_layer

log = logging.getLogger(__name__)

INPUT_RATE = 16000  # browser → Nova Sonic, 16-bit mono PCM
OUTPUT_RATE = 24000  # Nova Sonic → browser, 16-bit mono PCM
CONTEXT_LINES = 5  # earlier lines given to the risk check
_LEAD_IN = bytes(INPUT_RATE * 2 * 3 // 10)  # 300 ms of silence opens the audio stream before the greeting

SendJSON = Callable[[dict], Awaitable[None]]
SendAudio = Callable[[bytes], Awaitable[None]]
Classifier = Callable[[str, list[str]], UtteranceRisk]


class VoiceSession:
    def __init__(self, agent, send_json: SendJSON, send_audio: SendAudio, classify: Classifier | None) -> None:
        self.agent = agent
        self.send_json = send_json
        self.send_audio = send_audio
        self.classify = classify
        self.user_lines: list[str] = []
        self.risk = RiskLevel.LOW
        self._checks: set[asyncio.Task] = set()

    async def start(self) -> None:
        from strands.bidi.types.media import AudioDelta

        await self.agent.start()
        await self.agent.send(AudioDelta(format="pcm", source={"bytes": _LEAD_IN}))
        await self.agent.send(VOICE_GREETING)
        await self.send_json({"type": "ready", "output_rate": OUTPUT_RATE, "input_rate": INPUT_RATE})

    async def stop(self) -> None:
        await self.drain()
        await self.agent.stop()

    async def drain(self) -> None:
        """Wait for background risk checks still running."""
        if self._checks:
            await asyncio.gather(*self._checks, return_exceptions=True)

    async def on_audio(self, pcm: bytes) -> None:
        from strands.bidi.types.media import AudioDelta

        await self.agent.send(AudioDelta(format="pcm", source={"bytes": pcm}))

    async def on_text(self, text: str) -> None:
        """A line the person typed instead of speaking."""
        text = text.strip()[:1000]
        if not text:
            return
        await self._heard(text)
        await self.agent.send(text)

    async def pump(self) -> None:
        """Forward the agent's events to the browser until the connection ends."""
        try:
            async for event in self.agent.receive():
                await self.on_event(event)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            log.warning("Voice agent stopped (%s)", type(exc).__name__)
            await self.send_json({"type": "error", "message": "The voice connection dropped. Start again to keep talking."})

    async def on_event(self, event: dict) -> None:
        kind = event.get("type")
        if kind == "bidi_audio_delta":
            await self.send_audio(base64.b64decode(event["audio"]))
        elif kind == "bidi_transcript_delta":
            await self.send_json({"type": "caption", "role": event["role"], "id": event["content_id"], "text": event["delta"]})
        elif kind == "bidi_transcript_block":
            text = event["transcript"].strip()
            await self.send_json({"type": "line", "role": event["role"], "id": event["content_id"], "text": text})
            if event["role"] == "user" and text:
                await self._heard(text)
        elif kind == "bidi_barge_in":
            await self.send_json({"type": "barge_in"})
        elif kind == "bidi_response_stop":
            await self.send_json({"type": "turn_end"})

    async def _heard(self, text: str) -> None:
        earlier = self.user_lines[-CONTEXT_LINES:]
        self.user_lines.append(text)
        await self._raise_risk(keyword_layer(text))
        if self.classify is not None:
            task = asyncio.create_task(self._check(text, earlier))
            self._checks.add(task)
            task.add_done_callback(self._checks.discard)

    async def _check(self, text: str, earlier: list[str]) -> None:
        try:
            result = await asyncio.to_thread(self.classify, text, earlier)
        except Exception as exc:
            # The phrase rules already ran, and the whole conversation is checked again if it's
            # added to the check-in, where the full fail-safe applies.
            log.warning("Voice risk check failed (%s)", type(exc).__name__)
            return
        await self._raise_risk([RiskFinding(source="llm", level=RiskLevel.parse(result.risk_level), reason=result.risk_reason)])

    async def _raise_risk(self, findings: list[RiskFinding]) -> None:
        """Tell the browser only when the level goes up; it never goes down within a conversation."""
        level = combine(findings)
        if level <= self.risk:
            return
        self.risk = level
        await self.send_json(
            {
                "type": "risk",
                "level": level.name.lower(),
                "show_crisis": level >= RiskLevel.HIGH,
                "reasons": [f.reason for f in findings if f.level > RiskLevel.LOW],
            }
        )
        if level >= RiskLevel.HIGH:
            await self.agent.send(VOICE_CRISIS_NOTE)
