"""Agent tools. Built per check-in so each tool is bound to one user's data only."""

from datetime import date

from strands import tool

from app.data import coping_exercises
from app.store.base import Store


def make_tools(store: Store, user_id: str, today: date) -> list:
    @tool
    def get_mood_history(days: int = 14) -> dict:
        """Get this user's recent check-ins (including today's), oldest first.

        Args:
            days: How many days back to look, between 1 and 30.
        """
        days = max(1, min(days, 30))
        return {
            "checkins": [
                {
                    "date": c.day.isoformat(),
                    "mood": c.mood,
                    "tags": c.tags,
                    "sleep_hours": c.sleep_hours,
                    "note": (c.note or "")[:300],
                }
                for c in store.get_history(user_id, days, today)
            ]
        }

    @tool
    def list_coping_exercises() -> dict:
        """List the reviewed coping exercises the app can show. Pick at most one by id."""
        return {
            "exercises": [{"id": c["id"], "title": c["title"], "good_for": c["good_for"]} for c in coping_exercises()]
        }

    return [get_mood_history, list_coping_exercises]
