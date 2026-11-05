import uuid
from datetime import date

from app.health import DailyHealth
from app.models import Checkin, RiskFinding


class InMemoryStore:
    """Process-local store for development and tests. Swapped for SQLite in step 4."""

    def __init__(self) -> None:
        self.checkins: dict[str, Checkin] = {}
        self.findings: dict[str, list[RiskFinding]] = {}
        self.health: dict[str, dict[date, DailyHealth]] = {}

    def save_checkin(self, checkin: Checkin) -> str:
        checkin_id = checkin.id or uuid.uuid4().hex
        self.checkins[checkin_id] = checkin.model_copy(update={"id": checkin_id})
        return checkin_id

    def get_history(self, user_id: str, days: int, today: date) -> list[Checkin]:
        rows = [
            c for c in self.checkins.values() if c.user_id == user_id and 0 <= (today - c.day).days <= days
        ]
        return sorted(rows, key=lambda c: c.day)

    def save_risk_findings(self, checkin_id: str, findings: list[RiskFinding]) -> None:
        self.findings[checkin_id] = list(findings)

    def save_health(self, user_id: str, rows: list[DailyHealth]) -> None:
        days = self.health.setdefault(user_id, {})
        for row in rows:
            days[row.day] = row

    def get_health(self, user_id: str, days: int, today: date) -> list[DailyHealth]:
        rows = [r for d, r in self.health.get(user_id, {}).items() if 0 <= (today - d).days <= days]
        return sorted(rows, key=lambda r: r.day)

    def clear_health(self, user_id: str) -> None:
        self.health.pop(user_id, None)
