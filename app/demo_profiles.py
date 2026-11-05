"""Five demo people for showing Lantern: a profile, memories, a mood history and Apple Health data.

Loading one replaces the demo user's profile, memories and saved conversation, and reseeds
the check-in history. All names and phone numbers are fictional; the numbers use the
555-01xx range set aside for fiction, so nobody real can be dialled from the demo.
"""

from datetime import date, timedelta

from app.demo import USER_ID, seed_demo
from app.health import simulate
from app.memory import MemoryStore
from app.store.memory import InMemoryStore

DEMO_PROFILES: dict[str, dict] = {
    "dave": {
        "label": "Dave, 15",
        "summary": "Being bullied at school; his mood has slipped all week.",
        "scenario": "decline",
        "profile": {
            "preferred_name": "Dave",
            "age_group": "teen",
            "gender": "male",
            "what_helps": ["music", "skateboarding"],
            "trusted_people": ["Sam", "Mom"],
            "emergency_contact": {"name": "Mom", "phone": "(212) 555-0142"},
        },
        "health": {
            "usual": {"sleep": 8.2, "steps": 9200, "exercise": 45, "rhr": 63, "hrv": 66},
            "recent": {"sleep": 4.6, "steps": 3400, "exercise": 5, "rhr": 70, "hrv": 49},
        },
        "memories": [
            (9, "Sam is Dave's closest friend"),
            (4, "Dave is playing guitar with Sam at the school talent show on Friday"),
        ],
    },
    "maya": {
        "label": "Maya, 24",
        "summary": "Studying for her nursing exam; tracks her cycle, which is due in a few days.",
        "scenario": "steady",
        "profile": {
            "preferred_name": "Maya",
            "age_group": "young_adult",
            "gender": "female",
            "cycle": {"tracking": True, "days_ago": 24, "length": 28, "period_length": 5},
            "what_helps": ["drawing", "journaling"],
            "trusted_people": ["Aunt Rosa"],
            "emergency_contact": {"name": "Aunt Rosa", "phone": "(312) 555-0167"},
        },
        "health": {
            "usual": {"sleep": 7.8, "steps": 7600, "exercise": 25, "rhr": 66, "hrv": 58},
            "recent": {"sleep": 6.9, "steps": 6600, "exercise": 15, "rhr": 68, "hrv": 54},
        },
        "memories": [
            (6, "Maya has her nursing licensing exam on Saturday"),
            (3, "Drawing helps Maya calm down before bed"),
        ],
    },
    "jordan": {
        "label": "Jordan, 21",
        "summary": "College student in a new city; a good week so far.",
        "scenario": "good",
        "profile": {
            "preferred_name": "Jordan",
            "age_group": "young_adult",
            "gender": "male",
            "what_helps": ["running", "gaming with friends"],
            "trusted_people": ["Chris"],
            "emergency_contact": {"name": "Dad", "phone": "(415) 555-0119"},
        },
        "health": {"usual": {"sleep": 7.4, "steps": 11200, "exercise": 50, "rhr": 56, "hrv": 72}},
        "memories": [
            (12, "Jordan moved to a new city for college this fall"),
            (5, "Chris is Jordan's roommate and they run together"),
        ],
    },
    "priya": {
        "label": "Priya, 34",
        "summary": "New mother running on little sleep; ups and downs.",
        "scenario": "steady",
        "profile": {
            "preferred_name": "Priya",
            "age_group": "adult",
            "gender": "female",
            "what_helps": ["short walks", "calling my sister"],
            "trusted_people": ["Arjun", "Neha"],
            "emergency_contact": {"name": "Arjun", "phone": "(646) 555-0183"},
            "health_context": ["new_baby"],
        },
        "health": {
            "usual": {"sleep": 5.6, "steps": 5200, "exercise": 15, "rhr": 68, "hrv": 44},
            "recent": {"sleep": 4.5, "steps": 4800, "exercise": 10, "rhr": 70, "hrv": 41},
        },
        "memories": [
            (14, "Priya's daughter Asha was born in August"),
            (7, "Arjun is Priya's partner and Neha is her sister"),
            (2, "Priya goes back to work part-time next month"),
        ],
    },
    "robert": {
        "label": "Robert, 67",
        "summary": "Recently retired and widowed; just started using Lantern.",
        "scenario": "empty",
        "profile": {
            "preferred_name": "Robert",
            "age_group": "older_adult",
            "gender": "male",
            "what_helps": ["gardening", "walking the dog"],
            "trusted_people": ["Ellen"],
            "emergency_contact": {"name": "Ellen", "phone": "(617) 555-0156"},
        },
        "health": {
            "usual": {"sleep": 7.1, "steps": 7400, "exercise": 35, "rhr": 61, "hrv": 38},
            "recent": {"sleep": 4.9, "steps": 2300, "exercise": 3, "rhr": 66, "hrv": 31},
        },
        "memories": [
            (1, "Ellen is Robert's daughter and calls on Sundays"),
            (1, "Robert walks his dog Biscuit every morning"),
        ],
    },
}


def load_demo_profile(key: str, memory: MemoryStore, store: InMemoryStore, today: date | None = None) -> str:
    """Make the demo user this person. Returns the history scenario that was seeded."""
    demo = DEMO_PROFILES[key]
    today = today or date.today()
    memory.forget_everything(USER_ID)  # clears memories and the saved conversation
    profile = dict(demo["profile"])
    cycle = profile.pop("cycle", None)
    if cycle:
        cycle = dict(cycle)
        cycle["last_start"] = (today - timedelta(days=cycle.pop("days_ago"))).isoformat()
    profile["cycle"] = cycle or {"tracking": False}
    memory.update_profile(USER_ID, profile)
    for days_ago, text in demo["memories"]:
        memory.remember(USER_ID, text, today - timedelta(days=days_ago))
    seed_demo(store, demo["scenario"], today)
    store.clear_health(USER_ID)
    if demo.get("health"):
        seed = sum(map(ord, key))  # stable per person, so the demo looks the same every time
        rows = simulate(demo["health"], today, seed)
        store.save_health(USER_ID, rows)
        # With Health connected, a day's check-in sleep is that night's Health sleep.
        sleep = {r.day: r.sleep_hours for r in rows}
        for cid, c in store.checkins.items():
            if c.user_id == USER_ID and sleep.get(c.day) is not None:
                store.checkins[cid] = c.model_copy(update={"sleep_hours": round(sleep[c.day] * 2) / 2})
    return demo["scenario"]
