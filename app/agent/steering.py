"""Reply steering: asks the agent to rewrite a reflection that diagnoses, prescribes or fixes.

Strands steering runs inside the agent loop. After each model call this handler reads the
draft reflection. If the draft names a diagnosis, mentions medication or a phone number,
tells the person to see a professional, or offers a quick fix, it discards the draft and
tells the model what to change. The model gets one rewrite. If that still fails, the output
guard hook replaces the reflection with a standard message, so steering improves replies
without having to be perfect.
"""

import logging
import re
from typing import Any

from strands.vended_plugins.steering import Guide, ModelSteeringAction, Proceed, SteeringHandler

from app.agent.guard import violations
from app.models import AgentOutput, RiskLevel

log = logging.getLogger(__name__)

MAX_REWRITES = 1

# Softer than the guard's checks: these only ask for a rewrite, they never replace a reply.
STEER_CHECKS: dict[str, re.Pattern] = {
    "treatment_advice": re.compile(
        r"\b(?:you should|you need to|you must|i recommend|i suggest|consider|try)\s+(?:to\s+)?"
        r"(?:see|seeing|talk to|talking to|book|get|getting|start|starting|go to|going to)\s+"
        r"(?:a |an |some |into )?(?:therapist|therapy|psychiatrist|psychologist|doctor|gp|"
        r"counsell?or|counsell?ing|treatment|medication|professional help|evaluation|assessment|diagnosis)\b"
        r"|\b(?:important|a good idea|best|helpful|a good step) to (?:talk to|see|speak (?:to|with)|reach out to|consult)\s+"
        r"(?:a |an )?(?:mental health )?(?:professional|therapist|psychiatrist|psychologist|doctor|counsell?or)\b"
        r"|\b(?:talk to|speak with|see|consult) a (?:mental health )?professional\b"
    ),
    "diagnosis_hint": re.compile(
        r"\b(?:might|may|could) be (?:depression|an anxiety disorder|bipolar|ptsd|ocd|adhd|insomnia)\b"
        r"|\b(?:signs|symptoms) of (?:depression|anxiety|bipolar|ptsd|ocd|adhd|insomnia)\b"
        r"|\bsounds like (?:depression|bipolar|ptsd|ocd|adhd)\b"
    ),
    "quick_fix": re.compile(
        r"\bthe (?:solution|fix|answer|cure) (?:is|would be)\b"
        r"|\bjust (?:stop|get over|snap out|cheer up|think positive|ignore (?:it|them))\b"
        r"|\bsnap out of\b|\bget over it\b|\bstop (?:worrying|being sad|overthinking)\b|\bthink positive\b"
    ),
}

GUIDANCE = {
    "diagnosis": "Do not name, suggest or hint at any diagnosis or clinical label.",
    "diagnosis_hint": "Do not suggest what condition they might have, even as a possibility or by repeating their question.",
    "medication": "Do not mention medication, supplements or doses.",
    "phone_number": "Do not write any phone number; the app shows verified numbers itself.",
    "helpline_name": "Do not name any helpline; the app shows them itself.",
    "treatment_advice": (
        "Do not direct them to a professional or treatment. If it fits, say gently that support is always "
        "available in the app."
    ),
    "quick_fix": "Do not offer a fix, a solution or an instruction to feel differently; acknowledge what they shared.",
}


def problems(text: str) -> list[str]:
    """The guard's checks plus the softer steering checks, as category names."""
    normalised = text.lower().replace("’", "'")
    return violations(text) + [name for name, pattern in STEER_CHECKS.items() if pattern.search(normalised)]


def draft_of(message: dict) -> dict | None:
    """The structured-output tool input carrying the reflection, if this response has one."""
    for block in message.get("content", []):
        tool_use = block.get("toolUse")
        if tool_use and isinstance(tool_use.get("input"), dict) and "reflection" in tool_use["input"]:
            return tool_use["input"]
    return None


class ReplySteering(SteeringHandler):
    """One per check-in agent: guides at most MAX_REWRITES rewrites, then leaves it to the guard."""

    name = "reply_steering"

    def __init__(self) -> None:
        super().__init__()
        self.rewrites = 0
        self.rejected_risk: tuple[RiskLevel, str] | None = None

    async def steer_after_model(self, *, agent: Any, message: dict, stop_reason: Any, **kwargs: Any) -> ModelSteeringAction:
        draft = draft_of(message)
        if draft is None or not isinstance(draft.get("reflection"), str):
            return Proceed(reason="no reflection in this response")
        found = problems(draft["reflection"])
        if not found:
            return Proceed(reason="reflection is supportive")
        if self.rewrites >= MAX_REWRITES:
            log.warning("Steering stopped after %d rewrite(s) (%s); the output guard decides", self.rewrites, ", ".join(found))
            return Proceed(reason="rewrite limit reached")
        self.rewrites += 1
        self._remember_risk(draft)
        # Log the categories only, never the text (journal content stays out of logs).
        log.warning("Steering asked for a rewrite (%s)", ", ".join(found))
        rules = " ".join(GUIDANCE[name] for name in found)
        return Guide(
            reason=(
                f"Rewrite only the reflection. {rules} Reflect what they shared in 2-3 warm sentences; "
                "the single coping exercise is the only suggestion. Keep risk_level, risk_reason, signals "
                "and coping_id exactly as before."
            )
        )

    def _remember_risk(self, draft: dict) -> None:
        try:
            level = RiskLevel.parse(str(draft.get("risk_level", "low")))
        except KeyError:
            return
        if self.rejected_risk is None or level > self.rejected_risk[0]:
            self.rejected_risk = (level, str(draft.get("risk_reason", "")))

    def keep_risk(self, output: AgentOutput) -> AgentOutput:
        """A rewrite must never lower risk: keep the highest level any rejected draft reached."""
        if self.rejected_risk and self.rejected_risk[0] > RiskLevel.parse(output.risk_level):
            level, reason = self.rejected_risk
            return output.model_copy(update={"risk_level": level.name.lower(), "risk_reason": reason})
        return output
