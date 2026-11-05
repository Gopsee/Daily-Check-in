"""Loaders for bundled static data (hotlines, coping exercises)."""

import json
from functools import cache
from pathlib import Path

_DIR = Path(__file__).parent


@cache
def _hotlines() -> dict:
    return json.loads((_DIR / "hotlines.json").read_text())


@cache
def coping_exercises() -> list[dict]:
    return json.loads((_DIR / "coping.json").read_text())


def hotlines_for(region: str) -> list[dict]:
    data = _hotlines()
    return data.get(region.upper(), data["DEFAULT"])


def coping_by_id(coping_id: str | None) -> dict | None:
    return next((c for c in coping_exercises() if c["id"] == coping_id), None)
