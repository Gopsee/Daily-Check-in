"""Deterministic risk engine.

Runs on every check-in, independent of the LLM, so escalation still works
when the model is down, wrong, or manipulated by the journal text.
"""

import re

from app.models import Checkin, RiskFinding, RiskLevel
from app.risk.phrases import PHRASES


def normalise(text: str) -> str:
    text = text.lower().replace("'", "").replace("’", "")
    text = re.sub(r"[^\w\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def keyword_layer(note: str | None) -> list[RiskFinding]:
    if not note:
        return []
    text = normalise(note)
    findings = []
    for level, phrases in PHRASES.items():
        for reason, pattern in phrases:
            if re.search(rf"\b(?:{pattern})\b", text):
                findings.append(RiskFinding(source="keyword", level=level, reason=reason))
    return findings


def score_layer(checkin: Checkin) -> list[RiskFinding]:
    findings = []
    if checkin.phq9_item9 is not None and checkin.phq9_item9 >= 1:
        findings.append(
            RiskFinding(source="score", level=RiskLevel.HIGH, reason="Reported thoughts of self-harm (PHQ-9 item 9)")
        )
    if checkin.phq2_score is not None and checkin.phq2_score >= 3:
        findings.append(
            RiskFinding(source="score", level=RiskLevel.ELEVATED, reason="PHQ-2 score suggests low mood worth checking")
        )
    return findings


def trend_layer(checkin: Checkin, history: list[Checkin]) -> list[RiskFinding]:
    """history: earlier check-ins for the same user (current one excluded)."""
    findings = []
    last_week = [c for c in history if 1 <= (checkin.day - c.day).days <= 6]
    low_days = sum(c.mood <= 2 for c in last_week) + (checkin.mood <= 2)
    if low_days >= 5:
        findings.append(
            RiskFinding(source="trend", level=RiskLevel.ELEVATED, reason=f"Low mood on {low_days} of the last 7 days")
        )

    prior = [c.mood for c in history if 1 <= (checkin.day - c.day).days <= 7]
    if len(prior) >= 3:
        average = sum(prior) / len(prior)
        if average - checkin.mood >= 2:
            findings.append(
                RiskFinding(
                    source="trend",
                    level=RiskLevel.ELEVATED,
                    reason=f"Mood dropped sharply (today {checkin.mood} vs recent average {average:.1f})",
                )
            )
    return findings


def evaluate(checkin: Checkin, history: list[Checkin]) -> list[RiskFinding]:
    return keyword_layer(checkin.note) + score_layer(checkin) + trend_layer(checkin, history)


def combine(findings: list[RiskFinding]) -> RiskLevel:
    """Highest level wins. Nothing can lower a level another layer raised."""
    return max((f.level for f in findings), default=RiskLevel.LOW)
