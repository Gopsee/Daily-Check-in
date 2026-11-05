"""HTML mobile UI: a small Starlette app that serves the page and wraps submit_checkin()."""

import asyncio
import json
import logging
from collections.abc import Callable
from functools import partial
from datetime import date
from pathlib import Path

from pydantic import ValidationError
from starlette.applications import Starlette
from starlette.concurrency import run_in_threadpool
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse
from starlette.routing import Mount, Route, WebSocketRoute
from starlette.staticfiles import StaticFiles
from starlette.websockets import WebSocket, WebSocketDisconnect

from app import config
from app.agent.agent import classify_utterance, run_checkin_agent
from app.data import _hotlines, coping_exercises
from app.demo import SCENARIOS, USER_ID, seed_demo
from app.demo_profiles import DEMO_PROFILES, load_demo_profile
from app.health import BASELINE_DAYS, RECENT_DAYS, body_json, summarize
from app.memory import MemoryStore
from app.models import Checkin, CheckinResult, RiskLevel
from app.risk.engine import combine, evaluate
from app.service import AgentRunner, body_findings, submit_checkin
from app.store.memory import InMemoryStore
from app.voice.agent import build_voice_agent
from app.voice.session import Classifier, VoiceSession

log = logging.getLogger(__name__)

STATIC = Path(__file__).parent / "static"
MOOD_TAGS = ["anxious", "tired", "lonely", "stressed", "sad", "angry", "calm", "motivated", "grateful", "overwhelmed"]


def result_json(result: CheckinResult) -> dict:
    return {
        "checkin_id": result.checkin_id,
        "risk": result.final_risk.name.lower(),
        "show_crisis": result.show_crisis,
        "reasons": result.reasons,
        "findings": [{"source": f.source, "level": f.level.name.lower(), "reason": f.reason} for f in result.findings],
        "reflection": result.reflection,
        "coping": result.coping,
        "hotlines": result.hotlines,
        "ai_available": result.ai_available,
    }


def profile_json(memory: MemoryStore, user_id: str, store=None) -> dict:
    profile = memory.profile(user_id)
    out = {"profile": profile.editable(), "memories": [m.model_dump(mode="json") for m in profile.memories]}
    if store is not None:
        today = date.today()
        rows = store.get_health(user_id, RECENT_DAYS + BASELINE_DAYS, today)
        out["body"] = body_json(summarize(rows, today), frozenset(profile.health_context))
    return out


def profile_error(exc: Exception) -> str:
    if isinstance(exc, ValidationError):
        field = ".".join(str(p) for p in exc.errors()[0]["loc"]) or "profile"
        labels = {
            "health_context.0": "Pick from the listed options",
            "emergency_contact.phone": "Emergency contact phone: use digits, spaces, + ( ) or -",
            "cycle.last_start": "Last period start can't be in the future",
            "cycle.length": "Cycle length should be 21 to 45 days",
            "cycle.period_length": "Period length should be 2 to 8 days",
        }
        return labels.get(field, f"Check {field.replace('_', ' ')}")
    return "Couldn't read that profile"


def parse_checkin(body: dict) -> Checkin:
    return Checkin(
        user_id=USER_ID,
        mood=body.get("mood"),
        tags=[str(t) for t in body.get("tags") or []][:3],
        sleep_hours=body.get("sleep_hours"),
        note=(body.get("note") or "").strip() or None,
        phq2_score=body.get("phq2_score"),
        phq9_item9=body.get("phq9_item9"),
    )


