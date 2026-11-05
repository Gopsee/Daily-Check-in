# Lantern

**Because sometimes, you're the last to notice.**

Lantern is a one-minute daily mental health check-in run by AI agents built with the [Strands Agents SDK](https://strandsagents.com) on Amazon Bedrock. It notices when someone is slipping, reads what they say between the lines, and puts a real human within reach the moment it senses risk.

- **Demo video (2:49):** [add YouTube link]
- **Article:** [add Builder Center link]

> Lantern is a prototype, not a clinical tool or a substitute for professional care. If you or someone you know is struggling, call or text **988** in the US.

## What it does

1. **Daily check-in.** Mood, up to 3 tags, sleep and an optional note. On low days it asks the two PHQ-2 screening questions.
2. **A short, kind reply.** A Strands agent on Amazon Nova Pro writes 2–3 sentences and picks one exercise from a reviewed list. It never diagnoses.
3. **Notices the pattern.** Rules watch the 7-day mood trend, and the agent reads indirect wording that no keyword list catches.
4. **Crisis screen.** On high risk, a calm screen offers one-tap call or text to 988, the Crisis Text Line and 911 (or the local lines for India, the UK or Australia), and explains why it opened.
5. **Just talk.** A voice agent on Amazon Nova Sonic listens and replies out loud. Every line the person says gets the same safety checks, live.
6. **Remembers, transparently.** A profile (name, age group 13–17 / 18–25 / 26–59 / 60+, gender, what helps, people they trust, an emergency contact) and short facts the agents save. The person sees every memory and can delete any of them, or forget everything.
7. **Cycle-aware, never dismissive.** Period-cycle tracking is offered to anyone except a male profile, and is on by default for Female. The History chart shades the week before each predicted period and counts how many low days fell in it. Models see only the phase, never dates, and are told never to explain feelings away with hormones or lower risk because of the cycle.
8. **Notices the body, too (Apple Health, simulated).** Sleep, steps, exercise, resting heart rate and HRV, each compared with the person's own usual. A big drop in sleep or steps is a finding with a plain reason ("Steps down 61% this week"), shown as "Lantern noticed" even before they check in. Body signals can raise risk to elevated at most, never open the crisis screen alone, and never lower risk; heart data is context only, and changes the person expects (a new baby, shift work, illness, travel) aren't treated as warning signs.

## How it's built

| Part | Strands feature | File |
|---|---|---|
| Check-in agent | `Agent` on Nova Pro with `structured_output_model` | `app/agent/agent.py` |
| User-bound tools | `@tool`: `get_mood_history`, `list_coping_exercises` | `app/agent/tools.py` |
| Reply steering | `SteeringHandler`: `steer_after_model` returns `Guide` | `app/agent/steering.py` |
| Output guard | `HookProvider` on `AfterInvocationEvent` | `app/agent/guard.py` |
| Voice agent | `BidiAgent` on Nova Sonic | `app/voice/agent.py` |
| Per-line risk check | `Agent` on Nova Pro with structured output | `app/agent/agent.py` |
| Body signals | `@tool get_body_signals` (weekly summaries) + a deterministic rule layer | `app/health.py` |
| Memory | `FileSessionManager` + `SlidingWindowConversationManager`, `@tool remember` | `app/memory.py` |

Safety is decided in plain code around the agents:

- **The AI can raise risk, never lower it.** Rules (phrases, PHQ-2 and item 9, 7-day trend) and the agent each produce findings, and the final level is the highest one (`app/service.py`).
- **Help before the AI finishes.** A rules-only precheck can open the crisis screen before the agent replies.
- **Steering first.** If a draft reply diagnoses, hints at a condition, mentions medication, sends the person to treatment or offers a quick fix, a Strands steering handler discards it and asks the agent for one rewrite. A rewrite can never lower the risk level.
- **Output guard.** If the rewrite still fails, a hook replaces any reflection that contains phone numbers, helpline names, medication or diagnostic language. It never touches the risk level.
- **Fail-safe.** If the model fails, the check-in is already saved, the rules still decide, and an unread note raises the level to elevated.
- **Works offline.** Hotline numbers are built into the page, never written by a model.
- **Memory without anchoring.** The agents remember recent conversation, but today's risk is judged on its own and the `max()` merge still applies. The emergency contact's phone number is shown on the crisis screen only and never reaches a model. Crisis details and phone numbers are never saved as memories.

See [How Lantern works](docs/how-it-works.md) for diagrams and a walkthrough, and [Architecture.md](Architecture.md) for the full design reference.

## Results

Measured against live Amazon Bedrock on 5 November 2026. Small samples from single runs, not a clinical validation.

| Measure | Result |
|---|---|
| Risk detection (`pytest -m live`) | 17 of 17 labelled notes reached their required level; 0 of 5 safe notes over-escalated |
| Rules speed | 0.035 ms per evaluation |
| Agent reply time | median 5.1 s, slowest 8.3 s (16 check-ins) |
| Output guard | replaced 3 of 12 adversarial replies, 0 of 10 normal ones |
| Cost per check-in | about $0.004 (Nova Pro on-demand, Sydney pricing) |

## Run it

You need Python 3.12 and AWS credentials with Amazon Bedrock access to:

- **Amazon Nova Pro** through the APAC inference profile `apac.amazon.nova-pro-v1:0`, called from `ap-southeast-2`
- **Amazon Nova Sonic** (`amazon.nova-2-5-sonic`) in `ap-northeast-1`, for the voice tab

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m app.web --region US       # open http://localhost:8000
```

No Bedrock access? `python -m app.web --no-agent` runs the rules, standard replies and the crisis screen without Nova Pro.

| Flag | Default | What it does |
|---|---|---|
| `--region` | `IN` | Crisis lines to show: `US`, `IN`, `GB`, `AU` |
| `--demo` | `decline` | Seeded history: `decline`, `good`, `steady` or `empty` (use `empty` to start fresh) |
| `--host`, `--port` | `127.0.0.1`, `8000` | Use `--host 0.0.0.0` to open it from a phone on the same Wi-Fi |
| `--no-agent` | off | Skip Nova Pro; the voice tab still uses Nova Sonic |
| `--profile` | none | Start as a demo person: `dave` (15), `maya` (16), `jordan` (21), `priya` (34) or `robert` (67) |

Environment variables (all optional):

| Variable | Default |
|---|---|
| `CHECKIN_MODEL_ID` | `apac.amazon.nova-pro-v1:0` |
| `CHECKIN_AWS_REGION` | `ap-southeast-2` |
| `CHECKIN_MODEL_TIMEOUT_S` | `30` |
| `CHECKIN_VOICE_MODEL_ID` | `amazon.nova-2-5-sonic` |
| `CHECKIN_VOICE_REGION` | `ap-northeast-1` |
| `CHECKIN_VOICE_ID` | `tiffany` |
| `CHECKIN_HOTLINE_REGION` | `IN` |
| `CHECKIN_DATA_DIR` | `.lantern` (profiles and session files; personal data, git-ignored) |
| `CHECKIN_MEMORY_WINDOW` | `48` messages kept by the check-in agent |
| `CHECKIN_VOICE_MEMORY_WINDOW` | `20` messages kept by the voice agent |

**Demo people.** Five fictional people come with a profile, memories and a matching mood history: Dave (15, bullied at school), Maya (16, exam stress, tracks her cycle), Jordan (21, college student), Priya (34, new mother) and Robert (67, recently widowed). Each also has 5 weeks of simulated Apple Health data: Dave's sleep and steps fall as the bullying starts, Robert's dog walks stop before he has ever checked in, and Priya's short sleep is marked as expected with a new baby. Load one at start-up with `--profile`, e.g. `python -m app.web --region US --profile dave`. Their emergency numbers use the 555-01xx range reserved for fiction.

There is also a terminal version: `python -m app.cli --demo decline`.

## Tests

```bash
pytest              # 146 offline tests, no AWS needed
pytest -m live      # live eval against Bedrock
```

## Project layout

```
app/
  agent/    Strands check-in agent, tools, prompts, output guard
  voice/    Nova Sonic BidiAgent and the live voice session
  risk/     deterministic risk engine and phrase rules
  store/    storage interface and in-memory store
  web/      Starlette server and the mobile web UI
  data/     reviewed coping exercises and crisis hotlines
  service.py  one check-in: save, rules, agent, merge, reply
tests/      offline tests and the live eval
```

## Limitations

- Demo storage: check-ins are in memory, and profiles and memory are unencrypted local files, all for one shared demo user. Real use needs sign-in, encrypted storage and data retention.
- Apple Health data is simulated. A real version needs a native iOS companion app (HealthKit has no web API) that sends daily summaries only.
- Follow-ups from memory are hit and miss: the agent saves the right facts, but doesn't always ask about them later.
- Not yet reviewed by clinicians or tested with teens.
- English only.
- Voice replies play directly and can't be filtered first; safety checks run on what the person says.

## License

[MIT](LICENSE)
