"""Body signals from Apple Health (simulated for the demo).

A real iOS companion app would read HealthKit, work out one summary per day on the device and
send only that: sleep hours, steps, exercise minutes, resting heart rate and HRV. Never raw samples.

Everything here compares a person with their own usual, not with population thresholds:
this week (the last 7 days) against the 4 weeks before. Missing days (the watch wasn't worn)
are skipped, never read as inactivity, and a metric needs enough days on both sides to count.

Body signals can raise risk to elevated at most, never open the crisis screen on their own,
and never lower risk. Heart rate and HRV are context only: they never produce a finding.
"""

import random
from dataclasses import dataclass, field
from datetime import date, timedelta

from pydantic import BaseModel, Field

from app.models import RiskFinding, RiskLevel

RECENT_DAYS = 7
BASELINE_DAYS = 28
MIN_RECENT = 4
MIN_BASELINE = 10
SHORT_NIGHT_HOURS = 5
SHORT_NIGHTS = 4
SLEEP_DROP_HOURS = 1.5
STEPS_DROP = 0.5
MIN_USUAL_STEPS = 3000

# Things the person says affect their sleep or activity. A change they explain isn't a warning sign.
EXPECTED_LABEL = {
    "new_baby": "a new baby",
    "shift_work": "shift work",
    "illness_or_injury": "illness or injury",
    "travel": "travel",
}
SLEEP_EXPECTED = {"new_baby", "shift_work", "travel"}
ACTIVITY_EXPECTED = {"new_baby", "illness_or_injury", "travel"}

METRICS = {
    "sleep_hours": ("Sleep", "h a night"),
    "steps": ("Steps", "a day"),
    "exercise_minutes": ("Exercise", "min a day"),
    "resting_hr": ("Resting heart rate", "bpm"),
    "hrv_ms": ("Heart rate variability", "ms"),
}


class DailyHealth(BaseModel):
    """One day's summary. Sleep is the night that ended on this morning."""

    day: date
    sleep_hours: float | None = Field(default=None, ge=0, le=24)
    steps: int | None = Field(default=None, ge=0)
    exercise_minutes: int | None = Field(default=None, ge=0)
    resting_hr: int | None = Field(default=None, ge=25, le=220)
    hrv_ms: int | None = Field(default=None, ge=1, le=300)


@dataclass(frozen=True)
class Trend:
    recent: float | None
    usual: float | None
    recent_days: int
    usual_days: int

    @property
    def enough(self) -> bool:
        return self.recent_days >= MIN_RECENT and self.usual_days >= MIN_BASELINE


@dataclass(frozen=True)
class BodySummary:
    trends: dict[str, Trend] = field(default_factory=dict)
    short_nights: int = 0
    nights: int = 0
    last_night_sleep: float | None = None

    @property
    def available(self) -> bool:
        return any(t.enough for t in self.trends.values())


def _round(name: str, value: float) -> float:
    return round(value, 1) if name == "sleep_hours" else round(value)


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def summarize(rows: list[DailyHealth], today: date) -> BodySummary:
    """This week (today and the 6 days before) against the 28 days before that."""
    recent_start = today - timedelta(days=RECENT_DAYS - 1)
    usual_start = recent_start - timedelta(days=BASELINE_DAYS)
    recent = [r for r in rows if recent_start <= r.day <= today]
    usual = [r for r in rows if usual_start <= r.day < recent_start]
    trends = {}
    for name in METRICS:
        rv = [getattr(r, name) for r in recent if getattr(r, name) is not None]
        uv = [getattr(r, name) for r in usual if getattr(r, name) is not None]
        trends[name] = Trend(_mean(rv), _mean(uv), len(rv), len(uv))
    sleeps = [r.sleep_hours for r in recent if r.sleep_hours is not None]
    last = next((r.sleep_hours for r in rows if r.day == today), None)
    return BodySummary(trends, sum(s < SHORT_NIGHT_HOURS for s in sleeps), len(sleeps), last)


