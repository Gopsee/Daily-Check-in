from datetime import date
from typing import Protocol

from app.models import Checkin, RiskFinding


class Store(Protocol):
    def save_checkin(self, checkin: Checkin) -> str:
        """Persist a check-in and return its id."""

    def get_history(self, user_id: str, days: int, today: date) -> list[Checkin]:
        """Check-ins dated within `days` before `today`, plus `today`, oldest first."""

    def save_risk_findings(self, checkin_id: str, findings: list[RiskFinding]) -> None: ...
