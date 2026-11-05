"""Period cycle: a few dates in, a phase out.

The person gives their last period start date, typical cycle length and period length. Code
works out where they are in the cycle. Models only ever see the phase, never the dates.
"""

from dataclasses import dataclass
from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, field_validator

PREMENSTRUAL_DAYS = 7  # the week before a period, when many people notice mood changes
STALE_CYCLES = 3  # predictions from an older start date are too rough to use


class Cycle(BaseModel):
    tracking: bool = False
    last_start: date | None = None
    length: int = Field(default=28, ge=21, le=45)
    period_length: int = Field(default=5, ge=2, le=8)

    @field_validator("last_start")
    @classmethod
    def not_in_future(cls, value: date | None) -> date | None:
        if value is not None and value > date.today():
            raise ValueError("last period start can't be in the future")
        return value


@dataclass(frozen=True)
class CycleStatus:
    phase: Literal["period", "premenstrual", "other"]
    cycle_day: int
    days_until_next: int


def status(cycle: Cycle | None, today: date) -> CycleStatus | None:
    """Where they are in the cycle today, or None if not tracking or the start date is too old."""
    if not cycle or not cycle.tracking or not cycle.last_start or cycle.last_start > today:
        return None
    days_since = (today - cycle.last_start).days
    if days_since > STALE_CYCLES * cycle.length:
        return None
    cycle_day = days_since % cycle.length + 1
    days_until_next = cycle.length - days_since % cycle.length
    if cycle_day <= cycle.period_length:
        phase = "period"
    elif days_until_next <= PREMENSTRUAL_DAYS:
        phase = "premenstrual"
    else:
        phase = "other"
    return CycleStatus(phase, cycle_day, days_until_next)


def describe(s: CycleStatus | None) -> str | None:
    """One line for the model: the phase only, no dates."""
    if s is None or s.phase == "other":
        return None
    if s.phase == "period":
        return f"on their period (about day {s.cycle_day})"
    return f"in the days before their period (expected in about {s.days_until_next} days)"
