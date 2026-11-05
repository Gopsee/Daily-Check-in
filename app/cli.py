"""Terminal check-in for testing the agent before any UI exists.

    python -m app.cli                 # fresh user
    python -m app.cli --demo decline  # preload a week of low moods to see the trend layer
"""

import argparse
import logging
from datetime import date, timedelta

from app import config
from app.models import Checkin, CheckinResult, RiskLevel
from app.service import submit_checkin
from app.store.memory import InMemoryStore

USER_ID = "demo-user"
LEVEL_LABEL = {
    RiskLevel.LOW: "🟢 Low",
    RiskLevel.ELEVATED: "🟡 Elevated",
    RiskLevel.HIGH: "🟠 High",
    RiskLevel.IMMINENT: "🔴 Imminent",
}


def seed_decline(store: InMemoryStore) -> None:
    today = date.today()
    for days_ago, mood, note in [
        (6, 3, "Busy week"), (5, 2, "Didn't sleep well"), (4, 2, "Exams stressing me out"),
        (3, 1, "Skipped classes"), (2, 2, "Tired of everything"), (1, 2, "Stayed in my room all day"),
    ]:
        store.save_checkin(Checkin(user_id=USER_ID, day=today - timedelta(days=days_ago), mood=mood, note=note))


def ask_int(prompt: str, lo: int, hi: int, optional: bool = False) -> int | None:
    while True:
        raw = input(prompt).strip()
        if optional and not raw:
            return None
        if raw.isdigit() and lo <= int(raw) <= hi:
            return int(raw)
        print(f"  Please enter a number from {lo} to {hi}.")


def ask_hours(prompt: str) -> float | None:
    while True:
        raw = input(prompt).strip()
        if not raw:
            return None
        try:
            hours = float(raw)
        except ValueError:
            hours = -1
        if 0 <= hours <= 24:
            return hours
        print("  Please enter hours from 0 to 24, e.g. 6.5.")


def collect_checkin() -> Checkin:
    mood = ask_int("Mood today (1 very low – 5 very good): ", 1, 5)
    tags = [t.strip() for t in input("Tags, comma separated (e.g. anxious, tired) [optional]: ").split(",") if t.strip()]
    sleep = ask_hours("Hours slept [optional]: ")
    note = input("Anything on your mind? [optional]: ").strip() or None

    phq2 = item9 = None
    if mood <= 2:
        print("\nOver the last 2 weeks, how often have you been bothered by... (0 not at all, 1 several days,")
        print("2 more than half the days, 3 nearly every day)")
        phq2 = ask_int("  Little interest or pleasure in doing things: ", 0, 3) + ask_int(
            "  Feeling down, depressed, or hopeless: ", 0, 3
        )
        if phq2 >= 3:
            item9 = ask_int("  Thoughts that you'd be better off dead, or of hurting yourself: ", 0, 3)

    return Checkin(user_id=USER_ID, mood=mood, tags=tags, sleep_hours=sleep, note=note, phq2_score=phq2, phq9_item9=item9)


def format_hotlines(hotlines: list[dict]) -> list[str]:
    lines = []
    for line in hotlines:
        contact = " / ".join(x for x in [line.get("phone"), line.get("alt_phone"), line.get("sms"), line.get("url")] if x)
        lines.append(f"   • {line['name']}: {contact}")
    return lines


def render(result: CheckinResult) -> None:
    if result.show_crisis:
        print("\n" + "=" * 64)
        print("  It sounds like you're carrying a lot right now.")
        print("  You don't have to go through this alone. You can talk to someone now:\n")
        print("\n".join(format_hotlines(result.hotlines)))
        print("=" * 64)

    print(f"\n{result.reflection}")
    if not result.ai_available:
        print("(Our AI couldn't respond just now, so this is a standard message.)")

    if result.coping:
        print(f"\nTry this: {result.coping['title']}")
        for step in result.coping["steps"]:
            print(f"  - {step}")

    if result.final_risk == RiskLevel.ELEVATED:
        print("\nWould talking to someone help? These lines are free and confidential:")
        print("\n".join(format_hotlines(result.hotlines)))

    print(f"\nRisk level: {LEVEL_LABEL[result.final_risk]}")
    for finding in result.findings:
        if finding.level > RiskLevel.LOW:
            print(f"  [{finding.source}] {finding.reason}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Daily mental health check-in (terminal)")
    parser.add_argument("--demo", choices=["decline"], help="preload sample history")
    parser.add_argument("--region", default=config.HOTLINE_REGION, help="hotline region code, e.g. IN, US, GB, AU")
    parser.add_argument("-v", "--verbose", action="store_true", help="show model errors and fallbacks")
    args = parser.parse_args()
    logging.basicConfig(level=logging.ERROR, format="  (%(name)s) %(message)s")
    if args.verbose:
        logging.getLogger("app").setLevel(logging.INFO)

    store = InMemoryStore()
    if args.demo == "decline":
        seed_decline(store)

    print("Daily check-in. This is not a substitute for professional care, and AI can misjudge.\n")
    checkin = collect_checkin()
    print("\nThinking...")
    render(submit_checkin(store, checkin, region=args.region))


if __name__ == "__main__":
    main()
