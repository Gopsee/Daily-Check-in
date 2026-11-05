"""Live eval against Bedrock. Run with:  python -m pytest -m live -v

Checks the whole system (rules + LLM) reaches at least the expected level for
each phrase. Recall matters more than precision here, so over-escalating a
safe phrase is reported but does not fail the test.
"""

import pytest

from app.models import Checkin, RiskLevel
from app.service import submit_checkin
from app.store.memory import InMemoryStore
from tests.risk_phrases import PHRASES


@pytest.mark.live
@pytest.mark.parametrize("note, minimum", PHRASES, ids=[p[0][:40] for p in PHRASES])
def test_system_reaches_minimum_level(note, minimum):
    result = submit_checkin(InMemoryStore(), Checkin(user_id="eval", mood=3, note=note))
    assert not any(f.source == "failsafe" for f in result.findings), "agent call failed"
    assert result.final_risk >= minimum, f"{note!r}: got {result.final_risk.name}, need {minimum.name}"
    if minimum == RiskLevel.LOW and result.final_risk > RiskLevel.LOW:
        print(f"over-escalated (allowed): {note!r} -> {result.final_risk.name}")
