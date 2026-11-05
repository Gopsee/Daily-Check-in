from datetime import date

from app import config
from app.agent.prompts import VOICE_PROMPT
from app.agent.tools import make_tools
from app.store.base import Store
from app.voice.session import INPUT_RATE, OUTPUT_RATE


def build_voice_agent(store: Store, user_id: str, today: date):
    """A fresh Nova Sonic agent per conversation, with the same user-bound tools as the check-in agent."""
    from strands.bidi import BidiAgent
    from strands.bidi.models.bedrock import BedrockNovaSonicModel

    model = BedrockNovaSonicModel(
        model_id=config.VOICE_MODEL_ID,
        region=config.VOICE_REGION,
        voice=config.VOICE_ID,
        audio={"input": {"sample_rate": INPUT_RATE}, "output": {"sample_rate": OUTPUT_RATE}},
    )
    return BidiAgent(model=model, system_prompt=VOICE_PROMPT, tools=make_tools(store, user_id, today))