def create_app(
    run_agent: AgentRunner | None = None,
    scenario: str = "decline",
    region: str = config.HOTLINE_REGION,
    voice_agent_factory: Callable = build_voice_agent,
    classify: Classifier | None = classify_utterance,
    memory: MemoryStore | None = None,
    demo_profile: str | None = None,
) -> Starlette:
    """classify=None turns off the Nova Pro risk check in voice chat; the phrase rules still run.

    memory holds the person's profile, remembered facts and recent conversation (Strands sessions).
    """
    store = InMemoryStore()
    seed_demo(store, scenario)
    memory = memory or MemoryStore(config.DATA_DIR)
    if run_agent is None:
        run_agent = partial(run_checkin_agent, memory=memory)
    if demo_profile:
        load_demo_profile(demo_profile, memory, store)
    index_html = (STATIC / "index.html").read_text()

    async def index(request: Request) -> HTMLResponse:
        # Hotlines are inlined into the page so the crisis screen renders with no network call.
        boot = {
            "hotlines": {k: v for k, v in _hotlines().items() if not k.startswith("_")},
            "region": region.upper(),
            "tags": MOOD_TAGS,
            "coping": coping_exercises(),
            "scenarios": list(SCENARIOS),
            # Inlined like the hotlines, so the crisis screen can offer the person's own contact offline.
            "profile": profile_json(memory, USER_ID, store),
            "demo_profiles": [{"key": k, "label": v["label"], "summary": v["summary"]} for k, v in DEMO_PROFILES.items()],
        }
        return HTMLResponse(index_html.replace("__BOOT__", json.dumps(boot).replace("</", "<\\/")))

    async def precheck(request: Request) -> JSONResponse:
        """Rules only, no LLM: lets the UI open the crisis screen before the agent replies."""
        try:
            checkin = parse_checkin(await request.json())
        except (ValidationError, ValueError) as exc:
            return JSONResponse({"error": str(exc)}, status_code=422)
        expected = frozenset(memory.profile(USER_ID).health_context)
        findings = evaluate(checkin, store.get_history(USER_ID, 7, checkin.day)) + body_findings(store, USER_ID, checkin.day, expected)
        level = combine(findings)
        return JSONResponse(
            {
                "risk": level.name.lower(),
                "show_crisis": level >= RiskLevel.HIGH,
                "reasons": [f.reason for f in findings if f.level > RiskLevel.LOW],
            }
        )

    async def create_checkin(request: Request) -> JSONResponse:
        try:
            checkin = parse_checkin(await request.json())
        except (ValidationError, ValueError) as exc:
            return JSONResponse({"error": str(exc)}, status_code=422)
        hotline_region = request.query_params.get("region", region)
        expected = frozenset(memory.profile(USER_ID).health_context)
        result = await run_in_threadpool(submit_checkin, store, checkin, run_agent, hotline_region, expected)
        return JSONResponse(result_json(result))

    async def history(request: Request) -> JSONResponse:
        try:
            days = min(max(int(request.query_params.get("days", 30)), 1), 90)
        except ValueError:
            return JSONResponse({"error": "days must be a number"}, status_code=422)
        by_day: dict[str, dict] = {}
        for c in store.get_history(USER_ID, days, date.today()):  # oldest first, so the latest check-in of a day wins
            findings = store.findings.get(c.id, [])
            by_day[c.day.isoformat()] = {
                "date": c.day.isoformat(),
                "mood": c.mood,
                "tags": c.tags,
                "sleep_hours": c.sleep_hours,
                "risk": combine(findings).name.lower() if findings else None,
            }
        return JSONResponse({"days": days, "checkins": list(by_day.values())})

    async def reset(request: Request) -> JSONResponse:
        scenario = request.query_params.get("scenario", "decline")
        if scenario not in SCENARIOS:
            return JSONResponse({"error": f"scenario must be one of {', '.join(SCENARIOS)}"}, status_code=422)
        seed_demo(store, scenario)
        return JSONResponse({"ok": True, "scenario": scenario})

    async def demo_profile_route(request: Request) -> JSONResponse:
        key = request.query_params.get("key", "")
        if key not in DEMO_PROFILES:
            return JSONResponse({"error": f"key must be one of {', '.join(DEMO_PROFILES)}"}, status_code=422)
        scenario = load_demo_profile(key, memory, store)
        return JSONResponse({**profile_json(memory, USER_ID, store), "scenario": scenario, "label": DEMO_PROFILES[key]["label"]})

    async def get_profile(request: Request) -> JSONResponse:
        return JSONResponse(profile_json(memory, USER_ID, store))

    async def save_profile(request: Request) -> JSONResponse:
        try:
            memory.update_profile(USER_ID, await request.json())
        except (ValidationError, ValueError) as exc:
            return JSONResponse({"error": profile_error(exc)}, status_code=422)
        return JSONResponse(profile_json(memory, USER_ID, store))

    async def forget_memory(request: Request) -> JSONResponse:
        try:
            index = int((await request.json()).get("index"))
        except (TypeError, ValueError):
            return JSONResponse({"error": "index must be a number"}, status_code=422)
        if not memory.forget(USER_ID, index):
            return JSONResponse({"error": "no such memory"}, status_code=404)
        return JSONResponse(profile_json(memory, USER_ID, store))

    async def forget_everything(request: Request) -> JSONResponse:
        memory.forget_everything(USER_ID)
        return JSONResponse(profile_json(memory, USER_ID, store))

    async def talk(websocket: WebSocket) -> None:
        """Voice chat: binary frames are 16 kHz PCM both ways; text frames are JSON control messages."""
        await websocket.accept()
        lock = asyncio.Lock()  # one writer at a time: audio, captions and risk alerts share the socket

        async def send_json(message: dict) -> None:
            async with lock:
                await websocket.send_json(message)

        async def send_audio(pcm: bytes) -> None:
            async with lock:
                await websocket.send_bytes(pcm)

        try:
            session = VoiceSession(voice_agent_factory(store, USER_ID, date.today(), memory=memory), send_json, send_audio, classify)
            await session.start()
        except Exception as exc:
            log.warning("Voice chat could not start (%s)", type(exc).__name__)
            await send_json({"type": "error", "message": "The voice companion isn't available right now. You can still type your check-in."})
            await websocket.close()
            return

        pump = asyncio.create_task(session.pump())
        try:
            while True:
                message = await websocket.receive()
                if message["type"] == "websocket.disconnect":
                    break
                if message.get("bytes"):
                    await session.on_audio(message["bytes"])
                elif message.get("text"):
                    data = json.loads(message["text"])
                    if data.get("type") == "text":
                        await session.on_text(str(data.get("text", "")))
                    elif data.get("type") == "end":
                        break
        except (WebSocketDisconnect, json.JSONDecodeError):
            pass
        finally:
            pump.cancel()
            await asyncio.gather(pump, return_exceptions=True)
            await session.stop()
            try:
                await websocket.close()
            except (RuntimeError, WebSocketDisconnect):
                pass  # the browser already closed it

    return Starlette(
        routes=[
            WebSocketRoute("/ws/talk", talk),
            Route("/", index),
            Route("/api/checkins/precheck", precheck, methods=["POST"]),
            Route("/api/checkins", create_checkin, methods=["POST"]),
            Route("/api/history", history),
            Route("/api/demo/reset", reset, methods=["POST"]),
            Route("/api/demo/profile", demo_profile_route, methods=["POST"]),
            Route("/api/profile", get_profile),
            Route("/api/profile", save_profile, methods=["POST"]),
            Route("/api/memories/forget", forget_memory, methods=["POST"]),
            Route("/api/memories/forget-all", forget_everything, methods=["POST"]),
            Mount("/static", StaticFiles(directory=STATIC), name="static"),
        ]
    )
