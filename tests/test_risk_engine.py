from datetime import date, timedelta

import pytest

from app.models import Checkin, RiskFinding, RiskLevel
from app.risk.engine import combine, keyword_layer, normalise, score_layer, trend_layer

TODAY = date(2026, 11, 3)


def checkin(mood=3, days_ago=0, **kw):
    return Checkin(user_id="u", day=TODAY - timedelta(days=days_ago), mood=mood, **kw)


def keyword_level(note):
    return combine(keyword_layer(note))


@pytest.mark.parametrize(
    "note, expected",
    [
        ("Had a good day", RiskLevel.LOW),
        ("This exam is killing me lol", RiskLevel.LOW),
        ("I'm dying to watch the new movie", RiskLevel.LOW),
        ("I feel so hopeless", RiskLevel.ELEVATED),
        ("I'm a burden", RiskLevel.ELEVATED),
        ("Everyone would be better off without me", RiskLevel.HIGH),
        ("I don't want to wake up tomorrow", RiskLevel.HIGH),
        ("thinking about hurting myself", RiskLevel.HIGH),
        ("I want to kill myself", RiskLevel.IMMINENT),
        ("I WANT TO KILL MYSELF!!!", RiskLevel.IMMINENT),
        ("having suicidal thoughts", RiskLevel.IMMINENT),
        ("I have a plan to end it", RiskLevel.IMMINENT),
    ],
)
def test_keyword_layer(note, expected):
    assert keyword_level(note) == expected


def test_normalise_handles_curly_apostrophes_and_punctuation():
    assert normalise("I don’t   want to WAKE up...") == "i dont want to wake up"


def test_empty_note_has_no_findings():
    assert keyword_layer(None) == [] and keyword_layer("") == []


def test_phq9_item9_any_positive_is_high():
    assert combine(score_layer(checkin(phq9_item9=1))) == RiskLevel.HIGH
    assert combine(score_layer(checkin(phq9_item9=0))) == RiskLevel.LOW


def test_phq2_threshold():
    assert combine(score_layer(checkin(phq2_score=3))) == RiskLevel.ELEVATED
    assert combine(score_layer(checkin(phq2_score=2))) == RiskLevel.LOW


def test_trend_five_low_days_in_seven():
    history = [checkin(mood=2, days_ago=d) for d in (1, 2, 3, 4)]
    assert combine(trend_layer(checkin(mood=2), history)) == RiskLevel.ELEVATED
    assert combine(trend_layer(checkin(mood=4), history)) == RiskLevel.LOW


def test_trend_ignores_days_older_than_a_week():
    history = [checkin(mood=1, days_ago=d) for d in (8, 9, 10, 11)]
    assert combine(trend_layer(checkin(mood=2), history)) == RiskLevel.LOW


def test_trend_sharp_drop():
    history = [checkin(mood=4, days_ago=d) for d in (1, 2, 3)]
    assert combine(trend_layer(checkin(mood=2), history)) == RiskLevel.ELEVATED
    assert combine(trend_layer(checkin(mood=3), history)) == RiskLevel.LOW


def test_sharp_drop_needs_three_prior_days():
    history = [checkin(mood=5, days_ago=1), checkin(mood=5, days_ago=2)]
    assert combine(trend_layer(checkin(mood=1), history)) == RiskLevel.LOW


def test_combine_takes_highest_and_defaults_low():
    assert combine([]) == RiskLevel.LOW
    findings = [
        RiskFinding(source="llm", level=RiskLevel.LOW, reason="x"),
        RiskFinding(source="keyword", level=RiskLevel.IMMINENT, reason="y"),
    ]
    assert combine(findings) == RiskLevel.IMMINENT
