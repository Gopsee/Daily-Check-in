"""Shared data types."""

from datetime import date
from enum import IntEnum
from typing import Literal

from pydantic import BaseModel, Field


class RiskLevel(IntEnum):
    """Ordered so that max() picks the most severe level."""

    LOW = 0
    ELEVATED = 1
    HIGH = 2
    IMMINENT = 3

    @classmethod
    def parse(cls, name: str) -> "RiskLevel":
        return cls[name.upper()]


class Checkin(BaseModel):
    user_id: str
    day: date = Field(default_factory=date.today)
    mood: int = Field(ge=1, le=5)
    tags: list[str] = Field(default_factory=list)
    sleep_hours: float | None = Field(default=None, ge=0, le=24)
    note: str | None = None
    phq2_score: int | None = Field(default=None, ge=0, le=6)
    phq9_item9: int | None = Field(default=None, ge=0, le=3)
    id: str | None = None


class RiskFinding(BaseModel):
    source: Literal["keyword", "score", "trend", "llm", "failsafe"]
    level: RiskLevel
    reason: str


class AgentOutput(BaseModel):
    """Structured output the agent must return for every check-in."""

    reflection: str = Field(
        description="2-3 warm, plain-language sentences reflecting the check-in back to the user. No diagnosis."
    )
    risk_level: Literal["low", "elevated", "high", "imminent"] = Field(
        description="Self-harm / suicide risk read from the check-in. When unsure between two levels, pick the higher."
    )
    risk_reason: str = Field(description="One short sentence explaining the risk level, citing what the user said.")
    signals: list[str] = Field(
        default_factory=list,
        description="Short snake_case risk signals, e.g. passive_ideation, hopelessness, isolation. Empty if none.",
    )
    coping_id: str | None = Field(
        default=None, description="id of the one exercise from list_coping_exercises that fits best right now. Always pick one."
    )


class UtteranceRisk(BaseModel):
    """Structured output for the live risk check on one line spoken in the voice chat."""

    risk_level: Literal["low", "elevated", "high", "imminent"] = Field(
        description="Self-harm / suicide risk shown by the latest line. When unsure between two levels, pick the higher."
    )
    risk_reason: str = Field(description="One short sentence explaining the level, citing what the person said.")


class CheckinResult(BaseModel):
    checkin_id: str
    final_risk: RiskLevel
    findings: list[RiskFinding]
    reflection: str
    coping: dict | None
    hotlines: list[dict]
    ai_available: bool = True

    @property
    def show_crisis(self) -> bool:
        return self.final_risk >= RiskLevel.HIGH

    @property
    def reasons(self) -> list[str]:
        return [f.reason for f in self.findings if f.level > RiskLevel.LOW]
