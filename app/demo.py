"""Seeded demo history for the UI and the pitch."""

import random
from datetime import date, timedelta

from app.models import Checkin
from app.store.memory import InMemoryStore

USER_ID = "demo-user"
SCENARIOS = ("decline", "good", "steady", "empty")
DEMO_NOTES = {
    1: ["Couldn't get out of bed", "Everything feels heavy"],
    2: ["Didn't sleep well", "Exams stressing me out", "Stayed in my room all day"],
    3: ["Busy week", "Okay day, nothing special"],
    4: ["Good walk in the evening", "Slept well, gym done"],
    5: ["Great day with friends", "Finished my project"],
}
# The last 7 days, oldest first.
DECLINE_WEEK = [3, 2, 2, 1, 2, 2]  # 6 days: with a low check-in today, the trend layer flags 🟡
GOOD_WEEK = [5, 4, 4, 3, 4, 5, 4]  # 7 days: good (4 or 5) on 6 of them, one okay day
GOOD_WEEK_NOTES = [
    "Great dinner with friends",
    "Slept well, gym done",
    "Finished a big assignment",
    "Busy day, a bit tired",
    "Long walk in the evening",
    "Called my family, felt really good",
    "Productive and calm day",
]


def seed_demo(store: InMemoryStore, scenario: str, today: date | None = None) -> None:
    """30 days of history.

    decline: ends with a week of low moods, so the trend layer raises 🟡 Elevated.
    good: the last 7 days are good on 6 of them, so nothing is flagged.
    steady: ordinary ups and downs. empty: no history.
    """
    store.checkins.clear()
    store.findings.clear()
    if scenario == "empty":
        return
    today = today or date.today()
    rng = random.Random(7)
    walk = 4
    for days_ago in range(30, 0, -1):
        walk = min(5, max(3, walk + rng.choice([-1, 0, 0, 1])))  # gentle ups and downs
        if days_ago > 7 and rng.random() < 0.12:  # missed days are normal; keep the last week intact
            continue
        note = None
        if scenario == "decline" and days_ago <= len(DECLINE_WEEK):
            mood = DECLINE_WEEK[-days_ago]
        elif scenario == "good" and days_ago <= len(GOOD_WEEK):
            mood, note = GOOD_WEEK[-days_ago], GOOD_WEEK_NOTES[-days_ago]
        else:
            mood = walk
        tags = rng.sample(["tired", "stressed", "lonely", "anxious"] if mood <= 2 else ["calm", "motivated", "grateful"], 2)
        store.save_checkin(
            Checkin(
                user_id=USER_ID,
                day=today - timedelta(days=days_ago),
                mood=mood,
                tags=tags,
                sleep_hours=rng.choice([5, 5.5, 6, 6.5]) if mood <= 2 else rng.choice([6.5, 7, 7.5, 8]),
                note=note or rng.choice(DEMO_NOTES[mood]),
            )
        )
