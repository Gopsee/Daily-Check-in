"""Mobile check-in app (HTML UI + Python backend).

    python -m app.web                      # http://localhost:8000
    python -m app.web --host 0.0.0.0       # open it from a phone on the same Wi-Fi
    python -m app.web --no-agent           # skip Nova Pro: risk rules and standard messages only
                                           # (the Talk tab still uses Nova Sonic)
    python -m app.web --profile maya       # start as a demo person: dave, maya, jordan, priya, robert
"""

import argparse
import logging

import uvicorn

from app import config
from app.demo import SCENARIOS
from app.demo_profiles import DEMO_PROFILES
from app.web.server import create_app


def no_agent(store, checkin):
    raise RuntimeError("agent disabled with --no-agent")


def main() -> None:
    parser = argparse.ArgumentParser(description="Daily check-in mobile web app")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--demo", choices=SCENARIOS, default="decline", help="seeded history")
    parser.add_argument("--profile", choices=DEMO_PROFILES, help="load a demo person (profile, memories and history)")
    parser.add_argument("--region", default=config.HOTLINE_REGION, help="default hotline region, e.g. IN, US, GB, AU")
    parser.add_argument("--no-agent", action="store_true", help="skip Nova Pro (rules + standard messages only); voice still uses Nova Sonic")
    args = parser.parse_args()
    logging.basicConfig(level=logging.WARNING, format="  (%(name)s) %(message)s")

    if args.no_agent:
        app = create_app(run_agent=no_agent, classify=None, scenario=args.demo, region=args.region, demo_profile=args.profile)
    else:
        app = create_app(scenario=args.demo, region=args.region, demo_profile=args.profile)
    print(f"Daily check-in running at http://{args.host}:{args.port}")
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
