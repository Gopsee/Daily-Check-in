from datetime import date
from typing import Protocol

from app.health import DailyHealth
from app.models import Checkin, RiskFinding


class Store(Protocol):
    def save_checkin(self, checkin: Checkin) -> str:
        """Persist a check-in and return its id."""

    def get_history(self, user_id: str, days: int, today: date) -> list[Checkin]:
        """Check-ins dated within `days` before `today`, plus `today`, oldest first."""

    def save_risk_findings(self, checkin_id: str, findings: list[RiskFinding]) -> None: ...

    def save_health(self, user_id: str, rows: list[DailyHealth]) -> None:
        """Replace or add daily health summaries (one per day)."""

    def get_health(self, user_id: str, days: int, today: date) -> list[DailyHealth]:
        """Daily health summaries within `days` before `today`, plus `today`, oldest first."""
