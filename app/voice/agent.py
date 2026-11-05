from datetime import date

from app import config
from app.agent.prompts import VOICE_MEMORY_RULES, VOICE_PROMPT
from app.agent.tools import make_tools
from app.memory import MemoryStore, recent
from app.store.base import Store
from app.voice.session import INPUT_RATE, OUTPUT_RATE


def build_voice_agent(store: Store, user_id: str, today: date, memory: MemoryStore | None = None):
    """A fresh Nova Sonic agent per conversation, with the same user-bound tools as the check-in agent.

    With memory, it shares the person's profile and remembered facts, and a Strands session restores
    its own recent voice conversation, trimmed before the stream starts.
    """
    from strands.bidi import BidiAgent
    from strands.bidi.models.bedrock import BedrockNovaSonicModel

    model = BedrockNovaSonicModel(
        model_id=config.VOICE_MODEL_ID,
        region=config.VOICE_REGION,
        voice=config.VOICE_ID,
        audio={"input": {"sample_rate": INPUT_RATE}, "output": {"sample_rate": OUTPUT_RATE}},
    )
    expected = frozenset(memory.profile(user_id).health_context) if memory else frozenset()
    tools = make_tools(store, user_id, today, expected)
    if memory is None:
        return BidiAgent(model=model, system_prompt=VOICE_PROMPT, tools=tools)
    agent = BidiAgent(
        model=model,
        system_prompt=VOICE_PROMPT + VOICE_MEMORY_RULES + memory.context(user_id, today),
        tools=tools + [memory.remember_tool(user_id, today)],
        agent_id="voice",
        session_manager=memory.session_manager(user_id),
    )
    # BidiAgent has no conversation manager, so keep only the recent part of the restored history.
    agent.messages = recent(agent.messages, config.VOICE_MEMORY_WINDOW)
    return agent