def body_layer(summary: BodySummary, expected: set[str] | frozenset[str] = frozenset()) -> list[RiskFinding]:
    """Deterministic body-signal findings: elevated at most, with a plain reason each."""
    findings = []
    sleep = summary.trends.get("sleep_hours")
    if not (set(expected) & SLEEP_EXPECTED):
        if summary.nights >= MIN_RECENT and summary.short_nights >= SHORT_NIGHTS:
            findings.append(_finding(f"Slept under {SHORT_NIGHT_HOURS} hours on {summary.short_nights} of the last {summary.nights} nights (Apple Health)"))
        elif sleep and sleep.enough and sleep.usual - sleep.recent >= SLEEP_DROP_HOURS:
            findings.append(_finding(f"Sleeping about {sleep.recent:.1f} h a night this week, down from your usual {sleep.usual:.1f} h (Apple Health)"))
    steps = summary.trends.get("steps")
    if not (set(expected) & ACTIVITY_EXPECTED) and steps and steps.enough and steps.usual >= MIN_USUAL_STEPS:
        if steps.recent <= STEPS_DROP * steps.usual:
            drop = round(100 * (1 - steps.recent / steps.usual))
            findings.append(_finding(f"Steps down {drop}% this week: {steps.recent:,.0f} a day against your usual {steps.usual:,.0f} (Apple Health)"))
    return findings


def _finding(reason: str) -> RiskFinding:
    return RiskFinding(source="body", level=RiskLevel.ELEVATED, reason=reason)


def signals_for_agent(summary: BodySummary, expected: set[str] | frozenset[str] = frozenset()) -> dict:
    """What the agent tool returns: weekly averages against their usual, never raw samples."""
    if not summary.available:
        return {"available": False, "note": "No wearable data, or not enough days to compare."}
    out: dict = {"available": True, "source": "Apple Health, estimates from a wearable"}
    for name, (label, unit) in METRICS.items():
        t = summary.trends[name]
        if t.enough:
            out[name] = {"this_week": _round(name, t.recent), "usual": _round(name, t.usual), "unit": unit}
    if summary.nights:
        out["nights_under_5h_this_week"] = f"{summary.short_nights} of {summary.nights}"
    if expected:
        out["expected_because_of"] = [EXPECTED_LABEL[e] for e in sorted(expected)]
    return out


def body_json(summary: BodySummary, expected: set[str] | frozenset[str] = frozenset()) -> dict:
    """For the app: rows to display, the findings' reasons, and last night's sleep."""
    rows = []
    for name, (label, unit) in METRICS.items():
        t = summary.trends[name] if summary.trends else None
        if t and t.enough:
            rows.append({"key": name, "label": label, "unit": unit, "this_week": _round(name, t.recent), "usual": _round(name, t.usual)})
    return {
        "available": summary.available,
        "rows": rows,
        "noticed": [f.reason for f in body_layer(summary, expected)],
        "expected": [EXPECTED_LABEL[e] for e in sorted(expected)],
        "last_night_sleep": summary.last_night_sleep,
    }


def simulate(spec: dict, today: date, seed: int, days: int = RECENT_DAYS + BASELINE_DAYS) -> list[DailyHealth]:
    """Synthetic daily summaries: a usual pattern, an optional change over the last few days, gaps."""
    rng = random.Random(seed)
    usual, recent, recent_days = spec["usual"], spec.get("recent"), spec.get("recent_days", 6)
    rows = []
    for days_ago in range(days - 1, -1, -1):
        day = today - timedelta(days=days_ago)
        if days_ago > 0 and rng.random() < spec.get("missing", 0.08):
            continue  # the watch wasn't worn: no row at all, never zeros
        p = recent if recent and days_ago < recent_days else usual
        rows.append(
            DailyHealth(
                day=day,
                sleep_hours=round(max(2.0, min(11.0, rng.gauss(p["sleep"], 0.45))), 1),
                steps=max(200, int(rng.gauss(p["steps"], p["steps"] * 0.15))),
                exercise_minutes=max(0, int(rng.gauss(p["exercise"], max(3, p["exercise"] * 0.3)))),
                resting_hr=int(round(rng.gauss(p["rhr"], 1.5))),
                hrv_ms=max(10, int(round(rng.gauss(p["hrv"], 5)))),
            )
        )
    return rows
