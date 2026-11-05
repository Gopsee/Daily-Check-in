import logging

from botocore.config import Config
from strands import Agent
from strands.agent.conversation_manager import SlidingWindowConversationManager
from strands.models import BedrockModel

from app import config
from app.agent.guard import OutputGuard
from app.agent.prompts import MEMORY_RULES, SYSTEM_PROMPT, UTTERANCE_PROMPT, format_checkin, format_utterance
from app.agent.steering import ReplySteering
from app.agent.tools import make_tools
from app.memory import MemoryStore
from app.models import AgentOutput, Checkin, UtteranceRisk
from app.service import FALLBACK_REFLECTIONS
from app.store.base import Store

log = logging.getLogger(__name__)


def bedrock_model(max_tokens: int = 1024) -> BedrockModel:
    return BedrockModel(
        model_id=config.MODEL_ID,
        region_name=config.AWS_REGION,
        boto_client_config=Config(
            connect_timeout=5, read_timeout=config.MODEL_TIMEOUT_S, retries={"max_attempts": 2}
        ),
        temperature=0.3,
        max_tokens=max_tokens,
    )


def build_agent(
    store: Store, checkin: Checkin, steering: ReplySteering | None = None, memory: MemoryStore | None = None
) -> Agent:
    # A fresh agent per check-in, bound to one user. Without memory it starts empty every time;
    # with memory, a Strands session restores this person's recent conversation, trimmed to a window.
    # Steering asks for one rewrite of an unsupportive reply; the guard is the hard backstop.
    expected = frozenset(memory.profile(checkin.user_id).health_context) if memory else frozenset()
    tools = make_tools(store, checkin.user_id, checkin.day, expected)
    system_prompt = SYSTEM_PROMPT
    session: dict = {}
    if memory is not None:
        tools.append(memory.remember_tool(checkin.user_id, checkin.day))
        system_prompt += MEMORY_RULES + memory.context(checkin.user_id, checkin.day)
        session = {
            "agent_id": "checkin",
            "session_manager": memory.session_manager(checkin.user_id),
            "conversation_manager": SlidingWindowConversationManager(window_size=config.MEMORY_WINDOW),
        }
    return Agent(
        model=bedrock_model(),
        system_prompt=system_prompt,
        tools=tools,
        plugins=[steering or ReplySteering()],
        hooks=[OutputGuard(replacement=FALLBACK_REFLECTIONS[checkin.mood])],
        callback_handler=None,
        **session,
    )


def run_checkin_agent(store: Store, checkin: Checkin, memory: MemoryStore | None = None) -> AgentOutput:
    """Run the check-in agent on Nova Pro. Raises on failure; the service applies the fail-safe."""
    try:
        steering = ReplySteering()
        agent = build_agent(store, checkin, steering, memory)
        result = agent(format_checkin(checkin), structured_output_model=AgentOutput)
        output = result.structured_output
        if not isinstance(output, AgentOutput):
            raise ValueError("Agent returned no structured output")
        return steering.keep_risk(output)
    except Exception as exc:
        log.warning("Model %s failed (%s)", config.MODEL_ID, type(exc).__name__)
        raise


def classify_utterance(text: str, earlier: list[str]) -> UtteranceRisk:
    """Live risk check for one line spoken in the voice chat. Raises on failure."""
    agent = Agent(model=bedrock_model(max_tokens=256), system_prompt=UTTERANCE_PROMPT, callback_handler=None)
    result = agent(format_utterance(text, earlier), structured_output_model=UtteranceRisk)
    if not isinstance(result.structured_output, UtteranceRisk):
        raise ValueError("Risk check returned no structured output")
    return result.structured_output
